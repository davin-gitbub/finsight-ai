"""FinSight AI — FastAPI 入口

API 路由：
  WS  /ws/chat             流式对话（核心）
  POST /api/chat           非流式备选
  POST /api/chat/stream    SSE 流式（主页面用）
  POST /api/feedback 用户反馈
  GET  /health       健康检查
"""

import json
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import settings
from session import session_manager
from rag import rag_pipeline_stream
from ratelimit import rate_limiter


# ──── Lifespan ────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化 Chroma + 预加载模型，关闭时清理 session"""
    from rag import get_chroma_client, get_embedding

    try:
        client = get_chroma_client()
        client.heartbeat()
        print(f"Chroma connected, collection: {settings.chroma_collection}")
    except Exception as e:
        print(f"Warning: Chroma init failed: {e}")
        print("RAG retrieval will not work until Chroma is available.")

    # 预加载 embedding 模型，避免首次请求慢
    try:
        print("Pre-loading embedding model...")
        import time

        t0 = time.time()
        get_embedding("预热")
        print(f"Embedding model loaded in {time.time() - t0:.1f}s")
    except Exception as e:
        print(f"Warning: Embedding model init failed: {e}")

    yield

    cleaned = session_manager.cleanup_expired()
    print(f"Cleaned {cleaned} expired sessions")


# ──── FastAPI 应用 ────

app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──── 安全中间件 ────


@app.middleware("http")
async def security_middleware(request, call_next):
    from starlette.responses import JSONResponse
    from ratelimit import is_bot, ip_limiter

    client_ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    path = request.url.path

    # 白名单路径（不检查）
    if path in ("/health", "/api/token", "/"):
        return await call_next(request)

    # 1. 机器人检测
    is_bot_ua, matched = is_bot(ua)
    if is_bot_ua and path.startswith("/api/"):
        return JSONResponse({"error": "访问被拒绝"}, status_code=403)

    # 2. IP 速率限制（所有 API 路径）
    if path.startswith(("/api/", "/ws/")):
        ok, msg = ip_limiter.check(client_ip)
        if not ok:
            return JSONResponse({"error": msg}, status_code=429)

    # 3. 请求大小限制 (100KB)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 100_000:
        return JSONResponse({"error": "请求体过大"}, status_code=413)

    response = await call_next(request)
    return response


# ──── 启动时检查 .env 权限 ────


import os

_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    mode = os.stat(_env_path).st_mode
    # 检查是否其他用户可读 (group/other)
    if mode & 0o0044:
        print("⚠️  WARNING: .env 文件权限过于开放，建议执行: chmod 600 .env")


# ──── WebSocket: 流式对话（核心接口） ────


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    tenant = websocket.query_params.get("tenant", "finsight")
    session_id = websocket.query_params.get("session_id", None)

    await websocket.accept()

    session = session_manager.get_or_create(tenant, session_id)
    await websocket.send_json({"type": "connected", "session_id": session.session_id})

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") != "message":
                continue

            query = data.get("content", "").strip()
            if not query:
                continue

            session.add_message("user", query)

            async for event in rag_pipeline_stream(
                query=query,
                history=session.get_context(),
            ):
                await websocket.send_json(event)

                if event["type"] == "done":
                    session.add_message("assistant", event["content"])

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "code": "INTERNAL_ERROR",
                    "content": f"系统错误，请稍后重试：{str(e)}",
                }
            )
        except RuntimeError:
            pass


# ──── REST: 非流式对话 ────


class ChatRequest(BaseModel):
    content: str
    tenant: str = "finsight"
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    sources: list[dict] = []


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """非流式对话接口（备选）"""
    # 速率限制检查
    ok, reason = rate_limiter.check_query(request.content)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    session = session_manager.get_or_create(request.tenant, request.session_id)
    ok, reason = rate_limiter.check_session(session.session_id)
    if not ok:
        raise HTTPException(status_code=429, detail=reason)

    session.add_message("user", request.content)

    full_reply = ""
    sources = []

    try:
        async for event in rag_pipeline_stream(
            query=request.content,
            history=session.get_context(),
        ):
            if event["type"] == "token":
                full_reply += event["content"]
            elif event["type"] == "sources":
                sources = event["sources"]
            elif event["type"] == "error":
                full_reply = event["content"]

        session.add_message("assistant", full_reply)
        return ChatResponse(
            reply=full_reply, session_id=session.session_id, sources=sources
        )
    finally:
        tokens = len(full_reply) // 2
        rate_limiter.release(session.session_id, tokens)


# ──── SSE: 流式对话（主页面用） ────


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE 流式对话接口，用于前端逐 token 显示"""
    # 速率限制
    ok, reason = rate_limiter.check_query(request.content)
    if not ok:
        return StreamingResponse(_error_stream(reason), media_type="text/event-stream")

    session = session_manager.get_or_create(request.tenant, request.session_id)
    ok, reason = rate_limiter.check_session(session.session_id)
    if not ok:
        return StreamingResponse(_error_stream(reason), media_type="text/event-stream")

    session.add_message("user", request.content)

    async def event_generator():
        full_reply = ""
        try:
            async for event in rag_pipeline_stream(
                query=request.content,
                history=session.get_context(),
            ):
                if event["type"] == "token":
                    full_reply += event["content"]
                    yield f"data: {json.dumps({'type': 'token', 'content': event['content']})}\n\n"
                elif event["type"] == "status":
                    yield f"data: {json.dumps({'type': 'status', 'content': event['content']})}\n\n"
                elif event["type"] == "sources":
                    yield f"data: {json.dumps({'type': 'sources', 'sources': event['sources']})}\n\n"
                elif event["type"] == "done":
                    session.add_message("assistant", full_reply)
                    yield f"data: {json.dumps({'type': 'done', 'session_id': session.session_id})}\n\n"
                elif event["type"] == "error":
                    yield f"data: {json.dumps({'type': 'error', 'content': event['content']})}\n\n"
        finally:
            tokens = len(full_reply) // 2
            rate_limiter.release(session.session_id, tokens)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _error_stream(msg: str):
    """返回 SSE 格式的错误流"""
    import json

    yield f"data: {json.dumps({'type': 'error', 'content': msg})}\n\n"
    yield "data: [DONE]\n\n"


# ──── REST: 用户反馈 ────


class FeedbackRequest(BaseModel):
    session_id: str
    message_id: str
    rating: int  # 1 = 👍, 0 = 👎


class FeedbackResponse(BaseModel):
    status: str


@app.post("/api/feedback", response_model=FeedbackResponse)
async def feedback(request: FeedbackRequest):
    """用户反馈记录"""
    if request.rating not in (0, 1):
        raise HTTPException(status_code=400, detail="Rating must be 0 or 1")

    record = {
        "session_id": request.session_id,
        "message_id": request.message_id,
        "rating": request.rating,
        "timestamp": time.time(),
    }

    feedback_path = os.path.abspath(settings.feedback_path)
    os.makedirs(os.path.dirname(feedback_path) or ".", exist_ok=True)
    with open(feedback_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return FeedbackResponse(status="ok")


# ──── 健康检查 ────


@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": session_manager.active_count}


# ──── 页面 Token（防爬虫验证） ────


from ratelimit import generate_page_token


@app.get("/api/token")
async def get_page_token():
    """前端页面加载时获取验证 token"""
    return {"token": generate_page_token()}


# ──── 启动入口 ────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app", host=settings.host, port=settings.port, reload=settings.debug
    )

# FinSight AI — Implementation Design Document

**版本：** v1.0  
**日期：** 2026-06-25  
**状态：** Draft  
**作者：** Architect

---

## 目录

1. [设计总览与决策记录](#1-设计总览与决策记录)
2. [数据结构定义](#2-数据结构定义)
3. [后端详细设计](#3-后端详细设计)
4. [RAG Prompt 模板](#4-rag-prompt-模板)
5. [前端详细设计](#5-前端详细设计)
6. [Apple 风格 UI 设计规范](#6-apple-风格-ui-设计规范)

---

## 1. 设计总览与决策记录

### 1.1 决策确认清单

| 项目       | 决策                                     | 理由                                                              |
| ---------- | ---------------------------------------- | ----------------------------------------------------------------- |
| AI 名称    | **FinSight AI**                          | 品牌统一                                                          |
| 公司名称   | **FinSight 证券公司**                    | 项目归属                                                          |
| LLM        | **Claude API**（通过 DeepSeek Pro 代理） | DeepSeek Pro 提供 Claude 访问代理，无需直接申请 Anthropic API Key |
| Embedding  | **DeepSeek Embedding API**               | 已有 API Key，OpenAI 兼容协议，减少外部依赖                       |
| 向量数据库 | **Chroma**（本地文件数据库）             | MVP 演示无需云服务，零运维，零成本                                |
| 前端样式   | **Apple 风格**                           | 客户演示品质要求，简洁高端感                                      |
| 部署       | **Railway** / 客户服务器                 | 后续决定                                                          |

### 1.2 架构总览

```
┌── 用户浏览器 ──────────────────────────────────────────────┐
│  React 网站                                                  │
│   └─ <ChatWidget tenant="finsight" />                       │
│      ├─ WebSocket → wss://host/ws/chat                     │
│      ├─ 流式 Markdown 渲染                                   │
│      └─ Apple 风格 UI（毛玻璃、圆角、spring 动画）             │
└────────────────────────┬────────────────────────────────────┘
                         │ WSS
┌── 后端 FastAPI ────────▼────────────────────────────────────┐
│  ┌─ WS /ws/chat          (流式对话，核心接口)                  │
│  ├─ POST /api/chat       (非流式备选)                        │
│  ├─ POST /api/feedback   (用户反馈)                          │
│  └─ lifespan             (Chroma 客户端初始化/关闭)           │
│                                                              │
│  ┌──── RAG Pipeline ──────────────────────────────────────┐  │
│  │  用户 Query → DeepSeek Embedding → Chroma Top-5         │  │
│  │    → 拼 Prompt → Claude API (DeepSeek 代理) → 流式输出   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──── 存储层 ────────────────────────────────────────────┐  │
│  │  ├─ chroma_db/       向量数据库（本地持久化）             │  │
│  │  ├─ feedback.json    用户反馈                            │  │
│  │  └─ 内存 Sessions    ChatSession 字典（带锁）             │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 关键设计决策说明

| 决策                               | 说明                                                                                                                         |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Chroma 替代 Pinecone**           | MVP 演示阶段使用本地 Chroma 文件数据库。Pinecone 需云账号+网络，Chroma 零运维开箱即用。后期可迁移到 Pinecone/Qdrant/Milvus   |
| **DeepSeek Embedding 替代 OpenAI** | 客户已持有 DeepSeek API Key。DeepSeek Embedding API 兼容 OpenAI 协议，迁移成本为零                                           |
| **Claude API 通过 DeepSeek 代理**  | 通过 DeepSeek Pro 代理访问 Claude，需确认代理端点支持的 API 格式（设计同时支持 Anthropic SDK 和 OpenAI-compatible 两种模式） |
| **Apple 风格 UI**                  | 客户演示场景要求高视觉品质。Apple HIG 风格设计系统：SF Pro 字体栈、毛玻璃效果、弹簧动画、微妙阴影                            |
| **反馈存 JSON 文件**               | MVP 不需要数据库，JSON 文件追加写入即可。首天可能几 KB 数据量，后期可接入 Postgres/ClickHouse                                |
| **拒绝检测双保险**                 | 关键词预检（快速拒绝）+ System Prompt 规则（LLM 层兜底），确保不给投资建议                                                   |

---

## 2. 数据结构定义

### 2.1 WebSocket 消息协议

#### 客户端 -> 服务端

```typescript
// 发起对话消息
{
  "type": "message",
  "content": "用户的问题文本"
}
```

#### 服务端 -> 客户端

```typescript
// 连接确认（建立连接后首条消息）
{
  "type": "connected",
  "session_id": "uuid-string"
}

// 状态更新（展示思考过程）
{
  "type": "status",
  "content": "检索中..." | "生成回答中..."
}

// 流式 token（逐字推送）
{
  "type": "token",
  "content": "根"
}

// 引用来源（在 done 之前发送）
{
  "type": "sources",
  "sources": [
    {"title": "腾讯2024年度报告", "page": 23, "chunk": "盈利能力分析..."},
    {"title": "行业研究报告-科技板块", "page": 5, "chunk": "估值水平..."}
  ]
}

// 回答完成
{
  "type": "done",
  "content": "完整的回答文本",         // 完整回答（前端可直接使用）
  "sources": [{"title": "...", "page": 23}]  // 同 sources 消息
}

// 错误/拒绝
{
  "type": "error",
  "code": "REJECTED" | "RATE_LIMITED" | "CONTEXT_TOO_LONG" | "INTERNAL_ERROR",
  "content": "抱歉，我无法提供投资建议..."
}
```

**注意事项：**

- `status`、`token`、`sources`、`done` 四种消息按顺序推送：`status -> token* -> sources -> done`
- 错误场景下不会收到 `done`，直接推送 `error`
- `sources` 可能在 `done` 中重复发送，方便前端一次性处理

### 2.2 Chroma Collection Schema

```python
Collection: "finsight_docs"

字段说明：
- ids:       str               # 格式: "{source_filename}_{page}_{chunk_index}"
- embeddings: List[float]      # DeepSeek Embedding 输出的向量
- documents:  str              # 切块后的文本内容
- metadatas:  dict             # 元数据
  {
    "source":      str,        # 源文件名, e.g. "腾讯2024年报.pdf"
    "page":        int,        # 页码
    "chunk_index": int,        # 当前文档中的块序号
    "total_chunks": int,       # 当前文档的总块数
    "section":     str,        # 章节标题（如可用）
    "char_count":  int         # 块字符数
  }
```

**检索参数：**

```python
collection.query(
    query_embeddings=[vector],
    n_results=5,
    include=["documents", "metadatas", "distances"]
)
```

### 2.3 Session 存储结构

```python
# 内存数据结构
sessions: Dict[str, ChatSession] = {}
lock: threading.Lock

class ChatSession:
    session_id: str
    tenant_id: str
    history: List[Message]       # [{"role": "user"/"assistant", "content": str}]
    last_active: float           # time.time()
    created_at: float
    message_count: int           # 累计消息数（用于 message_id 生成）

class Message:
    role: str                    # "user" | "assistant"
    content: str
```

### 2.4 反馈数据存储结构

**文件：** `backend/feedback.jsonl`（JSON Lines 格式，每行一条记录）

```json
{
  "session_id": "uuid-string",
  "message_id": "msg-0003",
  "rating": 1,
  "query": "腾讯PE是多少",
  "response": "根据查询的资料...",
  "sources": [{ "title": "腾讯年报", "page": 23 }],
  "timestamp": 1719300000.0,
  "user_agent": "Mozilla/5.0..."
}
```

---

## 3. 后端详细设计

### 3.1 config.py — 配置管理

使用 `pydantic-settings` 管理所有配置项，支持 `.env` 文件加载和环境变量覆盖。

```python
# backend/config.py

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    # ──── 应用配置 ────
    app_name: str = "FinSight AI"
    debug: bool = False
    cors_origins: list[str] = ["*"]                     # MVP 阶段开放，后续收紧

    # ──── DeepSeek Proxy / Claude ────
    # DeepSeek Pro 代理 Claude API
    # 支持两种模式：
    #   模式A: anthropic_base_url 指向 DeepSeek 代理端点（推荐）
    #   模式B: openai_base_url 指向 DeepSeek 代理端点（OpenAI 兼容模式)
    llm_provider: str = "anthropic"                     # "anthropic" | "openai"
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_base_url: Optional[str] = Field(default=None, alias="ANTHROPIC_BASE_URL")
    # 如通过 OpenAI 兼容方式代理
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(default=None, alias="OPENAI_BASE_URL")
    claude_model: str = "claude-sonnet-4-20250514"      # 实际模型名依代理配置

    # ──── DeepSeek Embedding ────
    # DeepSeek Embedding API (OpenAI 兼容协议)
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        alias="DEEPSEEK_BASE_URL"
    )
    embedding_model: str = "deepseek-embedding"         # DeepSeek embedding 模型名
    embedding_dimensions: int = 1024                    # deepseek-embedding 输出维度

    # ──── Chroma ────
    chroma_persist_dir: str = "chroma_db"               # Chroma 持久化目录
    chroma_collection: str = "finsight_docs"            # 集合名
    retrieval_top_k: int = 5                            # 检索 Top-K

    # ──── Session ────
    session_timeout: int = 600                          # 10 分钟超时（秒）
    session_max_rounds: int = 3                         # 保留最近 3 轮对话

    # ──── RAG ────
    max_context_chars: int = 8000                       # 上下文最大字符数
    max_tokens: int = 4096                              # 生成最大 token 数

    # ──── Ingest ────
    chunk_min_chars: int = 100                          # 最小块字符数
    chunk_max_chars: int = 1500                         # 最大块字符数

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }

settings = Settings()  # 全局单例
```

**设计决策说明：**

- 使用 `pydantic-settings` 而非 `os.getenv`：类型安全、支持 `.env`、支持别名
- 同时保留 `OPENAI_API_KEY` 和 `ANTHROPIC_API_KEY`：支持两种代理模式切换
- 所有路径使用相对路径（相对于 `backend/`），Chroma 数据库文件在 `backend/chroma_db/`

### 3.2 session.py — 会话管理

```python
# backend/session.py

import time
import uuid
import threading
from typing import Optional
from config import settings

class ChatSession:
    """单个对话会话"""

    def __init__(self, tenant_id: str, session_id: Optional[str] = None):
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.tenant_id = tenant_id
        self.history: list[dict] = []  # [{"role": "user"/"assistant", "content": str}]
        self.last_active = time.time()
        self.created_at = time.time()
        self.message_count = 0

    def add_message(self, role: str, content: str) -> int:
        """添加一条消息，返回消息序号"""
        self.history.append({"role": role, "content": content})
        self.last_active = time.time()
        self.message_count += 1
        return self.message_count

    def get_context(self) -> list[dict]:
        """返回用于 prompt 的上下文历史（最近 N 轮）"""
        max_messages = settings.session_max_rounds * 2  # user + assistant per round
        # 排除当前正在等回复的最新 user 消息
        context = self.history[:-1] if self.history and self.history[-1]["role"] == "user" else self.history
        return context[-max_messages:]

    def is_expired(self) -> bool:
        """检查是否超过 10 分钟无活动"""
        return time.time() - self.last_active > settings.session_timeout

    def clear(self):
        """清空历史"""
        self.history.clear()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "message_count": self.message_count,
            "last_active": self.last_active
        }


class SessionManager:
    """线程安全的全局 Session 管理器"""

    def __init__(self):
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.Lock()

    def get_or_create(self, tenant_id: str, session_id: str | None = None) -> ChatSession:
        with self._lock:
            if session_id and session_id in self._sessions:
                session = self._sessions[session_id]
                if session.is_expired():
                    session.clear()
                return session
            # 创建新 session
            session = ChatSession(tenant_id=tenant_id, session_id=session_id)
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> ChatSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.is_expired():
                session.clear()
                return None  # 过期视为不存在，前端应重连
            return session

    def remove(self, session_id: str):
        with self._lock:
            self._sessions.pop(session_id, None)

    def cleanup_expired(self):
        """清理过期 session（可定时调用）"""
        now = time.time()
        with self._lock:
            expired = [
                sid for sid, s in self._sessions.items()
                if now - s.last_active > settings.session_timeout
            ]
            for sid in expired:
                del self._sessions[sid]
            return len(expired)

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._sessions)

# 全局单例
session_manager = SessionManager()
```

**设计决策说明：**

- `threading.Lock` 保证线程安全（Uvicorn 多 worker 场景下需注意，MVP 单进程单 worker 足够）
- `get_or_create` 中过期 session 不清除只清空 history：保持 session 连接，用户在 10 分钟后说话表现为"新对话"而非"断开"
- `cleanup_expired` 可供后台定时任务调用，防止内存泄漏

### 3.3 rag.py — RAG 流水线

RAG 核心流水线，包含检索、Prompt 构建、LLM 调用。

```python
# backend/rag.py

import json
import re
from typing import AsyncGenerator, Optional
import httpx

from config import settings

# ──── 拒绝检测 ────

# 投资建议关键词
INVESTMENT_ADVICE_PATTERNS = [
    r"(买|卖|建仓|清仓|加仓|减仓|抄底|逃顶|追涨|杀跌)",
    r"(涨|跌|走势|目标价|预测|看[好多空涨跌]|看空)",
    r"(推荐|建议).*(股票|基金|产品|组合)",
    r"(能不能|是否).*(买|投资|入手)",
    r"\d{6}.*(买|卖|如何)",  # 股票代码 + 买卖
]

# 无关话题关键词
OFF_TOPIC_PATTERNS = [
    r"(天气|娱乐|八卦|明星|游戏|电影|电视剧)",
]


def check_rejection(query: str) -> Optional[dict]:
    """
    拒绝检测前置过滤器。
    返回 None 表示通过，返回 dict 表示命中拒绝规则。
    """
    for pattern in INVESTMENT_ADVICE_PATTERNS:
        if re.search(pattern, query):
            return {
                "code": "REJECTED",
                "reason": "investment_advice",
                "message": "抱歉，我是 FinSight 证券公司的智能金融助手，无法提供投资建议或股价预测。"
                           "建议您咨询专业的投资顾问，或查阅公司官网的公开信息。"
            }
    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, query):
            return {
                "code": "REJECTED",
                "reason": "off_topic",
                "message": "抱歉，我仅能回答与 FinSight 证券公司业务及金融知识相关的问题。"
                           "请提出与公司产品或金融相关的问题。"
            }
    return None


# ──── Embedding ────

def get_embedding(text: str) -> list[float]:
    """
    调用 DeepSeek Embedding API 获取文本向量。
    API 兼容 OpenAI 协议。
    """
    response = httpx.post(
        f"{settings.deepseek_base_url}/embeddings",
        headers={
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": settings.embedding_model,
            "input": text
        }
    )
    response.raise_for_status()
    data = response.json()
    return data["data"][0]["embedding"]


# ──── Chroma 检索 ────

_chroma_client = None  # 延迟初始化，由 main.py lifespan 管理


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir
        )
    return _chroma_client


def get_chroma_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection
    )


def retrieve(query: str, top_k: int = None) -> list[dict]:
    """
    检索相似文档块。
    返回格式：[{"title": str, "page": int, "content": str, "score": float}, ...]
    """
    k = top_k or settings.retrieval_top_k
    query_vector = get_embedding(query)
    collection = get_chroma_collection()

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=k,
        include=["documents", "metadatas", "distances"]
    )

    docs = []
    if results["documents"] and results["documents"][0]:
        for i, doc_text in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            docs.append({
                "title": meta.get("source", "未知来源"),
                "page": meta.get("page", 0),
                "content": doc_text,
                "score": 1.0 - distance  # 转为相似度（越大越相似）
            })
    return docs


# ──── LLM 调用 ────

def _get_anthropic_client():
    """获取 Anthropic SDK 客户端（DeepSeek 代理模式）"""
    import anthropic
    kwargs = {"api_key": settings.anthropic_api_key}
    if settings.anthropic_base_url:
        kwargs["base_url"] = settings.anthropic_base_url
    return anthropic.AsyncAnthropic(**kwargs)


async def stream_llm(
    system_prompt: str,
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """
    流式调用 Claude API（通过 DeepSeek 代理）。
    返回 token 生成器。
    """
    client = _get_anthropic_client()

    async with client.messages.stream(
        model=settings.claude_model,
        system=system_prompt,
        messages=messages,
        max_tokens=settings.max_tokens,
    ) as stream:
        async for text in stream.text_stream:
            yield text


# ──── Prompt 构建 ────

SYSTEM_PROMPT_TPL = """你是 {company_name} 的智能金融助手，名称是 "{ai_name}"。

## 你的身份
- 你是 {company_name} 官方服务的 AI 助手
- 你的回答仅基于以下"参考资料"中的内容
- 你使用中文回答，风格专业、简洁、友好

## 回答规则
1. 始终基于"参考资料"中的内容回答，**不要编造信息**
2. 如果参考资料中没有相关信息，明确告知用户你不知道
3. 如果用户问到投资建议、股价预测，礼貌拒绝并说明无法提供
4. 回答中引用来源时，标注 [1]、[2] 等编号，结尾列出对应来源名称和页码
5. 使用 Markdown 格式，适当使用标题、列表、表格使回答更清晰
6. 不回答与 {company_name} 业务和金融知识无关的问题

## 参考资料
{context}
"""

HISTORY_TPL = """## 历史对话
{history_text}"""

USER_QUERY_TPL = """## 当前问题
用户：{query}
助手："""


def build_rag_prompt(
    query: str,
    retrieved_docs: list[dict],
    history: list[dict],
    company_name: str = "FinSight 证券公司",
    ai_name: str = "FinSight AI",
) -> tuple[str, list[dict]]:
    """
    构建 RAG Prompt。
    返回 (system_prompt, messages) 元组。
    """
    # 构建上下文文本
    context_parts = []
    for i, doc in enumerate(retrieved_docs, 1):
        if doc["content"]:
            context_parts.append(
                f"[{i}] 来源：{doc['title']}（第 {doc['page']} 页）\n{doc['content']}\n"
            )
    context_text = "\n".join(context_parts) if context_parts else "（无相关参考资料）"

    # 构建 System Prompt
    system_prompt = SYSTEM_PROMPT_TPL.format(
        company_name=company_name,
        ai_name=ai_name,
        context=context_text
    )

    # 构建消息列表（含历史）
    messages = list(history) if history else []
    messages.append({"role": "user", "content": query})

    # 如果上下文总字符超限，截断历史
    total_chars = len(system_prompt) + sum(
        len(m["content"]) for m in messages
    )
    while total_chars > settings.max_context_chars and len(messages) > 1:
        removed = messages.pop(0)
        total_chars -= len(removed["content"])

    return system_prompt, messages


# ──── 主入口 ────

async def rag_pipeline_stream(
    query: str,
    history: list[dict],
    company_name: str = "FinSight 证券公司",
    ai_name: str = "FinSight AI",
) -> AsyncGenerator[dict, None]:
    """
    RAG 流水线主入口（流式版本）。
    每次 yield 一个 dict：
      {"type": "status", "content": "..."}
      {"type": "token", "content": "..."}
      {"type": "sources", "sources": [...]}
      {"type": "done", "content": "...", "sources": [...]}
      {"type": "error", "code": "...", "content": "..."}
    """

    # 1. 拒绝检测
    rejection = check_rejection(query)
    if rejection:
        yield {"type": "error", "code": rejection["code"], "content": rejection["message"]}
        return

    # 2. 检索
    yield {"type": "status", "content": "检索知识库中..."}
    try:
        docs = retrieve(query)
    except Exception as e:
        yield {"type": "error", "code": "RETRIEVAL_FAILED", "content": f"检索失败：{str(e)}"}
        return

    # 3. 构建 Prompt
    yield {"type": "status", "content": "生成回答中..."}
    system_prompt, messages = build_rag_prompt(query, docs, history)

    # 4. 流式调用 LLM
    full_response = ""
    try:
        async for token in stream_llm(system_prompt, messages):
            full_response += token
            yield {"type": "token", "content": token}
    except Exception as e:
        yield {"type": "error", "code": "LLM_ERROR", "content": f"生成回答失败：{str(e)}"}
        return

    # 5. 返回来源和完成信号
    sources = [
        {"title": d["title"], "page": d["page"]}
        for d in docs
        if d["score"] > 0.3  # 低分来源不展示
    ]
    yield {"type": "sources", "sources": sources}
    yield {"type": "done", "content": full_response, "sources": sources}
```

**设计决策说明：**

1. **拒绝检测双保险**：关键词预检（`check_rejection`）在调用 LLM 前快速拦截明确违规问题，System Prompt 中的规则作为第二道防线兜底。

2. **DeepSeek Embedding 调用**：使用 `httpx` 直接调用 DeepSeek API（兼容 OpenAI 协议），避免引入 `openai` 包仅用于 Embedding。如果需要，可改为 `openai` SDK。

3. **Chroma 延迟初始化**：通过 `get_chroma_client()` 实现延迟加载，由 `main.py` 的 lifespan 管理生命周期，避免模块导入时即创建连接。

4. **截断策略**：当上下文超限时，从最早的历史消息开始移除（FIFO），保留最新的对话和历史。

5. **来源过滤**：相似度分数低于 0.3 的文档块不展示给用户，避免展示不相关或弱相关的来源。

### 3.4 ingest.py — 文档入库脚本

```python
# backend/ingest.py

"""
离线文档处理脚本。
用法：
    python ingest.py path/to/doc.pdf
    python ingest.py path/to/dir/        # 批量处理目录下所有 PDF
    python ingest.py --recreate          # 清空 Chroma 集合重新入库
"""

import os
import sys
import uuid
import argparse
import fitz  # PyMuPDF

from config import settings
from rag import get_embedding, get_chroma_collection


def extract_text_from_pdf(filepath: str) -> list[dict]:
    """
    使用 PyMuPDF 解析 PDF，返回段落列表。
    返回：[{"page": int, "text": str, "section": str}, ...]
    """
    doc = fitz.open(filepath)
    paragraphs = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("blocks")
        for block in blocks:
            text = block[4].strip()
            if len(text) < settings.chunk_min_chars:
                # 过短的文本跳过或合并
                continue
            paragraphs.append({
                "page": page_num + 1,
                "text": text,
                "section": _detect_section(text)
            })

    doc.close()
    return paragraphs


def _detect_section(text: str) -> str:
    """简单检测章节标题"""
    lines = text.strip().split("\n")
    for line in lines[:3]:
        line = line.strip()
        # 匹配 "第X章" "X." "一、" 等标题模式
        if re.match(r"^第[一二三四五六七八九十百千]+[章节条]", line):
            return line[:30]
        if re.match(r"^[0-9]+(\.[0-9]+)*\s+", line):
            return line[:30]
        if re.match(r"^[一二三四五六七八九十]、", line):
            return line[:30]
    return ""


def chunk_document(
    paragraphs: list[dict],
    source: str
) -> list[dict]:
    """
    递归切块：短段落合并，长段落拆分。
    返回 [{"text": str, "source": str, "page": int, ...}, ...]
    """
    chunks = []
    buffer = ""
    buffer_pages = set()
    chunk_index = 0

    for para in paragraphs:
        # 如果当前段落本身超过 max_chars，直接作为一个块
        if len(para["text"]) > settings.chunk_max_chars:
            # 先 flush buffer
            if buffer:
                chunks.append({
                    "text": buffer.strip(),
                    "source": source,
                    "page": min(buffer_pages),
                    "section": "",
                    "chunk_index": chunk_index
                })
                chunk_index += 1
                buffer = ""
                buffer_pages = set()
            # 大段落再拆分（按句号或换行）
            chunks.extend(_split_long_paragraph(para, source, chunk_index))
            chunk_index = len(chunks)
            continue

        # 合并后是否超限
        if buffer and len(buffer) + len(para["text"]) > settings.chunk_max_chars:
            chunks.append({
                "text": buffer.strip(),
                "source": source,
                "page": min(buffer_pages),
                "section": "",
                "chunk_index": chunk_index
            })
            chunk_index += 1
            buffer = ""
            buffer_pages = set()

        buffer += para["text"] + "\n"
        buffer_pages.add(para["page"])

    # 最后一段
    if buffer:
        chunks.append({
            "text": buffer.strip(),
            "source": source,
            "page": min(buffer_pages),
            "section": "",
            "chunk_index": chunk_index
        })

    return chunks


def _split_long_paragraph(para: dict, source: str, start_index: int) -> list[dict]:
    """按句子拆分超长段落"""
    import re
    chunks = []
    sentences = re.split(r"(?<=[。！？\n])", para["text"])
    buffer = ""
    idx = start_index

    for sent in sentences:
        if not sent.strip():
            continue
        if len(buffer) + len(sent) > settings.chunk_max_chars:
            if buffer:
                chunks.append({
                    "text": buffer.strip(),
                    "source": source,
                    "page": para["page"],
                    "section": para.get("section", ""),
                    "chunk_index": idx
                })
                idx += 1
            buffer = sent
        else:
            buffer += sent

    if buffer:
        chunks.append({
            "text": buffer.strip(),
            "source": source,
            "page": para["page"],
            "section": para.get("section", ""),
            "chunk_index": idx
        })

    return chunks


def process_file(filepath: str, collection) -> int:
    """处理单个 PDF 文件，返回入库块数"""
    filename = os.path.basename(filepath)
    print(f"  Processing: {filename}")

    paragraphs = extract_text_from_pdf(filepath)
    print(f"  Extracted {len(paragraphs)} paragraphs")

    chunks = chunk_document(paragraphs, filename)
    print(f"  Generated {len(chunks)} chunks")

    # 批量写入 Chroma
    ids = []
    embeddings = []
    documents = []
    metadatas = []

    for chunk in chunks:
        chunk_id = f"{filename}_{chunk['page']}_{chunk['chunk_index']}"
        ids.append(chunk_id)
        documents.append(chunk["text"])
        metadatas.append({
            "source": chunk["source"],
            "page": chunk["page"],
            "chunk_index": chunk["chunk_index"],
            "total_chunks": len(chunks),
            "section": chunk.get("section", ""),
            "char_count": len(chunk["text"])
        })

    # 批量 Embedding
    print(f"  Computing embeddings ({len(chunks)} chunks)...")
    for i, text in enumerate(documents):
        emb = get_embedding(text)
        embeddings.append(emb)
        if (i + 1) % 10 == 0:
            print(f"    {i + 1}/{len(chunks)}")

    # 写入
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    print(f"  Done: {len(chunks)} chunks indexed")
    return len(chunks)


def main():
    parser = argparse.ArgumentParser(description="FinSight AI 文档入库工具")
    parser.add_argument("path", help="PDF 文件路径或目录路径")
    parser.add_argument("--recreate", action="store_true", help="重建 Chroma 集合")
    args = parser.parse_args()

    # 获取 Chroma collection
    collection = get_chroma_collection()

    if args.recreate:
        print("Recreating collection...")
        client = get_chroma_client()
        client.delete_collection(settings.chroma_collection)
        collection = get_chroma_collection()

    # 收集文件
    if os.path.isfile(args.path):
        files = [args.path]
    elif os.path.isdir(args.path):
        files = [
            os.path.join(args.path, f)
            for f in os.listdir(args.path)
            if f.lower().endswith(".pdf")
        ]
    else:
        print(f"Error: {args.path} not found")
        sys.exit(1)

    total = 0
    for fp in files:
        try:
            total += process_file(fp, collection)
        except Exception as e:
            print(f"  Error processing {fp}: {e}")

    print(f"\nTotal: {total} chunks indexed from {len(files)} files")


if __name__ == "__main__":
    main()
```

**设计决策说明：**

- **递归切块策略**：短段落自动合并至 `chunk_max_chars`（1500 字符），超长段落按句号/换行拆分，保证每个块的语义完整性
- **批量 Embedding**：每 10 个块打印一次进度，便于监控大文档处理进度
- **Chroma 批量写入**：`collection.add()` 一次写入所有块，比逐条写入快一个数量级
- **`--recreate` 参数**：方便重新构建索引（文档更新需要重建）
- **Chunk ID 格式**：`{filename}_{page}_{chunk_index}`，便于溯源

### 3.5 main.py — FastAPI 入口

```python
# backend/main.py

import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from session import session_manager
from rag import rag_pipeline_stream

# ──── Lifespan ────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：初始化 Chroma（验证可达）
    from rag import get_chroma_client
    try:
        client = get_chroma_client()
        client.heartbeat()  # 验证可连接
        print(f"Chroma connected, collection: {settings.chroma_collection}")
    except Exception as e:
        print(f"Warning: Chroma init failed: {e}")
        print("RAG retrieval will not work until Chroma is available.")

    yield

    # 关闭时：清理过期 session
    cleaned = session_manager.cleanup_expired()
    print(f"Cleaned {cleaned} expired sessions")


# ──── FastAPI 应用 ────

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan
)

# CORS（允许前端嵌入）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──── WebSocket: 流式对话（核心接口） ────

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    tenant = websocket.query_params.get("tenant", "finsight")
    session_id = websocket.query_params.get("session_id", None)

    await websocket.accept()

    # 获取/创建 session
    session = session_manager.get_or_create(tenant, session_id)
    await websocket.send_json({
        "type": "connected",
        "session_id": session.session_id
    })

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") != "message":
                continue

            query = data.get("content", "").strip()
            if not query:
                continue

            # 记录用户消息
            session.add_message("user", query)

            # 执行 RAG 流水线
            async for event in rag_pipeline_stream(
                query=query,
                history=session.get_context(),
            ):
                # 发送事件到客户端
                await websocket.send_json(event)

                # 如果是 done，记录回答到历史
                if event["type"] == "done":
                    session.add_message("assistant", event["content"])

                # 如果是 error，也要处理
                if event["type"] == "error":
                    # 错误不记录到历史
                    pass

    except WebSocketDisconnect:
        pass  # 客户端断开，session 保留直到超时
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "code": "INTERNAL_ERROR",
                "content": f"系统错误，请稍后重试：{str(e)}"
            })
        except RuntimeError:
            pass  # WebSocket 可能已关闭


# ──── REST: 非流式对话 ────

class ChatRequest(BaseModel):
    content: str
    tenant: str = "finsight"
    session_id: str | None = None

class ChatResponse(BaseModel):
    reply: str
    session_id: str
    sources: list[dict] = []


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """非流式对话接口（备选）"""
    session = session_manager.get_or_create(request.tenant, request.session_id)
    session.add_message("user", request.content)

    full_reply = ""
    sources = []

    async for event in rag_pipeline_stream(
        query=request.content,
        history=session.get_context(),
    ):
        if event["type"] == "token":
            full_reply += event["content"]
        elif event["type"] == "sources":
            sources = event["sources"]
        elif event["type"] == "error":
            raise HTTPException(status_code=400, detail=event["content"])

    session.add_message("assistant", full_reply)

    return ChatResponse(
        reply=full_reply,
        session_id=session.session_id,
        sources=sources
    )


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
    import json
    import os

    if request.rating not in (0, 1):
        raise HTTPException(status_code=400, detail="Rating must be 0 or 1")

    record = {
        "session_id": request.session_id,
        "message_id": request.message_id,
        "rating": request.rating,
        "timestamp": __import__("time").time()
    }

    feedback_file = "feedback.jsonl"
    with open(feedback_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return FeedbackResponse(status="ok")


# ──── 健康检查 ────

@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": session_manager.active_count}


# ──── 启动入口 ────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
```

**设计决策说明：**

1. **WebSocket 生命周期管理**：
   - `tenant` 和 `session_id` 通过 query params 传入
   - session 由服务端管理，客户端断开后保留直到超时（10分钟）
   - 同一 session_id 重连后恢复历史上下文

2. **错误处理策略**：
   - `WebSocketDisconnect` 静默处理（正常断开）
   - 其他异常尝试发 error 消息，若连接已关闭则静默忽略
   - REST API 使用标准 HTTPException

3. **Lifespan 事件**：
   - 启动时验证 Chroma 连通性（警告而非崩溃）
   - 关闭时清理过期 session

4. **CORS 宽放**：MVP 阶段允许所有来源，上线前须收紧

### 3.6 requirements.txt — 依赖清单

```txt
# ──── Web 框架 ────
fastapi>=0.115.0,<1.0.0
uvicorn[standard]>=0.32.0,<1.0.0
pydantic>=2.0.0,<3.0.0
pydantic-settings>=2.0.0,<3.0.0
python-multipart>=0.0.12,<1.0.0

# ──── LLM ────
anthropic>=0.40.0,<1.0.0

# ──── 向量数据库 ────
chromadb>=0.5.0,<1.0.0

# ──── HTTP 客户端 ────
httpx>=0.27.0,<1.0.0

# ──── 文档解析 ────
PyMuPDF>=1.24.0,<2.0.0
```

**版本锁定说明：**

- 使用 `>=x,<x+1` 范围锁定大版本，避免 breaking changes 破坏 MVP
- `anthropic` SDK 用于 Claude API 流式调用
- `httpx` 用于 DeepSeek Embedding API 调用
- `chromadb` 本地持久化向量库

---

## 4. RAG Prompt 模板

### 4.1 System Prompt 模板

```
你是 {company_name} 的智能金融助手，名称是 "{ai_name}"。

## 你的身份
- 你是 {company_name} 官方服务的 AI 助手
- 你的回答仅基于以下"参考资料"中的内容
- 你使用中文回答，风格专业、简洁、友好

## 回答规则
1. 始终基于"参考资料"中的内容回答，**不要编造信息**
2. 如果参考资料中没有相关信息，明确告知用户你不知道
3. 如果用户问到投资建议、股价预测，礼貌拒绝并说明无法提供
4. 回答中引用来源时，标注 [1]、[2] 等编号，结尾列出对应来源名称和页码
5. 使用 Markdown 格式，适当使用标题、列表、表格使回答更清晰
6. 不回答与 {company_name} 业务和金融知识无关的问题

## 参考资料
[1] 来源：腾讯2024年度报告（第 23 页）
腾讯2024年营业收入为 6,600 亿元，同比增长 8%...
[2] 来源：行业研究报告-科技板块（第 5 页）
当前科技板块平均 PE 为 28 倍...

## 历史对话
用户：你好
助手：你好！我是 FinSight AI，FinSight 证券公司的智能金融助手。有什么可以帮助您的？

## 当前问题
用户：腾讯的PE是多少？
助手：
```

### 4.2 拒绝检测策略

**第一层：关键词预检（`check_rejection`）**

在调用 LLM 之前，使用正则表达式检测以下模式：

| 类别          | 检测规则                   | 示例             |
| ------------- | -------------------------- | ---------------- |
| 投资建议      | `(买/卖/建仓/清仓)`        | "这只股票能买吗" |
| 股价预测      | `(涨/跌/走势/目标价)`      | "明天会涨吗"     |
| 推荐请求      | `(推荐/建议).*(股票/基金)` | "推荐个基金"     |
| 股票代码+操作 | `\d{6}.*(买/卖)`           | "600519 能买吗"  |
| 无关话题      | `(天气/娱乐/八卦)`         | "今天天气怎么样" |

命中后直接返回拒绝消息，不消耗 Claude API Token。

**第二层：System Prompt 规则**

即使关键词预检未命中，System Prompt 中的规则 3 和规则 6 也会引导 Claude 在 LLM 层面拒绝回答。

### 4.3 历史截断策略

```
如果 总上下文字符 > max_context_chars（默认 8000）：
    从最早的消息开始移除，直到满足大小限制
    至少保留当前 query
```

反例演示：

- 如果历史有 10 轮对话，但上下文超长了
- 策略：从第 1 轮开始移除，保留最新的对话
- 最少保留 1 轮（当前 query）

---

## 5. 前端详细设计

### 5.1 types.ts — 类型定义

```typescript
// widget/src/types.ts

// ──── WebSocket 消息类型 ────

/** 客户端 -> 服务端消息 */
export interface WSClientMessage {
  type: "message";
  content: string;
}

/** 服务端 -> 客户端消息（联合类型） */
export type WSServerMessage =
  | WSConnected
  | WSStatus
  | WSToken
  | WSSources
  | WSDone
  | WSError;

export interface WSConnected {
  type: "connected";
  session_id: string;
}

export interface WSStatus {
  type: "status";
  content: string;
}

export interface WSToken {
  type: "token";
  content: string;
}

export interface WSSource {
  title: string;
  page?: number;
  chunk?: string;
}

export interface WSSources {
  type: "sources";
  sources: WSSource[];
}

export interface WSDone {
  type: "done";
  content: string;
  sources: WSSource[];
}

export interface WSError {
  type: "error";
  code: string;
  content: string;
}

// ──── 内部状态类型 ────

export type MessageRole = "user" | "assistant" | "system" | "error";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  sources?: WSSource[];
  timestamp: number;
  /** 是否正在流式接收中 */
  streaming?: boolean;
}

export type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting";

export interface ChatWidgetConfig {
  tenant: string;
  apiUrl: string;
  companyName: string;
  aiName: string;
  /** 可选：自定义欢迎语 */
  welcomeMessage?: string;
}

// ──── 组件 Props ────

export interface ChatWidgetProps {
  tenant?: string;
  apiUrl?: string;
  companyName?: string;
  aiName?: string;
  /** 自定义样式 */
  position?: "bottom-right" | "bottom-left";
  /** 初始展开 */
  defaultOpen?: boolean;
}

export interface FeedbackData {
  session_id: string;
  message_id: string;
  rating: 1 | 0;
}
```

### 5.2 ChatWidget.tsx — 主入口组件

```tsx
// widget/src/ChatWidget.tsx

/**
 * ChatWidget: 主入口组件
 *
 * 一行代码嵌入 React 网站：
 *   <ChatWidget tenant="finsight" apiUrl="wss://api.example.com" />
 *
 * 功能：
 * - 右下角固定浮窗
 * - 展开/收起动画（spring）
 * - 通过 props 配置 tenant、apiUrl、branding
 */

import React, { useState, useCallback } from "react";
import { ChatPanel } from "./ChatPanel";
import type { ChatWidgetProps } from "./types";

const DEFAULT_CONFIG = {
  tenant: "finsight",
  apiUrl: "ws://localhost:8000",
  companyName: "FinSight 证券公司",
  aiName: "FinSight AI",
};

export const ChatWidget: React.FC<ChatWidgetProps> = ({
  tenant = DEFAULT_CONFIG.tenant,
  apiUrl = DEFAULT_CONFIG.apiUrl,
  companyName = DEFAULT_CONFIG.companyName,
  aiName = DEFAULT_CONFIG.aiName,
  position = "bottom-right",
  defaultOpen = false,
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  const toggle = useCallback(() => {
    setIsOpen((prev) => !prev);
  }, []);

  const positionStyle: React.CSSProperties =
    position === "bottom-left"
      ? { bottom: 24, left: 24 }
      : { bottom: 24, right: 24 };

  return (
    <div style={{ position: "fixed", zIndex: 9999, ...positionStyle }}>
      {/* 触发按钮：圆形蓝色按钮，AI 图标 */}
      <button
        onClick={toggle}
        aria-label={isOpen ? "关闭对话" : "打开对话"}
        style={{
          width: 56,
          height: 56,
          borderRadius: "50%",
          border: "none",
          background: "linear-gradient(135deg, #0052CC, #007AFF)",
          color: "#fff",
          fontSize: 24,
          cursor: "pointer",
          boxShadow: "0 4px 16px rgba(0, 82, 204, 0.3)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "transform 0.2s ease",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = "scale(1.05)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = "scale(1)";
        }}
      >
        {/* Sparkles / AI icon */}
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M12 2l2 7h7l-5.5 4 2 7L12 16l-5.5 4 2-7L3 9h7z" />
        </svg>
      </button>

      {/* 展开面板 */}
      {isOpen && (
        <ChatPanel
          config={{ tenant, apiUrl, companyName, aiName }}
          onClose={toggle}
        />
      )}
    </div>
  );
};
```

**设计要点：**

- 通过 `position` prop 支持左右两种位置
- 按钮使用蓝色渐变背景 + 星形 SVG 图标
- hover 1.05x 放大效果（类似 Apple 交互）
- z-index: 9999 确保浮窗在最上层

### 5.3 ChatPanel.tsx — 对话面板

```tsx
// widget/src/ChatPanel.tsx

/**
 * ChatPanel: 对话框面板
 *
 * 职责：
 * - 渲染 Header（品牌名 + 关闭按钮）
 * - 管理 WebSocket 连接
 * - 渲染消息列表和输入框
 * - 处理重连和超时
 */

import React, { useState, useRef, useEffect, useCallback } from "react";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import type {
  ChatMessage,
  ChatWidgetConfig,
  ConnectionStatus,
  WSServerMessage,
} from "./types";

interface ChatPanelProps {
  config: ChatWidgetConfig;
  onClose: () => void;
}

const RECONNECT_DELAY = 3000;
const MAX_RECONNECT_ATTEMPTS = 5;

export const ChatPanel: React.FC<ChatPanelProps> = ({ config, onClose }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const sessionIdRef = useRef<string>("");
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();

  // ──── 建立 WebSocket 连接 ────
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setConnectionStatus("connecting");

    const wsUrl = `${config.apiUrl.replace(/^http/, "ws")}/ws/chat?tenant=${config.tenant}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionStatus("connected");
      reconnectCountRef.current = 0;
    };

    ws.onmessage = (event) => {
      const data: WSServerMessage = JSON.parse(event.data);

      switch (data.type) {
        case "connected":
          sessionIdRef.current = data.session_id;
          // 添加欢迎消息
          setMessages((prev) => [
            {
              id: "welcome",
              role: "system",
              content: `您好！我是 ${config.aiName}，${config.companyName} 的智能金融助手。我可以为您解答关于公司业务、金融知识等问题。请注意，我无法提供投资建议或股价预测。`,
              timestamp: Date.now(),
            },
            ...prev,
          ]);
          break;

        case "status":
          // 可展示状态（如"检索中..."）
          break;

        case "token": {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant" && last.streaming) {
              // 追加到最后一个助手消息
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...last,
                content: last.content + data.content,
              };
              return updated;
            } else {
              // 新建助手消息
              return [
                ...prev,
                {
                  id: `msg-${Date.now()}`,
                  role: "assistant",
                  content: data.content,
                  streaming: true,
                  timestamp: Date.now(),
                },
              ];
            }
          });
          break;
        }

        case "sources":
          // 保存来源到最后一条助手消息
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last?.role === "assistant") {
              updated[updated.length - 1] = { ...last, sources: data.sources };
            }
            return updated;
          });
          break;

        case "done":
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last?.role === "assistant") {
              updated[updated.length - 1] = {
                ...last,
                streaming: false,
                sources: data.sources || last.sources,
              };
            }
            return updated;
          });
          break;

        case "error":
          setMessages((prev) => [
            ...prev,
            {
              id: `error-${Date.now()}`,
              role: "error",
              content: data.content,
              timestamp: Date.now(),
            },
          ]);
          break;
      }
    };

    ws.onclose = () => {
      setConnectionStatus("disconnected");
      wsRef.current = null;

      // 自动重连
      if (reconnectCountRef.current < MAX_RECONNECT_ATTEMPTS) {
        setConnectionStatus("reconnecting");
        reconnectCountRef.current += 1;
        reconnectTimerRef.current = setTimeout(
          connect,
          RECONNECT_DELAY * reconnectCountRef.current,
        );
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [config]);

  // ──── 发送消息 ────
  const handleSend = useCallback((content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    // 添加用户消息
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        role: "user",
        content,
        timestamp: Date.now(),
      },
    ]);

    // 发送到服务端
    wsRef.current.send(JSON.stringify({ type: "message", content }));
  }, []);

  // ──── 生命周期 ────
  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  // ──── 渲染 ────
  return (
    <div
      style={{
        position: "absolute",
        bottom: 72,
        right: 0,
        width: 380,
        height: 600,
        borderRadius: 12,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        background: "rgba(255, 255, 255, 0.85)",
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.12)",
        border: "1px solid rgba(255, 255, 255, 0.3)",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "16px 20px",
          borderBottom: "1px solid rgba(0, 0, 0, 0.06)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          background: "rgba(255, 255, 255, 0.6)",
        }}
      >
        <div>
          <div style={{ fontWeight: 600, fontSize: 16, color: "#1D1D1F" }}>
            {config.aiName}
          </div>
          <div style={{ fontSize: 12, color: "#86868B", marginTop: 2 }}>
            {connectionStatus === "connected"
              ? "在线"
              : connectionStatus === "connecting"
                ? "连接中..."
                : connectionStatus === "reconnecting"
                  ? "重新连接中..."
                  : "已断开"}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "#86868B",
            fontSize: 20,
            padding: 4,
            borderRadius: 6,
          }}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* 消息列表 */}
      <MessageList
        messages={messages}
        sources={messages[messages.length - 1]?.sources}
      />

      {/* 输入框 */}
      <ChatInput
        onSend={handleSend}
        disabled={connectionStatus !== "connected"}
        placeholder={
          connectionStatus === "connected" ? "输入问题..." : "等待连接..."
        }
      />
    </div>
  );
};
```

**设计要点：**

- **WebSocket 管理**：自动连接、指数回退重连（最多 5 次）、断线状态提示
- **Token 流式渲染**：`onmessage` 中根据 `data.type` 分发处理，流式 token 追加到最后一条助手消息
- **连接状态**：header 中显示在线/断开状态，输入框在断线时禁用
- **Apple 毛玻璃效果**：`backdrop-filter: blur(20px)` + `rgba(255,255,255,0.85)` 半透明背景
- **面板尺寸**：380x600px，适合对话场景

### 5.4 MessageList.tsx — 消息列表

```tsx
// widget/src/MessageList.tsx

/**
 * MessageList: 消息列表组件
 *
 * 职责：
 * - 渲染消息气泡
 * - 流式 token 逐字渲染
 * - Markdown 渲染（支持表格、列表、代码块）
 * - 引用来源展示
 * - 反馈按钮 👍/👎
 * - 自动滚动到底部
 */

import React, { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage, WSSource } from "./types";

interface MessageListProps {
  messages: ChatMessage[];
  sources?: WSSource[];
}

export const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) return null;

  return (
    <div
      style={{
        flex: 1,
        overflowY: "auto",
        padding: "16px 20px",
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      {messages.map((msg) => (
        <div key={msg.id}>
          {/* 系统消息（欢迎语等） */}
          {msg.role === "system" && (
            <div
              style={{
                background: "rgba(0, 82, 204, 0.06)",
                borderRadius: 12,
                padding: "12px 16px",
                fontSize: 14,
                color: "#515154",
                lineHeight: 1.6,
              }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {msg.content}
              </ReactMarkdown>
            </div>
          )}

          {/* 用户消息 */}
          {msg.role === "user" && (
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <div
                style={{
                  background: "linear-gradient(135deg, #0052CC, #007AFF)",
                  color: "#fff",
                  borderRadius: 16,
                  borderBottomRightRadius: 4,
                  padding: "10px 16px",
                  maxWidth: "80%",
                  fontSize: 15,
                  lineHeight: 1.5,
                  boxShadow: "0 2px 8px rgba(0, 82, 204, 0.15)",
                }}
              >
                {msg.content}
              </div>
            </div>
          )}

          {/* 助手消息 */}
          {msg.role === "assistant" && (
            <div>
              <div
                style={{
                  background: "rgba(0, 0, 0, 0.03)",
                  borderRadius: 16,
                  borderBottomLeftRadius: 4,
                  padding: "12px 16px",
                  fontSize: 15,
                  lineHeight: 1.6,
                  color: "#1D1D1F",
                  maxWidth: "90%",
                }}
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.content}
                </ReactMarkdown>

                {/* 输入光标闪烁动画（流式生成中） */}
                {msg.streaming && (
                  <span
                    style={{
                      display: "inline-block",
                      width: 2,
                      height: 16,
                      background: "#0052CC",
                      marginLeft: 2,
                      animation: "blink 1s step-end infinite",
                    }}
                  />
                )}
              </div>

              {/* 引用来源 */}
              {msg.sources && msg.sources.length > 0 && !msg.streaming && (
                <div style={{ marginTop: 8, paddingLeft: 4 }}>
                  <div
                    style={{
                      fontSize: 12,
                      color: "#86868B",
                      marginBottom: 4,
                      fontWeight: 500,
                    }}
                  >
                    来源
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {msg.sources.map((src, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: 12,
                          color: "#0052CC",
                          background: "rgba(0, 82, 204, 0.08)",
                          padding: "2px 8px",
                          borderRadius: 6,
                          whiteSpace: "nowrap",
                        }}
                      >
                        {src.title}
                        {src.page ? ` (p.${src.page})` : ""}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* 反馈按钮 */}
              {!msg.streaming && (
                <div
                  style={{
                    display: "flex",
                    gap: 4,
                    marginTop: 6,
                    paddingLeft: 4,
                  }}
                >
                  <button
                    style={feedbackBtnStyle}
                    title="有帮助"
                    onClick={() => handleFeedback(msg.id, 1)}
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z" />
                    </svg>
                  </button>
                  <button
                    style={feedbackBtnStyle}
                    title="没帮助"
                    onClick={() => handleFeedback(msg.id, 0)}
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z" />
                    </svg>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* 错误消息 */}
          {msg.role === "error" && (
            <div
              style={{
                background: "rgba(255, 59, 48, 0.08)",
                borderRadius: 12,
                padding: "10px 14px",
                fontSize: 14,
                color: "#FF3B30",
                lineHeight: 1.5,
              }}
            >
              {msg.content}
            </div>
          )}
        </div>
      ))}

      {/* 自动滚动锚点 */}
      <div ref={bottomRef} />
    </div>
  );
};

const feedbackBtnStyle: React.CSSProperties = {
  background: "none",
  border: "1px solid rgba(0, 0, 0, 0.1)",
  borderRadius: 8,
  padding: "4px 8px",
  cursor: "pointer",
  color: "#86868B",
  display: "flex",
  alignItems: "center",
  gap: 4,
  fontSize: 13,
};

function handleFeedback(messageId: string, rating: number) {
  // TODO: 调用 POST /api/feedback
  console.log("Feedback:", messageId, rating);
}
```

**设计要点：**

- **Markdown 渲染**：使用 `react-markdown` + `remark-gfm`，支持表格、列表、代码块
- **流式光标**：`msg.streaming === true` 时显示闪烁的光标
- **来源展示**：蓝色 Tag 标签形式列出引用来源（带页码）
- **反馈按钮**：每条助手消息下方展示 👍/👎 按钮
- **气泡样式**：用户消息蓝色渐变右对齐，助手消息灰色左对齐，系统消息淡蓝背景
- **自动滚动**：`useEffect` 监听 messages 变化，smooth 滚动到底部

### 5.5 ChatInput.tsx — 输入框

```tsx
// widget/src/ChatInput.tsx

/**
 * ChatInput: 文本输入框
 *
 * 职责：
 * - 文本输入
 * - Enter 发送
 * - 加载态禁用
 * - 毛玻璃效果输入框
 */

import React, { useState, useRef, useCallback } from "react";

interface ChatInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  disabled = false,
  placeholder = "输入问题...",
}) => {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
    // 重置 textarea 高度
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }
  }, [text, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Enter 发送（Shift+Enter 换行）
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    // 自动增高
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  };

  return (
    <div
      style={{
        padding: "12px 16px 16px",
        borderTop: "1px solid rgba(0, 0, 0, 0.06)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        background: "rgba(255, 255, 255, 0.6)",
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "flex-end",
          background: "rgba(0, 0, 0, 0.04)",
          borderRadius: 12,
          padding: "4px 4px 4px 16px",
          border: "1px solid rgba(0, 0, 0, 0.06)",
          transition: "border-color 0.2s",
        }}
      >
        <textarea
          ref={inputRef}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          style={{
            flex: 1,
            border: "none",
            outline: "none",
            background: "transparent",
            fontSize: 15,
            color: "#1D1D1F",
            resize: "none",
            padding: "8px 0",
            fontFamily:
              '-apple-system, BlinkMacSystemFont, "SF Pro", "SF Pro Text", "Helvetica Neue", sans-serif',
            lineHeight: 1.4,
            maxHeight: 120,
          }}
        />

        {/* 发送按钮 */}
        <button
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          style={{
            width: 36,
            height: 36,
            borderRadius: 10,
            border: "none",
            background: text.trim()
              ? "linear-gradient(135deg, #0052CC, #007AFF)"
              : "rgba(0, 0, 0, 0.1)",
            color: "#fff",
            cursor: text.trim() ? "pointer" : "default",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            transition: "all 0.2s",
          }}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="12" y1="19" x2="12" y2="5" />
            <polyline points="5 12 12 5 19 12" />
          </svg>
        </button>
      </div>
    </div>
  );
};
```

**设计要点：**

- **Enter 发送**：按 Enter 直接发送，Shift+Enter 换行
- **自动增高**：输入框随内容自动增高（最大 120px）
- **毛玻璃容器**：外层容器 `backdrop-filter: blur(20px)`，内层输入框半透明灰底
- **发送按钮状态**：无内容时灰色禁用态，有内容时蓝色渐变可点
- **Apple 字体栈**：显示指定 `-apple-system` / `SF Pro` 字体

---

## 6. Apple 风格 UI 设计规范

### 6.1 颜色系统

| 用途           | 色值                                        | 说明             |
| -------------- | ------------------------------------------- | ---------------- |
| 背景色         | `#FFFFFF`                                   | 卡片/面板主背景  |
| 背景色（次要） | `#F5F5F7`                                   | Apple 经典浅灰   |
| 品牌色（主）   | `#0052CC`                                   | FinSight 品牌蓝  |
| 品牌色（渐变） | `linear-gradient(135deg, #0052CC, #007AFF)` | 按钮/用户消息    |
| 文本（主要）   | `#1D1D1F`                                   | Apple 深色文本   |
| 文本（次要）   | `#86868B`                                   | Apple 灰色副文本 |
| 文本（说明）   | `#515154`                                   | 辅助说明文案     |
| 分割线         | `rgba(0,0,0,0.06)`                          | 极淡分割线       |
| 错误色         | `#FF3B30`                                   | Apple 红         |
| 成功色         | `#34C759`                                   | Apple 绿         |

### 6.2 圆角规范

| 层级     | 圆角   | 适用          |
| -------- | ------ | ------------- |
| 面板     | `12px` | 主对话面板    |
| 卡片     | `12px` | 欢迎语卡片    |
| 消息气泡 | `16px` | 用户/助手消息 |
| 按钮     | `10px` | 发送按钮      |
| 标签     | `6px`  | 来源标签      |
| 圆形     | `50%`  | 触发按钮      |
| 输入框   | `12px` | 输入区        |

### 6.3 阴影层级

| 层级      | 阴影                            | 适用     |
| --------- | ------------------------------- | -------- |
| subtle    | `0 2px 8px rgba(0,0,0,0.08)`    | 消息气泡 |
| medium    | `0 8px 32px rgba(0,0,0,0.12)`   | 主面板   |
| prominent | `0 4px 16px rgba(0,82,204,0.3)` | 触发按钮 |

### 6.4 字体系统

字体栈：

```
font-family: -apple-system, BlinkMacSystemFont, "SF Pro", "SF Pro Text",
             "SF Pro Display", "Helvetica Neue", "Segoe UI", Roboto,
             Arial, sans-serif;
```

字号规范：

| 用途      | 字号    | 字重    | 颜色      |
| --------- | ------- | ------- | --------- |
| AI 名称   | 16px    | 600     | `#1D1D1F` |
| 消息正文  | 15px    | 400     | `#1D1D1F` |
| 按钮/标签 | 12-13px | 400-500 | 按上下文  |
| 状态提示  | 12px    | 400     | `#86868B` |

### 6.5 毛玻璃效果（Glassmorphism）

通用样式模板：

```css
backdrop-filter: blur(20px);
-webkit-backdrop-filter: blur(20px);
background: rgba(255, 255, 255, 0.85); /* 面板 */
/* 或 */
background: rgba(255, 255, 255, 0.6); /* 输入区/header */
border: 1px solid rgba(255, 255, 255, 0.3);
```

### 6.6 动画规范

| 场景       | 动画                           | 说明         |
| ---------- | ------------------------------ | ------------ |
| 面板展开   | `spring(1, 100, 10)`           | 弹簧弹出效果 |
| 按钮 hover | `transform: scale(1.05)`, 0.2s | 轻微放大     |
| 光标闪烁   | `blink 1s step-end infinite`   | 流式生成光标 |
| 消息出现   | `opacity 0.3s ease`            | 淡入         |

### 6.7 组件间距

```
面板内边距:   16px 20px
消息间距:     12px
段落间距:     8px
来源标签间距:  6px
头部高度:     56px (16px padding top/bottom)
输入区:       44px + padding
```

---

## 附录 A：.env 文件模板

```bash
# backend/.env

# ──── FinSight AI 配置 ────

# Claude API (via DeepSeek Pro Proxy)
ANTHROPIC_API_KEY=sk-your-deepseek-proxy-key
ANTHROPIC_BASE_URL=https://api.deepseek.com/v1  # 替换为实际代理地址

# DeepSeek Embedding API
DEEPSEEK_API_KEY=sk-your-deepseek-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 应用
DEBUG=true
```

## 附录 B：curl 测试命令

```bash
# WebSocket 流式对话（需要 websocat 或 wscat）
# npm install -g wscat
wscat -c "ws://localhost:8000/ws/chat?tenant=finsight"
> {"type": "message", "content": "腾讯PE是多少"}

# REST 非流式对话
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"tenant": "finsight", "content": "腾讯PE是多少"}'

# 用户反馈
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"session_id": "xxx", "message_id": "msg-001", "rating": 1}'

# 健康检查
curl http://localhost:8000/health
```

## 附录 C：实施顺序建议

| 阶段 | 文件              | 预估耗时 | 里程碑              |
| ---- | ----------------- | -------- | ------------------- |
| 1    | `config.py`       | 15 min   | 配置就绪            |
| 2    | `session.py`      | 20 min   | Session 管理        |
| 3    | `rag.py`          | 60 min   | RAG 流水线跑通      |
| 4    | `main.py`         | 30 min   | WebSocket 对话      |
| 5    | `ingest.py`       | 30 min   | 文档入库            |
| 6    | `types.ts`        | 15 min   | 前端类型            |
| 7    | `ChatInput.tsx`   | 15 min   | 输入框              |
| 8    | `MessageList.tsx` | 30 min   | 消息列表 + Markdown |
| 9    | `ChatPanel.tsx`   | 30 min   | 面板 + WebSocket    |
| 10   | `ChatWidget.tsx`  | 15 min   | 主入口              |
| 11   | 端到端联调        | 30 min   | 全部功能可用        |
| 12   | UI 打磨           | 30 min   | Apple 风格细节      |

**总计预估：约 5 小时核心开发 + 0.5 小时 UI 细节调整**

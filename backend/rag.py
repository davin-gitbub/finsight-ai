"""FinSight AI — RAG 流水线

核心 RAG 流程：
  用户 query → 拒绝检测 → DeepSeek Embedding → Chroma 检索
  → Prompt 构建 → Claude 流式生成（DeepSeek 代理）
"""

import re
import os
import httpx
from typing import AsyncGenerator, Optional

from config import settings

# ──── 拒绝检测 ────

REJECT_PATTERNS = {
    "investment_advice": [
        r"(买|卖|建仓|清仓|加仓|减仓|抄底|逃顶|追涨|杀跌)",
        r"(涨|跌|走势|目标价|预测|看[好多空涨跌]|看空)",
        r"(推荐|建议).*(股票|基金|产品|组合)",
        r"(能不能|是否).*(买|投资|入手)",
        r"\d{6}.*(买|卖|如何)",
    ],
    "sensitive_info": [
        r"(API\s*[Kk]ey|[Aa]pi[_-]?key|[Aa]ccess_[Tt]oken|sk[_-][a-zA-Z0-9]{5,})",
        r"(私钥|密钥|密码|口令|登录密码|给我.*[Tt]oken)",
        r"(ANTHROPIC_|OPENAI_|DEEPSEEK_)[A-Z_]+",
        r"(model\s*(name|config|id)|LLM|模型配置|模型名称)",
        r"(token|secret)\s*[:=]\s*[\"'][a-zA-Z0-9_\-]{8,}",
    ],
    "off_topic": [
        r"(天气|娱乐|八卦|明星|游戏|电影|电视剧|美食|旅游)",
    ],
}

REJECT_MESSAGES = {
    "investment_advice": (
        "您好，不能回复此问题，我是 FinSight AI，FinSight Securities 的智能金融助手。\n\n"
        "我可以回答关于公司业务、金融概念和市场术语的问题。"
        "请注意，我无法提供投资建议或股价预测。"
    ),
    "sensitive_info": (
        "您好，不能回复此问题，我是 FinSight AI，FinSight Securities 的智能金融助手。\n\n"
        "我可以回答关于公司业务、金融概念和市场术语的问题。"
        "请注意，我无法提供投资建议或股价预测。"
    ),
    "off_topic": (
        "您好，不能回复此问题，我是 FinSight AI，FinSight Securities 的智能金融助手。\n\n"
        "我可以回答关于公司业务、金融概念和市场术语的问题。"
        "请注意，我无法提供投资建议或股价预测。"
    ),
}


def check_rejection(query: str) -> Optional[dict]:
    """拒绝检测前置过滤器。返回 None 表示通过，dict 表示命中拒绝规则。"""
    for reason, patterns in REJECT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, query):
                return {
                    "code": "REJECTED",
                    "reason": reason,
                    "message": REJECT_MESSAGES[reason],
                }
    return None


# ──── Embedding（本地 sentence-transformers）────

_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def get_embedding(text: str) -> list[float]:
    """使用本地 sentence-transformers 模型计算文本向量。"""
    model = _get_embedding_model()
    return model.encode(text).tolist()


# ──── Chroma 检索 ────

_chroma_client = None


def get_chroma_client():
    """延迟初始化 Chroma 客户端"""
    global _chroma_client
    if _chroma_client is None:
        import chromadb

        _chroma_client = chromadb.PersistentClient(
            path=os.path.abspath(settings.chroma_persist_dir)
        )
    return _chroma_client


def get_chroma_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(name=settings.chroma_collection)


def retrieve(query: str, top_k: Optional[int] = None) -> list[dict]:
    """检索相似文档块。返回 [{"title","page","content","score"}, ...]"""
    k = top_k or settings.retrieval_top_k
    query_vector = get_embedding(query)
    collection = get_chroma_collection()

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    docs = []
    if results.get("documents") and results["documents"][0]:
        for i, doc_text in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            docs.append(
                {
                    "title": meta.get("source", "未知来源"),
                    "page": meta.get("page", ""),
                    "content": doc_text,
                    "score": round(1.0 - distance / 2, 4),
                }
            )
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
    """流式调用 Claude API（通过 DeepSeek 代理）"""
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

SYSTEM_PROMPT_TPL = """You are the AI financial assistant of {company_name}, named "{ai_name}".

## Your identity
- You are the official AI assistant of {company_name} (Chinese name: 融视证券)
- Your answers are based solely on the "Reference Materials" below
- You are professional, concise, and friendly

## Response rules
1. Always answer based on the "Reference Materials" below. **Do not make up information.**
2. If the reference materials do not contain relevant information, honestly tell the user you don't know.
3. If the user asks for investment advice or stock price predictions, politely decline.
4. When citing sources, mark them as [1], [2], etc. and list the source names at the end.
5. Use Markdown format for clarity.
6. Do not answer questions unrelated to {company_name}'s business and financial knowledge.
7. **IMPORTANT: Respond in the same language as the user's question.** If they ask in Chinese, reply in Chinese. If they ask in English, reply in English. If they ask in Traditional Chinese, reply in Traditional Chinese.

## Reference Materials
{context}
"""


def build_rag_prompt(
    query: str,
    retrieved_docs: list[dict],
    history: list[dict],
    company_name: str = "FinSight Securities",
    ai_name: str = "FinSight AI",
) -> tuple[str, list[dict]]:
    """构建 RAG Prompt，返回 (system_prompt, messages) 元组。"""
    context_parts = []
    for i, doc in enumerate(retrieved_docs, 1):
        if doc.get("content"):
            context_parts.append(
                f"[{i}] Source: {doc['title']} (p.{doc['page']})\n{doc['content']}\n"
            )
    context_text = (
        "\n".join(context_parts)
        if context_parts
        else "(No relevant reference materials found)"
    )

    system_prompt = SYSTEM_PROMPT_TPL.format(
        company_name=company_name, ai_name=ai_name, context=context_text
    )

    messages = list(history) if history else []
    messages.append({"role": "user", "content": query})

    return system_prompt, messages


# ──── 主入口 ────


async def rag_pipeline_stream(
    query: str,
    history: list[dict],
    company_name: str = "FinSight Securities",
    ai_name: str = "FinSight AI",
) -> AsyncGenerator[dict, None]:
    """RAG 流水线主入口（流式版本）。

    每次 yield 一个 dict:
      {"type": "status", "content": "..."}
      {"type": "token", "content": "..."}
      {"type": "sources", "sources": [...]}
      {"type": "done", "content": "...", "sources": [...]}
      {"type": "error", "code": "...", "content": "..."}
    """
    # 1. 拒绝检测
    rejection = check_rejection(query)
    if rejection:
        yield {
            "type": "error",
            "code": rejection["code"],
            "content": rejection["message"],
        }
        return

    # 2. 检索
    yield {"type": "status", "content": "正在检索知识库..."}
    try:
        docs = retrieve(query)
    except Exception as e:
        yield {
            "type": "error",
            "code": "RETRIEVAL_FAILED",
            "content": f"检索失败：{str(e)}",
        }
        return

    # 3. 构建 Prompt
    yield {"type": "status", "content": "正在生成回答..."}
    system_prompt, messages = build_rag_prompt(
        query, docs, history, company_name, ai_name
    )

    # 4. 流式调用 LLM
    full_response = ""
    try:
        async for token in stream_llm(system_prompt, messages):
            full_response += token
            yield {"type": "token", "content": token}
    except Exception as e:
        yield {
            "type": "error",
            "code": "LLM_ERROR",
            "content": f"生成回答失败：{str(e)}",
        }
        return

    # 5. 返回来源和完成信号
    sources = [
        {"title": d["title"], "page": d["page"]} for d in docs if d["score"] > 0.15
    ]
    yield {"type": "sources", "sources": sources}
    yield {"type": "done", "content": full_response, "sources": sources}

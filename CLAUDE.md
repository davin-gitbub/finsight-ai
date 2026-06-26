# FinSight AI

金融行业 AI 对话 + RAG 问答系统。嵌入官网作为客户智能助手。

## 架构

```
前端 React <ChatWidget> → WebSocket → FastAPI → RAG Pipeline → Claude API
```

## 目录结构

```
finsight-ai/
├── backend/
│   ├── main.py        # FastAPI 入口 + API 路由
│   ├── rag.py         # RAG 流水线（检索 + 拼 prompt）
│   ├── session.py     # ChatSession 上下文管理
│   ├── config.py      # API Key 配置
│   ├── ingest.py      # 离线文档处理脚本
│   └── requirements.txt
├── widget/
│   └── src/
│       ├── ChatWidget.tsx
│       ├── ChatPanel.tsx
│       ├── MessageList.tsx
│       ├── ChatInput.tsx
│       └── types.ts
└── docs/
    └── architecture.md
```

## 技术栈

- 后端：Python FastAPI + Uvicorn
- 向量库：Pinecone Serverless
- LLM：Claude API (anthropic SDK)
- Embedding：OpenAI text-embedding-3-large
- 文档解析：PyMuPDF
- 前端：React + TypeScript + TailwindCSS
- 通信：WebSocket 流式

## 关键设计

- 上下文：最近 3 轮对话，10 分钟无输入自动清空
- 身份：金融助手，不提供投资建议，不预测股价
- RAG：纯向量检索（MVP 不加关键词）
- 部署：Railway

## 文档

完整架构方案见 `docs/architecture.md`。

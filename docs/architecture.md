# FinSight AI — MVP 技术方案

> 一个面向证券/金融场景的 AI 对话 + RAG 问答系统，嵌入官网服务客户。
> 对标富途牛牛 AI，但 MVP 阶段以"跑通链路、验证价值"为目标。

---

## 一、方案概述

### 我们要做什么

在官网嵌入一个 AI 聊天对话框，客户可以直接提问，AI 基于公司知识库（研报、公告、FAQ 等）给出回答。类似 Yellow River Securities 的 "River AI" 页面，但实际可用。

### 身份定义（AI 角色）

```
名称：River AI（可以自定义）
定位：公司智能金融助手
风格：专业、简洁、中文
能力边界：
  ✅ 回答基于公司知识库的问题（研报、公告、费率、流程等）
  ✅ 解释金融术语
  ❌ 不提供投资建议
  ❌ 不预测股价
  ❌ 不回答与公司无关的问题
```

### 核心功能

```
MVP 功能清单
├─ 用户提问 → AI 回答（基于公司文档）
├─ 流式输出（一个字一个字出，体验好）
├─ 保留最近 3 轮对话上下文（能理解"它""这个"指代）
├─ 10分钟无输入 → 自动清空历史（新对话）
├─ 引用来源（回答里标注来自哪个文档）
├─ 用户反馈 👍👎（收集数据后面改进）
└─ 一行代码嵌入 React 网站
```

---

## 二、架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                        用户端                                      │
│  React 网站                                                        │
│  └─ <ChatWidget tenant="xxx" /> — 聊天组件                        │
│     ├─ WebSocket → wss://api.yourservice.com/ws/chat             │
│     ├─ 流式显示 token                                             │
│     └─ Markdown 渲染 + 引用链接                                    │
└───────────────────────────┬──────────────────────────────────────┘
                            │ WSS
┌───────────────────────────▼──────────────────────────────────────┐
│                     后端 FastAPI                                   │
│                                                                   │
│  POST /api/chat        → 发起对话（返回 session_id）               │
│  WS   /ws/chat         → 流式对话（核心接口）                      │
│  POST /api/feedback    → 用户反馈                                 │
│                                                                   │
│  每 WebSocket 连接 = 一个 session                                  │
│  ├─ session_id                                                  │
│  ├─ history[]   ← 最近 3 轮对话                                    │
│  └─ last_active ← 最后活动时间，>10分钟自动 reset                  │
└───────┬──────────────────────────────────────────────────────────┘
        │
        ├─────────────────────────────────────────────────────┐
        │   RAG 流水线                                         │
        │                                                     │
        │  用户输入                                               │
        │    ↓                                                 │
        │  ① 拼上下文：history(3轮) + 当前问题                    │
        │    ↓                                                 │
        │  ② 用户问题 → OpenAI Embedding → 向量                  │
        │    ↓                                                 │
        │  ③ Pinecone 向量检索 → Top-10                          │
        │    ↓                                                 │
        │  ④ 拼 System Prompt + 检索结果 + 历史 + 问题            │
        │    ↓                                                 │
        │  ⑤ Claude API 流式返回 → WebSocket 推给客户端           │
        │    ↓                                                 │
        │  ⑥ 用户看到逐字生成的回答                                │
        └─────────────────────────────────────────────────────┘

        ┌─────────────────────────────────────────────────────┐
        │   离线文档处理（一次性跑）                              │
        │                                                     │
        │  上传 PDF/Word                                       │
        │    ↓                                                 │
        │  PyMuPDF 解析 → 按段落+章节切块                       │
        │    ↓                                                 │
        │  OpenAI Embedding → 写入 Pinecone（带 tenant 标记）    │
        │    ↓                                                 │
        │  完成后即可在对话中检索到                                 │
        └─────────────────────────────────────────────────────┘
```

---

## 三、上下文机制（简单版）

### 实现方式

每个 WebSocket 连接对应一个 ChatSession，内存中维护：

```python
class ChatSession:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.history: list[dict] = []   # [{"role":"user","content":...}, {"role":"assistant","content":...}]
        self.last_active: float = time.time()
    
    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        self.last_active = time.time()
    
    def get_context(self, max_rounds: int = 3) -> list[dict]:
        # 只保留最近 max_rounds 轮
        return self.history[-(max_rounds * 2):]  # 每轮 user + assistant
```

### 拼入 Prompt

```
System: 你是 {company_name} 的智能金融助手，名称为 {ai_name}。
请仅基于以下参考资料回答问题。如果参考资料中没有相关信息，
请如实告知用户你不知道。

参考资料：
{检索到的 Top-5 文档片段，带来源标注}

—————

{历史对话（最近 3 轮）}
用户：{当前问题}
助手：
```

### 清空逻辑

```python
if time.time() - session.last_active > 600:  # 10 分钟
    session.history.clear()
```

### 不做的（相比富途）

| 富途做的 | MVP 不做 | 理由 |
|---------|---------|------|
| 小模型预分类主题 | 全部走 LLM | 量小不需要 |
| 时间加权历史 | 只保留最近 3 轮 | 够用 |
| 语义压缩 query | 直接传原文 | token 够用 |
| 向量化存储对话历史 | 内存里存文本 | 重启丢了也不要紧 |
| 用户画像个性化 | 统一回复 | MVP 不登录也能用 |

---

## 四、技术栈

| 层 | 技术 | 版本 | 用途 |
|---|------|------|------|
| **后端框架** | Python FastAPI | latest | API 服务 |
| **ASGI 服务器** | Uvicorn | latest | 跑 FastAPI |
| **LLM** | Claude API (anthropic SDK) | sonnet-4 | 生成回答 |
| **Embedding** | OpenAI API (text-embedding-3-large) | latest | 文档向量化 |
| **向量数据库** | Pinecone Serverless | latest | 存储 + 检索文档向量 |
| **文档解析** | PyMuPDF (fitz) | latest | PDF 解析 |
| **WS 通信** | fastapi.WebSocket | 原生 | 流式推送 |
| **前端** | React + TypeScript | 18+ | 聊天组件 |
| **CSS** | TailwindCSS | 3+ | 样式 |
| **WS 客户端** | 原生 WebSocket API | 浏览器 | 连接后端 |
| **Markdown 渲染** | react-markdown + remark-gfm | latest | 渲染回答 |
| **部署** | Railway | — | 一键部署 |

### 不需要的

```
❌ LangChain / LangGraph
❌ Redis / 消息队列
❌ PostgreSQL / 数据库
❌ Elasticsearch
❌ Docker（MVP 阶段 Railway 自动处理）
❌ K8s
```

---

## 五、项目目录结构

```
river-ai/
├── backend/
│   ├── main.py                 # FastAPI 入口 + 路由
│   ├── rag.py                  # RAG 流水线（检索 + 拼 prompt）
│   ├── session.py              # ChatSession 管理（上下文）
│   ├── config.py               # 配置（API Key 等）
│   ├── ingest.py               # 文档处理脚本（离线跑一次）
│   └── requirements.txt        # Python 依赖
│
├── widget/                     # 前端聊天组件
│   ├── src/
│   │   ├── ChatWidget.tsx      # 主组件
│   │   ├── ChatPanel.tsx       # 对话框面板
│   │   ├── MessageList.tsx     # 消息列表
│   │   ├── ChatInput.tsx       # 输入框
│   │   └── types.ts            # 类型定义
│   ├── package.json
│   └── tailwind.config.js
│
└── docs/
    └── architecture.md         # 本文档
```

**命名规则：**
- 函数/变量：蛇形命名 `retrieve_docs()`
- 前端组件：帕斯卡命名 `ChatWidget`
- 文件：蛇形命名 `rag.py`

---

## 六、API 设计

### WebSocket — 流式对话（核心接口）

```
连接：wss://api.yourservice.com/ws/chat?tenant=xxx&session_id=xxx

客户端 → 服务端：
{"type": "message", "content": "腾讯的PE是多少？"}

服务端 → 客户端（流式）：
{"type": "token", "content": "根据"}       # 逐 token
{"type": "token", "content": "我"}
{"type": "token", "content": "查"}
{"type": "token", "content": "阅"}
{"type": "token", "content": "的"}
...
{"type": "done", "sources": [{"title": "腾讯2024年报", "url": ""}]}

服务端 → 客户端（错误）：
{"type": "error", "content": "连接失败，请稍后重试"}
```

### REST — 辅助接口

```
POST /api/chat
  Body: {"tenant": "xxx", "content": "腾讯PE是多少?", "session_id": "xxx"}
  Response: {"reply": "腾讯当前PE为24.5...", "sources": [...]}

POST /api/feedback
  Body: {"session_id": "xxx", "message_id": "xxx", "rating": 1}  // 1=👍 0=👎
  Response: {"status": "ok"}
```

---

## 七、与富途牛牛 AI 对比

| 维度 | 富途牛牛 AI | River AI MVP |
|------|------------|-------------|
| **定位** | 全功能智能投资引擎 | 公司官网 AI 客服 + 知识库问答 |
| **核心能力** | 行情分析、策略生成、实盘交易、AI Agent | 基于公司文档的问答、术语解释 |
| **技术路线** | 全自研：Go 微服务 + 自建金融模型 + Python PyTorch | FastAPI + Claude API + Pinecone + React |
| **模型策略** | 自建金融模型（专家训练）+ LLM 组合调优 | Claude Sonnet API + Prompt Engineering |
| **上下文机制** | 专利级：主题识别+时间加权+语义压缩+向量化历史 | 简单 3 轮历史缓存 + 10分钟超时清空 |
| **数据来源** | 自有行情数据、社区内容、全网搜索 | 客户上传的公司文档、FAQ |
| **个性化** | 可接入用户持仓，针对性分析 | 无个性化，统一回答 |
| **Agent 能力** | 策略生成→回测→实盘（AI Agent Skills） | 纯问答，无 Agent |
| **响应模式** | 流式 + 结构化报告 | 流式 token |
| **部署** | K8s + 自研 GoOps，多可用区 | Railway 单服务 |
| **团队规模** | 千人技术团队，14 年迭代 | 1-3 人，2 周 MVP |
| **适用客户** | 富途 2000 万+ 交易用户 | 单一公司官网访客 |

### 能力对比雷达图（1-5分）

```
                   富途牛牛 AI      River AI MVP
知识库问答能力        ★★★★☆           ★★★★☆
多轮对话理解          ★★★★★           ★★★☆☆
行情数据分析          ★★★★★           ☆☆☆☆☆
交易执行              ★★★★★           ☆☆☆☆☆
个性化程度            ★★★★★           ★☆☆☆☆
部署/运维复杂度       ★★★★☆(重)       ★☆☆☆☆(轻)
开发速度              ★☆☆☆☆           ★★★★★
成本                  ★★★★★(高)       ★★☆☆☆(低)
```

### 一句话

```
富途 = 造航母（覆盖交易全链路，千万用户级别）
我们 = 造快艇（先解决官网智能问答一个痛点，跑通再升级）
```

---

## 八、MVP 实施路线

### 第 1 天：环境 + 后端

```
1. 注册/准备 API Key
   ├─ Pinecone: 创建 index
   ├─ OpenAI: 获取 API Key（用于 embedding）
   └─ Anthropic: 获取 API Key（用于 Claude）
2. 写 main.py + rag.py + session.py
3. 跑通 /ws/chat 流式对话
   ├─ 用户发 "你好" → AI 能回复
   └─ 流式 token 逐字推送到 ws
```

### 第 2 天：文档入库

```
1. 准备测试文档（2-3 份 PDF）
2. 跑 ingest.py
   ├─ PyMuPDF 解析
   ├─ 按段落切块
   ├─ OpenAI embedding
   └─ 写入 Pinecone
3. 验证：问一个文档里有的问题 → 能检索到并正确回答
```

### 第 3 天：前端组件

```
1. 写 ChatWidget React 组件
   ├─ 支持 WebSocket 连接
   ├─ 流式显示 token
   ├─ Markdown 渲染
   └─ 引用来源展示
2. 在你的 React 项目里安装并嵌入
3. 部署后端到 Railway
```

---

## 九、身份定义（开机 Prompt）

```python
SYSTEM_PROMPT = """你是 {company_name} 的智能金融助手，名称是 "{ai_name}"。

## 你的身份
- 你是 {company_name} 官方服务的 AI 助手
- 你的回答仅基于公司提供的参考资料
- 你使用中文回答，风格专业、简洁、友好

## 回答规则
1. 始终基于"参考资料"中的内容回答，不要编造信息
2. 如果参考资料中没有相关信息，明确告知用户你不知道
3. 如果用户问到投资建议、股价预测，礼貌拒绝并说明无法提供
4. 回答中引用来源时，标注 [1]、[2] 等编号，结尾列出对应来源名称
5. 使用 Markdown 格式，适当使用标题、列表、表格使回答更清晰

## 参考资料
{context}

## 历史对话
{history}

## 当前问题
用户：{query}
助手："""
```

---

## 十、注意事项 / 边界

### 安全边界

```
✅ 可回答：费率多少、开户流程、XX概念是什么、年报发了没
❌ 拒绝回答：这只股票能买吗、明天涨还是跌、推荐个投资组合
❌ 拒绝回答：与公司业务无关的问题（天气、娱乐等）
```

### 已知限制（MVP 阶段）

| 限制 | 原因 | 后续可改进 |
|------|------|-----------|
| 无用户认证 | 简化 MVP | 加 session token |
| 无缓存 | 每个问题都查向量库 | 加 Redis 精确/语义缓存 |
| 无关键词检索 | 纯向量，数字/代码可能不准 | 加 ES 混合检索 |
| 只支持 PDF/Word | 简化文档解析 | 加网页、图片 OCR |
| 无管理员后台 | 文档上传靠脚本 | 加管理面板 |
| 无数据分析 | 看不到用户问什么 | 加对话统计看板 |

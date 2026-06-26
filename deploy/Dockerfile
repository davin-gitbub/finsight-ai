# FinSight AI — Backend Dockerfile
# Python 3.12 + FastAPI + ChromaDB + sentence-transformers

FROM python:3.12-slim

# --- 系统依赖 (ChromaDB 需要 libc++) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    libc++-dev \
    && rm -rf /var/lib/apt/lists/*

# --- 工作目录 ---
WORKDIR /app

# --- 安装 Python 依赖 ---
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- 预下载 Embedding 模型 (避免首次请求冷启动 30-60s) ---
ENV HF_HOME=/app/hf_cache
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# --- 复制应用代码 ---
COPY backend/ .

# --- 创建数据目录 (volume 挂载点) ---
RUN mkdir -p /app/chroma_db /app/feedback

# --- 运行时 ---
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

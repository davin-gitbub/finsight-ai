"""FinSight AI — 配置管理

使用 pydantic-settings 管理所有配置项，支持 .env 文件加载。
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # ──── 应用配置 ────
    app_name: str = "FinSight AI"
    debug: bool = False
    # 服务器绑定
    host: str = "0.0.0.0"
    port: int = 5173
    # CORS 白名单 — 逗号分隔，同源部署时设为空字符串即可
    cors_origins: str = "http://localhost:8000,http://localhost:5173,http://127.0.0.1:8000,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        val = self.cors_origins.strip()
        return [o.strip() for o in val.split(",") if o.strip()] if val else []

    allowed_referers: list[str] = ["localhost", "127.0.0.1", "finsight"]

    # ──── LLM (DeepSeek 代理 Claude) ────
    llm_provider: str = "anthropic"
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_base_url: Optional[str] = Field(default=None, alias="ANTHROPIC_BASE_URL")
    claude_model: str = "deepseek-v4-flash"
    max_tokens: int = 1024
    temperature: float = 0.3

    # ──── Embedding (sentence-transformers 本地模型) ────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    # ──── Chroma ────
    chroma_persist_dir: str = "chroma_db"
    chroma_collection: str = "finsight_docs"
    retrieval_top_k: int = 5

    # ──── Session ────
    session_timeout: int = 600
    max_history_rounds: int = 3

    # ──── 拒绝回答检测 ────
    reject_keywords: list[str] = [
        "买",
        "卖",
        "买入",
        "卖出",
        "建仓",
        "减仓",
        "加仓",
        "目标价",
        "看涨",
        "看跌",
        "推荐",
        "评级",
        "涨到",
        "跌到",
        "会不会涨",
        "能不能买",
        "投资建议",
        "操盘",
        "抄底",
        "逃顶",
        "stock pick",
        "buy",
        "sell",
        "target price",
        # 敏感信息泄露防护
        "API Key",
        "api_key",
        "api-key",
        "apikey",
        "sk-",
        "sk_",  # API key 前缀
        "token",
        "Token",
        "access_token",
        "secret",
        "密码",
        "口令",
        "登录密码",
        "模型配置",
        "model name",
        "模型名称",
        "LLM",
        "ANTHROPIC_",
        "OPENAI_",
        "DEEPSEEK_",
        "private key",
        "私钥",
        "密钥",
    ]

    # ──── 速率限制与 Token 保护 ────
    page_token_secret: str = Field(
        default="",
        alias="PAGE_TOKEN_SECRET",
        description="页面 token 签名密钥，留空则自动生成（每次重启变化）",
    )
    rate_limit_per_session: float = 1.5  # 每个 session 请求间隔（秒）
    rate_limit_global_max: int = 5  # 全局最大并发请求数
    query_min_length: int = 2  # 最小提问长度
    query_max_length: int = 500  # 最大提问长度
    max_tokens_per_response: int = 1024  # 每次回答最大 token
    max_tokens_per_session: int = 20000  # 每个 session 累计 token 上限

    # ──── 文档入库 ────
    chunk_min_chars: int = 20
    chunk_max_chars: int = 1500
    chunk_overlap_chars: int = 100

    # ──── 数据目录 ────
    feedback_path: str = "./feedback.jsonl"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

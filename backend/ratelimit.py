"""FinSight AI — 速率限制与安全防护"""

import time
import threading
import hashlib
import hmac
import os
from typing import Dict, Tuple, Optional

from config import settings


# ──── 已知爬虫/机器人 User-Agent 关键词 ────

BOT_UA_KEYWORDS = [
    "bot",
    "crawler",
    "spider",
    "scraper",
    "curl",
    "wget",
    "python-requests",
    "python-httpx",
    "go-http-client",
    "java/",
    "okhttp",
    "ruby",
    "scrapy",
    "axios",
    "aiohttp",
    "httplib",
    "urllib",
    "libwww",
    "lwp",
    "fetch",
    "node-fetch",
    "php",
    "perl",
    "nethttp",
    "httpclient",
    "selenium",
    "headless",
    "phantom",
    "puppeteer",
    "playwright",
    "cypress",
]

# ──── Token 签发 ────

_secret: str = None  # type: ignore


def _get_secret() -> str:
    global _secret
    if _secret is not None:
        return _secret
    # 优先使用配置中的固定密钥（持久化，重启不变）
    from config import settings

    if settings.page_token_secret:
        _secret = settings.page_token_secret
    else:
        # 自动生成（每次重启变化，旧 token 失效）
        _secret = os.urandom(32).hex()
    return _secret


def generate_page_token() -> str:
    """生成页面加载时下发的验证 token"""
    ts = int(time.time())
    raw = f"finsight:{ts}:{_get_secret()}"
    sig = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"{ts}:{sig}"


def verify_page_token(token: str) -> bool:
    """验证页面 token（5 分钟内有效）"""
    try:
        parts = token.split(":")
        ts = int(parts[0])
        sig = parts[1]
        if time.time() - ts > 300:
            return False
        expected = hashlib.sha256(
            f"finsight:{ts}:{_get_secret()}".encode()
        ).hexdigest()[:12]
        return hmac.compare_digest(sig, expected)
    except (IndexError, ValueError):
        return False


# ──── 机器人检测 ────


def is_bot(user_agent: str) -> Tuple[bool, str]:
    """检查 User-Agent 是否为已知爬虫/机器人"""
    ua = user_agent.lower()
    for kw in BOT_UA_KEYWORDS:
        if kw in ua:
            return True, kw
    return False, ""


# ──── IP 速率限制 ────


class IPRateLimiter:
    """基于 IP 的请求频率限制"""

    def __init__(self):
        self._lock = threading.Lock()
        # ip -> [(timestamp, weight), ...]  滑动窗口
        self._windows: Dict[str, list] = {}
        # WINDOW 秒内最多 MAX 次请求
        self.WINDOW = 60
        self.MAX_REQUESTS = 30

    def check(self, ip: str) -> Tuple[bool, str]:
        now = time.time()
        with self._lock:
            if ip not in self._windows:
                self._windows[ip] = []
            # 清理过期记录
            self._windows[ip] = [
                (t, w) for t, w in self._windows[ip] if now - t < self.WINDOW
            ]
            count = sum(w for _, w in self._windows[ip])
            if count >= self.MAX_REQUESTS:
                return False, f"请求过于频繁，{self.WINDOW}秒后再试"
            self._windows[ip].append((now, 1))
            return True, ""


ip_limiter = IPRateLimiter()


# ──── Session 速率限制 ────


class RateLimiter:
    """Session 级别的速率限制，防止 token 滥用"""

    def __init__(self):
        self._lock = threading.Lock()
        self._session_last: Dict[str, float] = {}
        self._session_tokens: Dict[str, int] = {}
        self._active_requests = 0

    def check_session(self, session_id: str) -> Tuple[bool, str]:
        now = time.time()
        with self._lock:
            if self._active_requests >= settings.rate_limit_global_max:
                return False, "系统繁忙，请稍后再试"
            last = self._session_last.get(session_id, 0)
            if now - last < settings.rate_limit_per_session:
                return False, "请求过于频繁，请稍后再试"
            total = self._session_tokens.get(session_id, 0)
            if total >= settings.max_tokens_per_session:
                return False, "今日对话额度已用完"
            self._session_last[session_id] = now
            self._active_requests += 1
            return True, ""

    def release(self, session_id: str, tokens_used: int = 0):
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
            if tokens_used > 0:
                self._session_tokens[session_id] = (
                    self._session_tokens.get(session_id, 0) + tokens_used
                )

    def check_query(self, query: str) -> Tuple[bool, str]:
        q = query.strip()
        if len(q) < settings.query_min_length:
            return False, "问题太短，请输入更多内容"
        if len(q) > settings.query_max_length:
            return False, "问题太长，请精简后重试"
        return True, ""


rate_limiter = RateLimiter()

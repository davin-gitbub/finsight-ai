"""FinSight AI — 会话管理

线程安全的 ChatSession 和 SessionManager。
10 分钟无输入自动清空历史，session 本身保持存活。
"""

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
        self.history: list[dict] = []
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
        max_messages = settings.max_history_rounds * 2
        context = (
            self.history[:-1]
            if self.history and self.history[-1]["role"] == "user"
            else self.history
        )
        return context[-max_messages:]

    def is_expired(self) -> bool:
        """检查是否超过 N 分钟无活动"""
        return time.time() - self.last_active > settings.session_timeout

    def clear(self):
        """清空历史"""
        self.history.clear()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "message_count": self.message_count,
            "last_active": self.last_active,
        }


class SessionManager:
    """线程安全的全局 Session 管理器"""

    def __init__(self):
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self, tenant_id: str, session_id: Optional[str] = None
    ) -> ChatSession:
        with self._lock:
            if session_id and session_id in self._sessions:
                session = self._sessions[session_id]
                if session.is_expired():
                    session.clear()
                return session
            session = ChatSession(tenant_id=tenant_id, session_id=session_id)
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> Optional[ChatSession]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.is_expired():
                session.clear()
                return None
            return session

    def remove(self, session_id: str):
        with self._lock:
            self._sessions.pop(session_id, None)

    def cleanup_expired(self):
        """清理过期 session"""
        now = time.time()
        with self._lock:
            expired = [
                sid
                for sid, s in self._sessions.items()
                if now - s.last_active > settings.session_timeout
            ]
            for sid in expired:
                del self._sessions[sid]
            return len(expired)

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._sessions)


session_manager = SessionManager()

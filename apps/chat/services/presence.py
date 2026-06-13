"""
Presence — кто сейчас онлайн (есть активный WS-коннект).

Источник истины — счётчик коннектов в Redis (>0 → online), см. §8. Несколько
вкладок/устройств → несколько коннектов, поэтому именно счётчик, не флаг.
Best-effort: presence не критичен (фаза 2), при недоступности Redis считаем
offline и не роняем ни WS, ни REST.
"""

from __future__ import annotations

from collections.abc import Iterable

import structlog
from django_redis import get_redis_connection

logger = structlog.get_logger(__name__)

_KEY = "chat:online:{uid}"
# Safety-TTL на счётчик: если disconnect не доехал (kill -9 процесса), ключ
# сам протухнет и юзер не «залипнет» онлайн навечно.
_TTL_SECONDS = 60 * 60


class PresenceService:
    @staticmethod
    def _conn():
        return get_redis_connection("default")

    @classmethod
    def connected(cls, user_id: int) -> None:
        try:
            conn = cls._conn()
            key = _KEY.format(uid=user_id)
            conn.incr(key)
            conn.expire(key, _TTL_SECONDS)
        except Exception:
            logger.warning("presence_connected_failed", user_id=user_id)

    @classmethod
    def disconnected(cls, user_id: int) -> None:
        try:
            conn = cls._conn()
            key = _KEY.format(uid=user_id)
            value = conn.decr(key)
            if value is None or value <= 0:
                conn.delete(key)
        except Exception:
            logger.warning("presence_disconnected_failed", user_id=user_id)

    @classmethod
    def is_online(cls, user_id: int) -> bool:
        try:
            return bool(cls._conn().exists(_KEY.format(uid=user_id)))
        except Exception:
            return False

    @classmethod
    def online_map(cls, user_ids: Iterable[int]) -> dict[int, bool]:
        """Батч-проверка онлайна (один pipeline) для списка чатов."""
        ids = list(user_ids)
        if not ids:
            return {}
        try:
            conn = cls._conn()
            pipe = conn.pipeline()
            for uid in ids:
                pipe.exists(_KEY.format(uid=uid))
            results = pipe.execute()
            return {uid: bool(res) for uid, res in zip(ids, results, strict=False)}
        except Exception:
            return dict.fromkeys(ids, False)

"""
Промпт-шаблоны и JSON-схема ответа для AI-рекомендаций.

Промпт собран так, чтобы модель:
- использовала только place_id из контекста (защита от hallucination через
  явное правило + post-filter)
- давала 2-3 рекомендации, не 10 (UX — не пугать список из 10 кафе)
- формировала reasoning на русском, 1-2 предложения
"""
from __future__ import annotations

from typing import Any

SYSTEM_PROMPT_TEMPLATE = """Ты — AI-помощник "Куда пойти?" в социальном приложении для города Астана.
Ты помогаешь пользователю выбрать 2-3 заведения или события из списка ниже, под его запрос.

Правила:
1. Рекомендуй ТОЛЬКО места и события из контекста ниже. Если ничего не подходит, верни пустой массив.
2. Используй ТОЛЬКО реальные place_id из контекста. Не выдумывай id.
3. Reasoning пиши на русском, 1-2 предложения. Объясни почему именно это место.
4. vibe_match — 1-3 тега вайбов места, которые соответствуют запросу.
5. Учитывай предпочтения пользователя (если они переданы в user-сообщении).

# Контекст города

{context}
"""


# Gemini принимает OpenAPI-subset JSON Schema через response_schema.
# Запрещаем модели выдумывать поля кроме перечисленных.
RECOMMEND_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "place_id": {"type": "integer"},
                    "reasoning": {"type": "string"},
                    "vibe_match": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["place_id", "reasoning"],
            },
        },
    },
    "required": ["items"],
}


def build_user_message(
    *,
    query: str,
    preferred_vibes: list[str],
    ai_context: str,
) -> str:
    """
    Сообщение от юзера. Контекст профиля (вайбы + о себе) подмешивается,
    если он задан, иначе только сам query.
    """
    parts: list[str] = []

    profile_lines: list[str] = []
    if preferred_vibes:
        profile_lines.append(f"- Любимые вайбы: {', '.join(preferred_vibes)}")
    if ai_context:
        profile_lines.append(f"- О себе: {ai_context}")

    if profile_lines:
        parts.append("О пользователе:")
        parts.extend(profile_lines)
        parts.append("")

    parts.append(f"Запрос: {query}")
    return "\n".join(parts)
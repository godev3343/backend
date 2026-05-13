"""
Калькуляция стоимости одного LLM-запроса.

Прайс-лист хардкодится здесь — он меняется редко, а тащить из env
просто чтобы был "не хардкод" — ненужная сложность. На pre-MVP мы на free tier,
cost_usd всё равно 0, но считаем правильно для будущего.

Цены актуальны на 2026-05; источник — официальные тарифы провайдеров.
Если перешли на платный tier — апдейтим тут и катим миграцию данных в логах
если нужен пересчёт исторических costs (вряд ли).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ModelPricing:
    """Стоимость в USD за 1M токенов."""

    input_per_1m: Decimal
    output_per_1m: Decimal
    cached_input_per_1m: Decimal = Decimal("0")


# Цены в USD per 1M tokens.
_PRICING: dict[str, ModelPricing] = {
    # Gemini 2.5 family
    "gemini-2.5-flash": ModelPricing(
        input_per_1m=Decimal("0.30"),
        output_per_1m=Decimal("2.50"),
        cached_input_per_1m=Decimal("0.075"),
    ),
    "gemini-2.5-flash-lite": ModelPricing(
        input_per_1m=Decimal("0.10"),
        output_per_1m=Decimal("0.40"),
    ),
    "gemini-2.5-pro": ModelPricing(
        input_per_1m=Decimal("1.25"),
        output_per_1m=Decimal("10.00"),
    ),
    # Gemini 3.x
    "gemini-3-flash": ModelPricing(
        input_per_1m=Decimal("0.30"),
        output_per_1m=Decimal("2.50"),
    ),
    "gemini-3.1-flash-lite": ModelPricing(
        input_per_1m=Decimal("0.10"),
        output_per_1m=Decimal("0.40"),
    ),
    # Anthropic — на будущее
    "claude-haiku-4-5": ModelPricing(
        input_per_1m=Decimal("1.00"),
        output_per_1m=Decimal("5.00"),
    ),
    "claude-sonnet-4-6": ModelPricing(
        input_per_1m=Decimal("3.00"),
        output_per_1m=Decimal("15.00"),
    ),
}


def calc_cost_usd(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
) -> Decimal:
    """
    Возвращает стоимость запроса в USD. Если модель неизвестна — 0
    (логируется, но не блокирует ответ).

    Округление до 6 знаков — хватает для стоимости одного запроса
    (на flash-tier один запрос ~0.001-0.005 USD).
    """
    pricing = _PRICING.get(model)
    if pricing is None:
        return Decimal("0")

    # cached токены идут со скидкой, остальные input — по полной
    paid_input = max(input_tokens - cached_input_tokens, 0)
    million = Decimal("1000000")

    cost = (
        (Decimal(paid_input) / million) * pricing.input_per_1m
        + (Decimal(cached_input_tokens) / million) * pricing.cached_input_per_1m
        + (Decimal(output_tokens) / million) * pricing.output_per_1m
    )
    return cost.quantize(Decimal("0.000001"))
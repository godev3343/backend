from __future__ import annotations

import pytest

from apps.ai.clients.base import LLMError, LLMMessage
from apps.ai.clients.gemini import GeminiClient


class TestGeminiClient:
    def test_empty_api_key_raises(self) -> None:
        with pytest.raises(LLMError):
            GeminiClient(api_key="")

    @pytest.mark.asyncio
    async def test_complete_returns_response(self, mocker) -> None:
        """Мокаем SDK, проверяем что обёртка корректно мапит usage."""
        from types import SimpleNamespace

        client = GeminiClient(api_key="fake-key")
        fake_response = SimpleNamespace(
            text="Hello",
            usage_metadata=SimpleNamespace(
                prompt_token_count=10,
                candidates_token_count=5,
                cached_content_token_count=0,
            ),
        )

        mocker.patch.object(
            client._client.aio.models,
            "generate_content",
            return_value=fake_response,
        )

        response = await client.complete(
            system="be helpful",
            messages=[LLMMessage(role="user", content="hi")],
        )

        assert response.text == "Hello"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.model == "gemini-2.5-flash"
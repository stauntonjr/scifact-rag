from __future__ import annotations

import httpx

from scifact_rag.adapters.openai_compatible import OpenAiCompatibleGenerator
from scifact_rag.domain import SearchHit


def test_generator_disables_thinking_for_answer_content(monkeypatch) -> None:
    request_json = {}

    def fake_post(url, *, headers, json, timeout):
        request_json.update(json)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Supported [42]"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    generator = OpenAiCompatibleGenerator(base_url="http://generator.test/v1", model="test-model")

    result = generator.generate("question", [SearchHit("42", "title", "evidence", 0.9)])

    assert result == "Supported [42]"
    assert request_json["chat_template_kwargs"] == {"enable_thinking": False}
    assert "Do not turn associations or animal-model" in request_json["messages"][0]["content"]


def test_generator_retains_server_reported_prompt_and_generated_tokens(monkeypatch) -> None:
    def fake_post(url, *, headers, json, timeout):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Supported [42]"}}],
                "usage": {"prompt_tokens": 137, "completion_tokens": 9, "total_tokens": 146},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    generator = OpenAiCompatibleGenerator(base_url="http://generator.test/v1", model="test-model")

    result = generator.generate_with_metrics(
        "question",
        [SearchHit("42", "title", "evidence", 0.9)],
    )

    assert result.text == "Supported [42]"
    assert result.input_tokens == 137
    assert result.generated_tokens == 9

import json

import httpx

from app.services.llm.openai_compatible import OpenAICompatibleLLMProvider


def test_openai_compatible_provider_skips_without_api_key() -> None:
    provider = OpenAICompatibleLLMProvider(
        base_url="https://example.test/v1",
        api_key=None,
        model="test-model",
    )

    result = provider.analyze({"report_date": "2026-05-25"})

    assert result.status == "skipped"
    assert result.output is None
    assert result.error is None


def test_openai_compatible_provider_parses_response() -> None:
    output = {
        "summary": "Sales are stable.",
        "findings": [
            {
                "title": "Review sales",
                "severity": "info",
                "evidence_refs": ["report:2026-05-25"],
                "reasoning": "Normal demand in the normalized report.",
                "recommended_human_actions": ["Review store summary"],
                "human_review_required": True,
            }
        ],
        "data_quality_notes": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://example.test/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(output),
                        }
                    }
                ]
            },
        )

    provider = OpenAICompatibleLLMProvider(
        base_url="https://example.test/v1",
        api_key="secret",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )

    result = provider.analyze(
        {
            "report_date": "2026-05-25",
            "evidence_ids": ["report:2026-05-25"],
        }
    )

    assert result.status == "succeeded"
    assert result.output == output
    assert result.error is None


def test_openai_compatible_provider_returns_failure_without_raising() -> None:
    provider = OpenAICompatibleLLMProvider(
        base_url="https://example.test/v1",
        api_key="secret",
        model="test-model",
        transport=httpx.MockTransport(lambda _request: httpx.Response(500, text="nope")),
    )

    result = provider.analyze(
        {
            "report_date": "2026-05-25",
            "evidence_ids": ["report:2026-05-25"],
        }
    )

    assert result.status == "failed"
    assert result.output is None
    assert result.error

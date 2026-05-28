import json
from dataclasses import dataclass

import httpx

from app.domain.enums import LLMStatus
from app.services.llm.validator import validate_llm_output


@dataclass(frozen=True)
class LLMAnalysisResult:
    status: str
    output: dict[str, object] | None
    error: str | None


class OpenAICompatibleLLMProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout_seconds: int = 30,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def analyze(self, snapshot: dict[str, object]) -> LLMAnalysisResult:
        if not self.api_key:
            return LLMAnalysisResult(status=LLMStatus.SKIPPED.value, output=None, error=None)

        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "Return JSON with summary and findings. "
                                    "All recommendations must require human review."
                                ),
                            },
                            {
                                "role": "user",
                                "content": json.dumps(snapshot, ensure_ascii=False),
                            },
                        ],
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            validated = validate_llm_output(parsed, snapshot)
        except Exception as exc:
            return LLMAnalysisResult(
                status=LLMStatus.FAILED.value,
                output=None,
                error=str(exc),
            )

        return LLMAnalysisResult(
            status=LLMStatus.SUCCEEDED.value,
            output=validated,
            error=None,
        )

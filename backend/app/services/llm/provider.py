from typing import Protocol


class LLMProvider(Protocol):
    def analyze(self, snapshot: dict[str, object]) -> dict[str, object]:
        raise NotImplementedError


class MockLLMProvider:
    def analyze(self, snapshot: dict[str, object]) -> dict[str, object]:
        report_date = str(snapshot["report_date"])
        return {
            "summary": f"Daily report for {report_date} is ready for review.",
            "findings": [
                {
                    "title": "Review daily changes",
                    "evidence_refs": [f"report:{report_date}"],
                    "possible_causes": ["Imported report data changed from prior day"],
                    "recommended_human_actions": ["Review flagged stores before taking action"],
                    "risk_level": "medium",
                    "confidence": "medium",
                    "human_review_required": True,
                }
            ],
        }

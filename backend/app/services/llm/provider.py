from typing import Protocol


class LLMProvider(Protocol):
    def analyze(self, snapshot: dict[str, object]) -> dict[str, object]:
        raise NotImplementedError


class MockLLMProvider:
    def analyze(self, snapshot: dict[str, object]) -> dict[str, object]:
        report_date = str(snapshot["report_date"])
        evidence_ids = list(snapshot.get("evidence_ids", [f"report:{report_date}"]))
        return {
            "summary": f"Daily report for {report_date} is ready for review.",
            "findings": [
                {
                    "title": "Review daily changes",
                    "severity": "warning",
                    "evidence_refs": evidence_ids[:1],
                    "reasoning": "Imported report data changed from the normalized business data.",
                    "recommended_human_actions": ["Review flagged stores before taking action."],
                    "human_review_required": True,
                }
            ],
            "data_quality_notes": list(snapshot.get("warnings", [])),
        }

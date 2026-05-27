from datetime import date

from app.schemas.reports import DailyReportDocument
from app.services.llm.provider import MockLLMProvider
from app.services.llm.snapshot import build_llm_snapshot
from app.services.llm.validator import validate_llm_output


def test_build_llm_snapshot_uses_report_data() -> None:
    report = DailyReportDocument(
        report_date=date(2026, 5, 25),
        store_summaries=[],
        totals={},
        warnings=[],
    )

    snapshot = build_llm_snapshot(report)

    assert snapshot["report_date"] == "2026-05-25"
    assert snapshot["warnings"] == []


def test_mock_llm_provider_returns_valid_output() -> None:
    output = MockLLMProvider().analyze({"report_date": "2026-05-25", "warnings": []})

    validated = validate_llm_output(output, snapshot={"evidence_ids": ["report:2026-05-25"]})

    assert validated["summary"]
    assert validated["findings"][0]["human_review_required"] is True


def test_validator_rejects_automatic_operation_recommendation() -> None:
    output = {
        "summary": "Unsafe",
        "findings": [
            {
                "title": "Auto change bid",
                "evidence_refs": ["report:2026-05-25"],
                "possible_causes": ["High ACOS"],
                "recommended_human_actions": ["Automatically change bid to 0.5"],
                "risk_level": "high",
                "confidence": "medium",
                "human_review_required": True,
            }
        ],
    }

    try:
        validate_llm_output(output, snapshot={"evidence_ids": ["report:2026-05-25"]})
    except ValueError as exc:
        assert "automatic" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError")

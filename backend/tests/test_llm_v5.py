from app.services.llm.output_schema import validate_daily_report_analysis
from app.services.llm.prompt_registry import load_prompt


def test_prompt_registry_loads_daily_report_v1() -> None:
    prompt = load_prompt("daily_report_v1")

    assert prompt.prompt_version == "daily_report_v1"
    assert "human review" in prompt.system_prompt.lower()
    assert "{{ snapshot_json }}" in prompt.user_prompt


def test_llm_schema_accepts_evidence_backed_output() -> None:
    output = {
        "summary": "Sales are stable.",
        "findings": [
            {
                "title": "Review SKU movement",
                "severity": "warning",
                "evidence_refs": ["store:1:marketplace:1:2026-05-20"],
                "reasoning": "Units changed from the imported report.",
                "recommended_human_actions": ["Review SKU level sales before changing anything."],
                "human_review_required": True,
            }
        ],
        "data_quality_notes": ["No freshness warnings."],
    }

    validated = validate_daily_report_analysis(
        output,
        evidence_ids={"store:1:marketplace:1:2026-05-20"},
    )

    assert validated.summary == "Sales are stable."
    assert validated.findings[0].severity == "warning"


def test_llm_schema_rejects_automatic_operations() -> None:
    output = {
        "summary": "Unsafe.",
        "findings": [
            {
                "title": "Unsafe action",
                "severity": "critical",
                "evidence_refs": ["store:1:marketplace:1:2026-05-20"],
                "reasoning": "The model tried to operate Amazon.",
                "recommended_human_actions": ["Automatically change price to 9.99."],
                "human_review_required": True,
            }
        ],
        "data_quality_notes": [],
    }

    try:
        validate_daily_report_analysis(
            output,
            evidence_ids={"store:1:marketplace:1:2026-05-20"},
        )
    except ValueError as exc:
        assert "automatic" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError")

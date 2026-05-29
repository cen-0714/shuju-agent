from app.services.llm.output_schema import validate_daily_report_analysis


def validate_llm_output(
    output: dict[str, object],
    snapshot: dict[str, object],
) -> dict[str, object]:
    validated = validate_daily_report_analysis(
        output,
        evidence_ids={str(item) for item in snapshot.get("evidence_ids", [])},
    )
    return validated.model_dump(mode="json")

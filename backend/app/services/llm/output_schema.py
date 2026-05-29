from pydantic import BaseModel, Field, field_validator

BLOCKED_ACTION_WORDS = (
    "automatically change",
    "auto change",
    "change bid",
    "change price",
    "edit listing",
    "pause campaign",
    "increase budget",
    "modify inventory",
)


class DailyReportFinding(BaseModel):
    title: str
    severity: str = Field(pattern="^(info|warning|critical)$")
    evidence_refs: list[str]
    reasoning: str
    recommended_human_actions: list[str]
    human_review_required: bool

    @field_validator("human_review_required")
    @classmethod
    def must_require_human_review(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Finding must require human review")
        return value


class DailyReportAnalysis(BaseModel):
    summary: str
    findings: list[DailyReportFinding]
    data_quality_notes: list[str] = Field(default_factory=list)


def validate_daily_report_analysis(
    output: dict[str, object],
    *,
    evidence_ids: set[str],
) -> DailyReportAnalysis:
    parsed = DailyReportAnalysis.model_validate(output)
    for finding in parsed.findings:
        if not finding.evidence_refs:
            raise ValueError("Finding missing evidence references")
        unknown_refs = set(finding.evidence_refs) - evidence_ids
        if unknown_refs:
            unknown_refs_text = ", ".join(sorted(unknown_refs))
            raise ValueError(f"Finding references evidence outside snapshot: {unknown_refs_text}")
        actions_text = " ".join(finding.recommended_human_actions).lower()
        if any(blocked in actions_text for blocked in BLOCKED_ACTION_WORDS):
            raise ValueError("LLM output includes automatic Amazon operation recommendation")
    return parsed

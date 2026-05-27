BLOCKED_ACTION_WORDS = (
    "automatically change",
    "auto change",
    "change bid",
    "change price",
    "edit listing",
    "pause campaign",
    "increase budget",
)


def validate_llm_output(
    output: dict[str, object],
    snapshot: dict[str, object],
) -> dict[str, object]:
    if not isinstance(output.get("summary"), str) or not output["summary"]:
        raise ValueError("LLM output missing summary")
    findings = output.get("findings")
    if not isinstance(findings, list):
        raise ValueError("LLM output missing findings")

    evidence_ids = set(snapshot.get("evidence_ids", []))
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("Finding must be an object")
        refs = finding.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            raise ValueError("Finding missing evidence references")
        if any(ref not in evidence_ids for ref in refs):
            raise ValueError("Finding references evidence outside snapshot")
        actions = finding.get("recommended_human_actions")
        if not isinstance(actions, list) or not actions:
            raise ValueError("Finding missing recommended human actions")
        joined_actions = " ".join(str(action).lower() for action in actions)
        if any(blocked in joined_actions for blocked in BLOCKED_ACTION_WORDS):
            raise ValueError("LLM output includes automatic Amazon operation recommendation")
        if finding.get("human_review_required") is not True:
            raise ValueError("Finding must require human review")
    return output

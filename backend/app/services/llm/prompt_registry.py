from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptTemplate:
    prompt_version: str
    output_schema_version: str
    system_prompt: str
    user_prompt: str


PROMPT_ROOT = Path(__file__).parent / "prompts"


class PromptNotFoundError(Exception):
    pass


def load_prompt(prompt_version: str) -> PromptTemplate:
    if prompt_version != "daily_report_v1":
        raise PromptNotFoundError(f"Prompt version not found: {prompt_version}")
    prompt_dir = PROMPT_ROOT / prompt_version
    return PromptTemplate(
        prompt_version=prompt_version,
        output_schema_version="daily_report_analysis.v1",
        system_prompt=(prompt_dir / "system.md").read_text(encoding="utf-8").strip(),
        user_prompt=(prompt_dir / "user.md").read_text(encoding="utf-8").strip(),
    )

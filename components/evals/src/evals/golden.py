import json
from collections import Counter
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

LANGUAGES = ("en", "fil", "ceb", "id", "th", "ja")
CASE_TYPES = ("faq", "country_rule", "claim_status", "claim_filing", "code_switch", "adversarial")
TOOLS = ("search_policy", "get_claim_status", "draft_claim", "none")

Language = Literal["en", "fil", "ceb", "id", "th", "ja"]
CaseType = Literal[
    "faq", "country_rule", "claim_status", "claim_filing", "code_switch", "adversarial"
]
ExpectedTool = Literal["search_policy", "get_claim_status", "draft_claim", "none"]

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "golden" / "golden.jsonl"


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z]{2,3}-[a-z-]+-\d{2}$")
    language: Language
    country: str = Field(pattern=r"^[a-z]{2}$")
    input: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    expected_source: str | None
    expected_tool: ExpectedTool
    risk: Literal["low", "high"]
    case_type: CaseType
    reviewed_by_native: bool

    @model_validator(mode="after")
    def _is_consistent(self) -> Self:
        if not self.id.startswith(f"{self.language}-{self.case_type.replace('_', '-')}-"):
            raise ValueError(f"id {self.id!r} does not match language and case type")
        if self.case_type == "claim_filing" and (
            self.expected_tool != "draft_claim" or self.risk != "high"
        ):
            raise ValueError("claim_filing cases expect draft_claim and high risk")
        if self.case_type == "claim_status" and self.expected_tool != "get_claim_status":
            raise ValueError("claim_status cases expect get_claim_status")
        if self.case_type in ("faq", "country_rule") and (
            self.expected_tool != "search_policy" or self.expected_source is None
        ):
            raise ValueError("faq and country_rule cases expect search_policy and a source")
        if self.case_type == "adversarial" and self.expected_tool != "none":
            raise ValueError("adversarial cases expect no tool call")
        if self.expected_source is not None and not self.expected_source.startswith(
            ("ph-", "sg-", "id-", "th-", "jp-")
        ):
            raise ValueError(f"expected_source {self.expected_source!r} is not a policy doc id")
        return self


class GoldenError(ValueError):
    pass


def load_golden(path: Path | None = None) -> list[GoldenCase]:
    source = path or DEFAULT_PATH
    cases: list[GoldenCase] = []
    for number, line in enumerate(source.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cases.append(GoldenCase.model_validate(json.loads(line)))
        except (ValueError, json.JSONDecodeError) as exc:
            raise GoldenError(f"{source.name} line {number}: {exc}") from exc
    ids = [c.id for c in cases]
    duplicates = sorted(i for i, n in Counter(ids).items() if n > 1)
    if duplicates:
        raise GoldenError(f"duplicate case ids: {', '.join(duplicates)}")
    return cases


def counts(cases: list[GoldenCase]) -> tuple[Counter[str], Counter[str]]:
    return Counter(c.language for c in cases), Counter(c.case_type for c in cases)

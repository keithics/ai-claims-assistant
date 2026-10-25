import re
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Tier = Literal["small", "large"]
DeploymentTier = Literal["small", "large", "embedding"]

_LANGUAGE = re.compile(r"^[a-z]{2,3}$")
_CODE = re.compile(r"^[a-z]{2}$")


class CountryPack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    name: str = Field(min_length=1)
    languages: list[str] = Field(min_length=1)
    azure_region: str = Field(min_length=1)
    deployment_type: Literal["regional", "global", "datazone"]
    allowed_model_tiers: list[Tier] = Field(min_length=1)
    search_filter: str
    log_prompts: bool
    retention_days: int = Field(gt=0)
    monthly_budget_usd: Decimal = Field(gt=0)
    human_handoff: str = Field(min_length=1)
    regulatory_notes_ref: str = Field(min_length=1)

    @field_validator("code")
    @classmethod
    def _code_is_two_lowercase_letters(cls, value: str) -> str:
        if not _CODE.match(value):
            raise ValueError("must be two lowercase letters, for example 'ph'")
        return value

    @field_validator("languages")
    @classmethod
    def _languages_are_codes(cls, value: list[str]) -> list[str]:
        bad = [lang for lang in value if not _LANGUAGE.match(lang)]
        if bad:
            raise ValueError(f"language codes must be 2-3 lowercase letters, got {bad}")
        return value

    @model_validator(mode="after")
    def _search_filter_matches_code(self) -> Self:
        expected = f"country eq '{self.code}'"
        if self.search_filter != expected:
            raise ValueError(f"search_filter must be {expected!r}, got {self.search_filter!r}")
        return self


class PriceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_per_1m: Decimal = Field(ge=0)
    cached_input_per_1m: Decimal = Field(ge=0)
    output_per_1m: Decimal = Field(ge=0)


class DeploymentEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tier: DeploymentTier
    model: str = Field(min_length=1)
    version: str = Field(min_length=1)
    prices: PriceEntry


class ModelCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    deployments: dict[str, DeploymentEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _has_small_and_large(self) -> Self:
        tiers = {d.tier for d in self.deployments.values()}
        missing = {"small", "large"} - tiers
        if missing:
            raise ValueError(f"no deployment for tier(s): {', '.join(sorted(missing))}")
        return self

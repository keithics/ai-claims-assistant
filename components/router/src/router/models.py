import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Tier = Literal["small", "large"]
Intent = Literal["faq", "country_rule", "claim_status", "claim_filing", "other"]
Risk = Literal["low", "high"]
BudgetState = Literal["ok", "warn", "exceeded"]
Decision = Literal["small", "large", "handoff"]

INTENTS: tuple[Intent, ...] = ("faq", "country_rule", "claim_status", "claim_filing", "other")
_LANGUAGE = re.compile(r"^[a-z]{2,3}$")
_COUNTRY = re.compile(r"^[a-z]{2}$")


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    country: str
    language: str
    intent: Intent
    risk: Risk
    allowed_tiers: tuple[Tier, ...] = ("small", "large")


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tier: Decision
    deployment: str | None
    reason: str
    fallbacks: tuple[str, ...] = ()
    max_output_tokens: int | None = None


class OutputLimit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    small: int = Field(gt=0)
    large: int = Field(gt=0)


class RoutingRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    language: str | None = None
    intent: Intent | None = None
    country: str | None = None
    tier: Tier
    reason: str = Field(min_length=1)

    @field_validator("language")
    @classmethod
    def _language_is_a_code(cls, value: str | None) -> str | None:
        if value is not None and not _LANGUAGE.match(value):
            raise ValueError("language must be 2-3 lowercase letters")
        return value

    @field_validator("country")
    @classmethod
    def _country_is_a_code(cls, value: str | None) -> str | None:
        if value is not None and not _COUNTRY.match(value):
            raise ValueError("country must be two lowercase letters")
        return value

    @model_validator(mode="after")
    def _has_a_condition(self) -> Self:
        if self.language is None and self.intent is None and self.country is None:
            raise ValueError("a rule needs at least one of language, intent or country")
        return self


class RoutingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(ge=1)
    default_tier: Tier = "small"
    deployments: dict[Tier, list[str]]
    rules: list[RoutingRule] = Field(default_factory=list)
    output_limits: dict[Intent, OutputLimit]

    @model_validator(mode="after")
    def _is_complete(self) -> Self:
        for tier in ("small", "large"):
            names = self.deployments.get(tier)
            if not names:
                raise ValueError(f"deployments needs at least one entry for tier {tier!r}")
            if len(set(names)) != len(names):
                raise ValueError(f"deployments for tier {tier!r} repeat a name")
        missing = [i for i in INTENTS if i not in self.output_limits]
        if missing:
            raise ValueError(f"output_limits is missing intent(s): {', '.join(missing)}")
        return self

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

import httpx
from openai import OpenAI

METRICS = ("groundedness", "relevance", "coherence")

PROMPTS: Mapping[str, str] = {
    "groundedness": (
        "You grade whether an assistant's ANSWER is supported by the CONTEXT documents. "
        "5 = every factual claim is in the context; 3 = partly supported; 1 = contradicts or "
        "invents facts. If the answer only refuses, asks a question or hands off, and states "
        "no unsupported facts, give 5. If there is no context, grade 5 only when the answer "
        "makes no factual claims about policies."
    ),
    "relevance": (
        "You grade whether the ANSWER addresses the QUESTION and agrees with the REFERENCE "
        "facts. 5 = fully answers and consistent with the reference; 3 = partly; 1 = off topic "
        "or contradicts the reference. When the reference describes a refusal or a draft that "
        "needs approval, the answer must show that behaviour."
    ),
    "coherence": (
        "You grade whether the ANSWER is clear, well formed and easy to follow in its own "
        "language. 5 = clear and fluent; 3 = understandable but awkward; 1 = confusing."
    ),
}
FORMAT = 'Reply with JSON only: {"score": <integer 1-5>, "reason": "<one short sentence>"}.'


@dataclass(frozen=True)
class JudgeScore:
    score: float
    reason: str


class Judge(Protocol):
    def grade(
        self,
        metric: str,
        *,
        country: str,
        question: str,
        answer: str,
        context: str,
        reference: str,
    ) -> JudgeScore: ...


def parse_score(text: str) -> JudgeScore:
    try:
        data = json.loads(text)
        value = int(data["score"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"judge reply is not the expected JSON: {text[:120]!r}") from exc
    if not 1 <= value <= 5:
        raise ValueError(f"judge score {value} is outside 1-5")
    return JudgeScore((value - 1) / 4, str(data.get("reason", ""))[:200])


class GatewayJudge:
    def __init__(
        self,
        gateway_url: str,
        keys: Mapping[str, str],
        *,
        tier: str = "small",
        deployment: str = "small-a",
        api_version: str = "2024-10-21",
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base = f"{gateway_url.rstrip('/')}/{tier}"
        self._keys = dict(keys)
        self._tier = tier
        self._deployment = deployment
        self._api_version = api_version
        self._http_client = http_client
        self._clients: dict[str, OpenAI] = {}

    def _client(self, country: str) -> OpenAI:
        key = self._keys.get(country)
        if key is None:
            raise ValueError(f"no gateway key for country {country!r}")
        if country not in self._clients:
            self._clients[country] = OpenAI(
                base_url=self._base,
                api_key=key,
                http_client=self._http_client,  # type: ignore[arg-type]
                max_retries=2,
                default_query={"api-version": self._api_version},
                default_headers={
                    "api-key": key,
                    "x-country": country,
                    "x-app": "evals",
                    "x-model": self._deployment,
                    "x-route-tier": self._tier,
                },
            )
        return self._clients[country]

    def grade(
        self,
        metric: str,
        *,
        country: str,
        question: str,
        answer: str,
        context: str,
        reference: str,
    ) -> JudgeScore:
        body = (
            f"QUESTION:\n{question}\n\nREFERENCE:\n{reference}\n\n"
            f"CONTEXT:\n{context or '(none)'}\n\nANSWER:\n{answer}\n\n{FORMAT}"
        )
        response = self._client(country).chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": PROMPTS[metric]},
                {"role": "user", "content": body},
            ],
            max_completion_tokens=200,
            response_format={"type": "json_object"},
        )
        return parse_score(response.choices[0].message.content or "")

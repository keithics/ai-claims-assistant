from collections.abc import Sequence
from dataclasses import dataclass

from rag.chunking import estimate_tokens
from rag.retriever import RetrievedChunk

DEDUPE_OVERLAP = 0.8


@dataclass(frozen=True)
class TrimResult:
    chunks: list[RetrievedChunk]
    dropped_duplicates: int
    dropped_over_budget: int

    @property
    def changed(self) -> bool:
        return bool(self.dropped_duplicates or self.dropped_over_budget)


def _words(text: str) -> set[str]:
    return set(text.lower().split())


def _overlap(a: str, b: str) -> float:
    left, right = _words(a), _words(b)
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def trim_chunks(
    chunks: Sequence[RetrievedChunk],
    *,
    max_chunks: int,
    max_tokens: int,
    dedupe: bool = True,
) -> TrimResult:
    kept: list[RetrievedChunk] = []
    duplicates = 0
    over_budget = 0
    used = 0
    for chunk in chunks:
        if dedupe and any(_overlap(chunk.text, k.text) >= DEDUPE_OVERLAP for k in kept):
            duplicates += 1
            continue
        cost = estimate_tokens(chunk.text)
        if len(kept) >= max_chunks or (kept and used + cost > max_tokens):
            over_budget += 1
            continue
        kept.append(chunk)
        used += cost
    return TrimResult(kept, duplicates, over_budget)

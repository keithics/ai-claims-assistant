from dataclasses import dataclass, field
from typing import Any

from agent_app.tools.claims_client import ClaimsGateway
from rag import RetrievedChunk, Retriever


@dataclass(frozen=True)
class ToolOutcome:
    model_text: str
    ok: bool = True
    draft: dict[str, Any] | None = None


@dataclass
class ToolContext:
    country: str
    language: str
    retriever: Retriever
    claims: ClaimsGateway
    sources: list[RetrievedChunk] = field(default_factory=list)

    def source_number(self, chunk: RetrievedChunk) -> int:
        for index, known in enumerate(self.sources, start=1):
            if known.id == chunk.id:
                return index
        self.sources.append(chunk)
        return len(self.sources)

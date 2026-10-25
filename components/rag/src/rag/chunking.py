import math
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

TokenCounter = Callable[[str], int]

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_JA_ENDERS = "。！？"
_CLOSERS = "」』）)"


def estimate_tokens(text: str) -> int:
    total = 0.0
    for char in text:
        if char.isspace():
            total += 0.1
            continue
        name = unicodedata.name(char, "")
        if name.startswith("CJK UNIFIED") or name.startswith("CJK COMPATIBILITY"):
            total += 1.0
        elif name.startswith(("HIRAGANA", "KATAKANA")):
            total += 0.75
        elif name.startswith("THAI"):
            total += 0.6
        else:
            total += 0.25
    return math.ceil(total)


def split_sentences(line: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    i = 0
    n = len(line)
    while i < n:
        char = line[i]
        if char in _JA_ENDERS:
            j = i + 1
            while j < n and line[j] in _JA_ENDERS + _CLOSERS:
                j += 1
            sentences.append(line[start:j])
            start = i = j
            continue
        if char in ".!?" and (i + 1 == n or line[i + 1].isspace()):
            token_start = line.rfind(" ", start, i) + 1 or start
            if char == "." and token_start == start and line[token_start:i].isdigit():
                i += 1
                continue
            j = i + 1
            sentences.append(line[start:j])
            while j < n and line[j].isspace():
                j += 1
            start = i = j
            continue
        i += 1
    sentences.append(line[start:])
    return [s.strip() for s in sentences if s.strip()]


def _pack_words(text: str, max_tokens: int, counter: TokenCounter) -> list[str]:
    pieces: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if current and counter(candidate) > max_tokens:
            pieces.append(current)
            current = word
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _hard_split(text: str, max_tokens: int, counter: TokenCounter) -> list[str]:
    pieces: list[str] = []
    current = ""
    for char in text:
        if current and counter(current + char) > max_tokens:
            pieces.append(current)
            current = char
        else:
            current += char
    if current:
        pieces.append(current)
    return pieces


def split_oversized(unit: str, max_tokens: int, counter: TokenCounter) -> list[str]:
    if counter(unit) <= max_tokens:
        return [unit]
    pieces: list[str] = []
    for part in _pack_words(unit, max_tokens, counter):
        pieces.extend(
            _hard_split(part, max_tokens, counter) if counter(part) > max_tokens else [part]
        )
    return pieces


@dataclass(frozen=True)
class Chunk:
    index: int
    heading: str
    text: str
    tokens: int


@dataclass
class _Section:
    heading: str
    units: list[str]


def _sections(body: str) -> list[_Section]:
    sections: list[_Section] = []
    stack: list[tuple[int, str]] = []
    current: _Section | None = None
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _HEADING.match(line)
        if match:
            level = len(match.group(1))
            stack = [(lvl, text) for lvl, text in stack if lvl < level]
            stack.append((level, line))
            current = _Section("\n".join(text for _, text in stack), [])
            sections.append(current)
            continue
        if current is None:
            current = _Section("", [])
            sections.append(current)
        current.units.extend(split_sentences(line))
    return [s for s in sections if s.units]


def chunk_markdown(
    body: str,
    *,
    max_tokens: int = 300,
    overlap_tokens: int | None = None,
    counter: TokenCounter = estimate_tokens,
) -> list[Chunk]:
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if overlap_tokens is None:
        overlap_tokens = min(40, max_tokens // 5)
    if not 0 <= overlap_tokens < max_tokens:
        raise ValueError("overlap_tokens must be at least 0 and less than max_tokens")

    chunks: list[Chunk] = []

    def render(heading: str, units: list[str]) -> str:
        text = "\n".join(units)
        return f"{heading}\n\n{text}" if heading else text

    for section in _sections(body):
        heading_cost = counter(section.heading) if section.heading else 0
        budget = max(1, max_tokens - heading_cost)
        units: list[str] = []
        for sentence in section.units:
            units.extend(split_oversized(sentence, budget, counter))

        current: list[str] = []
        for unit in units:
            if current and counter("\n".join([*current, unit])) > budget:
                text = render(section.heading, current)
                chunks.append(Chunk(len(chunks), section.heading, text, counter(text)))
                carry: list[str] = []
                carried = 0
                for previous in reversed(current):
                    cost = counter(previous)
                    if carried + cost > overlap_tokens:
                        break
                    carry.insert(0, previous)
                    carried += cost
                while carry and counter("\n".join([*carry, unit])) > budget:
                    carry.pop(0)
                current = carry
            current.append(unit)
        if current:
            text = render(section.heading, current)
            chunks.append(Chunk(len(chunks), section.heading, text, counter(text)))
    return chunks

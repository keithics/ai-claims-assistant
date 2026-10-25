from collections.abc import Iterable

LEVERS = (
    "prompt_cache_key",
    "retrieval_trim",
    "history_cap",
    "compact_prompts",
    "output_limits",
    "concise_style",
)


class UnknownLeverError(ValueError):
    pass


def parse_levers(names: Iterable[str]) -> frozenset[str]:
    wanted = [n.strip() for n in names if n.strip()]
    unknown = sorted(set(wanted) - set(LEVERS))
    if unknown:
        raise UnknownLeverError(
            f"unknown lever(s): {', '.join(unknown)}; known: {', '.join(LEVERS)}"
        )
    return frozenset(wanted)

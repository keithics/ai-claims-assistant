import re

_START = r"(?<![A-Za-z0-9])"
_END = r"(?![A-Za-z0-9])"

EMAIL = "[EMAIL]"
POLICY = "[POLICY]"
CLAIM_ID = "[CLAIM_ID]"
NATIONAL_ID = "[NATIONAL_ID]"
PHONE = "[PHONE]"

_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"),
        EMAIL,
    ),
    (
        re.compile(rf"{_START}POL-(?:[A-Z]{{2}}-)?[0-9]{{5,12}}{_END}"),
        POLICY,
    ),
    (
        re.compile(rf"{_START}[A-Z]{{2}}-[0-9]{{3,6}}{_END}"),
        CLAIM_ID,
    ),
    (
        re.compile(
            rf"{_START}(?:"
            r"[0-9]-[0-9]{4}-[0-9]{5}-[0-9]{2}-[0-9]"
            r"|[0-9]{4}(?:[ -]?[0-9]{4}){3}"
            r"|[0-9]{13}"
            r"|(?!0)[0-9]{4}-[0-9]{7}-[0-9]"
            r"|(?!0)[0-9]{4}[ -]?[0-9]{4}[ -]?[0-9]{4}"
            r"|[STFGM][0-9]{7}[A-Z]"
            rf"){_END}"
        ),
        NATIONAL_ID,
    ),
    (
        re.compile(
            r"(?:(?<![A-Za-z0-9+])\+[0-9]{1,3}[ .-]?\(?[0-9]{1,4}\)?"
            rf"(?:[ .-]?[0-9]{{2,4}}){{2,3}}{_END}"
            rf"|{_START}0[0-9]{{1,3}}[ .-]?[0-9]{{3,4}}[ .-]?[0-9]{{3,4}}{_END}"
            rf"|{_START}[689][0-9]{{3}}[ -]?[0-9]{{4}}{_END})"
        ),
        PHONE,
    ),
)


def redact(text: str) -> str:
    for pattern, placeholder in _RULES:
        text = pattern.sub(placeholder, text)
    return text

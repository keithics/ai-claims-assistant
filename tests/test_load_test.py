import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "load_test", Path(__file__).resolve().parent.parent / "tools" / "load_test.py"
)
assert spec and spec.loader
lt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lt)


def result(country: str, statuses: list[int], deployment: str = "") -> "lt.CountryResult":
    r = lt.CountryResult(country, 1.0)
    r.samples = [
        lt.Sample(s, 0.5 + i / 10, deployment, 100 if s == 200 else 0)
        for i, s in enumerate(statuses)
    ]
    return r


def test_rates_are_parsed() -> None:
    assert lt.parse_rates("ph=3, SG=0.5") == {"ph": 3.0, "sg": 0.5}


@pytest.mark.parametrize("text", ["ph", "ph=", "ph=0", "ph=-1", "=2"])
def test_bad_rates_are_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        lt.parse_rates(text)


def test_percentiles() -> None:
    assert lt.percentile([], 0.5) == 0.0
    assert lt.percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert lt.percentile([1, 2, 3, 4, 5], 0.95) == 5


def test_counts_and_classification() -> None:
    ph = result("ph", [200, 200, 429, 429, 503])
    sg = result("sg", [200, 200, 200])
    assert (ph.ok, ph.limited, ph.other, ph.tokens) == (2, 2, 1, 200)
    limited, healthy = lt.classify([ph, sg])
    assert limited == ["ph"] and healthy == ["sg"]


def test_report_names_who_was_limited_and_who_kept_working() -> None:
    report = lt.render(
        [result("ph", [200, 429], "small-a"), result("sg", [200, 200], "small-b")],
        60,
        300,
        "https://gw",
    )
    assert "Hit their token limit: ph." in report
    assert "Kept working with no 429: sg." in report
    assert "small-a x2" in report and "small-b x2" in report

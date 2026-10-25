import json
import re
from pathlib import Path

import pytest

from telemetry.workbook import KQL_DIR, OUTPUT, VIEWS, build_workbook, read_query, render

KQL_FILES = sorted(KQL_DIR.glob("*.kql"))


def test_the_committed_workbook_is_current() -> None:
    assert OUTPUT.read_text(encoding="utf-8") == render(), (
        "run `python -m telemetry.workbook` and commit components/telemetry/workbook"
    )


def test_it_has_four_tabs_each_with_its_own_group() -> None:
    workbook = build_workbook()
    links = next(i for i in workbook["items"] if i["type"] == 11)["content"]["links"]
    assert [link["linkLabel"] for link in links] == ["Executive", "Cost", "Engineering", "Quality"]
    groups = [i for i in workbook["items"] if i["type"] == 12]
    assert [g["conditionalVisibility"]["value"] for g in groups] == [v[0] for v in VIEWS]
    assert all(g["content"]["items"] for g in groups)


def test_every_query_in_the_workbook_comes_from_a_kql_file() -> None:
    workbook = json.loads(OUTPUT.read_text(encoding="utf-8"))
    used = {
        item["content"]["query"]
        for group in workbook["items"]
        if group["type"] == 12
        for item in group["content"]["items"]
    }
    available = {read_query(path.stem) for path in KQL_FILES}
    assert used <= available


def test_queries_use_the_time_range_parameter_and_the_workspace_placeholder() -> None:
    text = OUTPUT.read_text(encoding="utf-8")
    assert "{TimeRange:start}" in text and "ago(30d)" not in text
    assert text.count("${workspace_id}") >= 6


@pytest.mark.parametrize("path", KQL_FILES, ids=lambda p: p.stem)
def test_each_query_is_well_formed(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count("(") == text.count(")")
    assert text.count('"') % 2 == 0
    assert not re.search(r"\$\{|%\{", text)
    code = [line for line in text.splitlines() if not line.startswith("//")]
    assert code and not any("\t" in line for line in code)


@pytest.mark.parametrize("path", KQL_FILES, ids=lambda p: p.stem)
def test_each_query_reads_only_the_span_and_gateway_tables(path: Path) -> None:
    tables = set(re.findall(r"\b(App[A-Z][A-Za-z]+)\b", path.read_text(encoding="utf-8")))
    assert tables <= {"AppDependencies", "AppRequests", "AppEvents", "AppRoleName"}


def test_the_budget_query_returns_spend_per_country() -> None:
    text = (KQL_DIR / "spend_by_country.kql").read_text(encoding="utf-8")
    assert "spend_usd" in text and "by country" in text and "startofmonth" in text

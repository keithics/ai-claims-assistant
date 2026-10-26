import re
from pathlib import Path

from country_packs import load_country_packs

DOC = Path(__file__).resolve().parent.parent / "docs" / "regulatory.md"
COLUMNS = ("code", "azure_region", "deployment_type", "log_prompts", "retention_days")


def settings_rows() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 7 and re.fullmatch(r"[a-z]{2}", cells[1]):
            rows[cells[1]] = cells
    return rows


def test_every_country_pack_has_a_row_and_every_row_matches_its_pack() -> None:
    packs = load_country_packs()
    rows = settings_rows()
    assert set(rows) == set(packs)
    for code, pack in packs.items():
        cells = rows[code]
        assert cells[0] == pack.name
        assert cells[2] == pack.azure_region
        assert cells[3] == pack.deployment_type
        assert cells[4] == str(pack.log_prompts).lower()
        assert cells[5] == str(pack.retention_days)
        assert cells[6] == f"{pack.monthly_budget_usd:g}"


def test_the_disclaimer_is_at_the_top_and_every_pack_anchor_exists() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "Not legal advice" in text.split("\n", 4)[2]
    for pack in load_country_packs().values():
        anchor = pack.regulatory_notes_ref.split("#", 1)[1]
        assert f"## {anchor.title()}" in text, anchor

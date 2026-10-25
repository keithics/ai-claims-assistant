import json
from pathlib import Path

from country_packs import load_country_packs
from evals.golden import load_golden
from rag import load_policy_documents

ROOT = Path(__file__).resolve().parent.parent
CASES = load_golden()


def test_every_expected_source_is_a_real_policy_document_of_that_country() -> None:
    docs = {d.doc_id: d for d in load_policy_documents(packs=load_country_packs())}
    for case in CASES:
        if case.expected_source is None:
            continue
        assert case.expected_source in docs, case.id
        assert docs[case.expected_source].country == case.country, case.id


def test_claim_numbers_in_status_cases_belong_to_the_case_country_and_exist() -> None:
    seeds = {}
    for code in ("ph", "sg", "id", "th", "jp"):
        data = json.loads(
            (ROOT / "components" / "claims_api" / "seed" / f"{code}.json").read_text()
        )
        seeds[code] = {c["claim_id"] for c in data["claims"]}
    for case in CASES:
        if case.case_type != "claim_status":
            continue
        claim = next(token for token in case.input.replace("。", " ").split() if "-10" in token)
        claim = claim.strip(".,?!、)")
        assert claim in seeds[case.country], case.id

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from country_packs import CountryPack, load_country_packs

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
_REQUIRED = ("country", "language", "title", "doc_id")


class DocumentError(ValueError):
    pass


@dataclass(frozen=True)
class PolicyDocument:
    country: str
    language: str
    title: str
    doc_id: str
    body: str
    path: Path


def default_policies_dir() -> Path:
    override = os.environ.get("RAG_POLICIES_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "policies"


def parse_document(path: Path, packs: dict[str, CountryPack]) -> PolicyDocument:
    match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    if match is None:
        raise DocumentError(f"{path}: missing front matter (--- block at the top)")
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise DocumentError(f"{path}: invalid front matter: {exc}") from exc
    if not isinstance(meta, dict):
        raise DocumentError(f"{path}: front matter must be a mapping")
    missing = [key for key in _REQUIRED if not meta.get(key)]
    if missing:
        raise DocumentError(f"{path}: front matter missing {', '.join(missing)}")
    values = {key: str(meta[key]) for key in _REQUIRED}
    country = values["country"]
    if country != path.parent.name:
        raise DocumentError(f"{path}: country {country!r} does not match its folder")
    if country not in packs:
        raise DocumentError(f"{path}: no country pack for {country!r}")
    if values["language"] not in packs[country].languages:
        raise DocumentError(
            f"{path}: language {values['language']!r} is not one of "
            f"{country}'s languages {packs[country].languages}"
        )
    if values["doc_id"] != path.stem:
        raise DocumentError(f"{path}: doc_id {values['doc_id']!r} does not match the file name")
    body = match.group(2).strip()
    if not body:
        raise DocumentError(f"{path}: empty document body")
    return PolicyDocument(
        country=country,
        language=values["language"],
        title=values["title"],
        doc_id=values["doc_id"],
        body=body,
        path=path,
    )


def load_policy_documents(
    policies_dir: Path | None = None,
    packs: dict[str, CountryPack] | None = None,
) -> list[PolicyDocument]:
    directory = policies_dir or default_policies_dir()
    country_packs = packs if packs is not None else load_country_packs()
    documents = [parse_document(path, country_packs) for path in sorted(directory.glob("*/*.md"))]
    ids = [d.doc_id for d in documents]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise DocumentError(f"duplicate doc_id: {', '.join(duplicates)}")
    return documents

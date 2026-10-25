import pytest

from rag import chunk_markdown, estimate_tokens, load_policy_documents, split_sentences
from rag.chunking import split_oversized

ENGLISH = """# Claim deadlines

## Reporting

Report the incident within 30 days. Late reports may be declined. Keep your receipts safe.
Call us if you are unsure!

## Payment

Approved claims are paid in 15 working days. We pay by bank transfer. Is your account active?
1. Send your bank details.
2. Wait for confirmation.
"""

JAPANESE = """# 請求の期限

## 連絡

事故の日から60日以内にご連絡ください。連絡が遅れた場合は、お支払いできないことがあります。必要書類をご用意ください!
本当にご不明ですか?いつでもお電話ください。

## 支払い

書類がそろってから30日以内にお支払いします。「ご確認ください。」と案内する場合があります。
お支払いは銀行振込です。
"""

THAI = """# กำหนดเวลาการเคลม

## การแจ้งเหตุ

- แจ้งเหตุภายใน 15 วัน นับจากวันเกิดเหตุ
- ส่งเอกสารประกอบทั้งหมดภายใน 45 วัน นับจากวันเกิดเหตุ
- การแจ้งล่าช้าอาจถูกปฏิเสธ เว้นแต่มีเหตุผลอันสมควร

## การจ่ายเงิน

- เคลมที่อนุมัติจะจ่ายภายใน 20 วันทำการ
- จ่ายโดยการโอนเงินเข้าบัญชีธนาคาร
"""


def sentence_set(body: str) -> set[str]:
    sentences: set[str] = set()
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            sentences.update(split_sentences(stripped))
    return sentences


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("One. Two! Three? Four", ["One.", "Two!", "Three?", "Four"]),
        ("事故です。連絡して!本当?はい。", ["事故です。", "連絡して!本当?はい。"]),
        ("請求できます。「確認を。」次です。", ["請求できます。", "「確認を。」", "次です。"]),
        ("Pay PHP 5,000. Then wait", ["Pay PHP 5,000.", "Then wait"]),
        ("1. Send details. 2. Wait", ["1. Send details.", "2. Wait"]),
        ("Rp 300.000 per klaim", ["Rp 300.000 per klaim"]),
        ("แจ้งเหตุภายใน 15 วัน", ["แจ้งเหตุภายใน 15 วัน"]),
        ("", []),
    ],
)
def test_split_sentences(line: str, expected: list[str]) -> None:
    assert split_sentences(line) == expected


def test_japanese_sentence_endings_split_without_spaces() -> None:
    assert split_sentences("A。B！C？D") == ["A。", "B！", "C？", "D"]


@pytest.mark.parametrize("body", [ENGLISH, JAPANESE, THAI], ids=["en", "ja", "th"])
@pytest.mark.parametrize("max_tokens", [60, 90, 150])
def test_chunks_respect_size_and_keep_sentences_whole(body: str, max_tokens: int) -> None:
    chunks = chunk_markdown(body, max_tokens=max_tokens, overlap_tokens=10)
    sentences = sentence_set(body)
    assert chunks
    for chunk in chunks:
        assert chunk.tokens == estimate_tokens(chunk.text)
        assert chunk.tokens <= max_tokens
        content = [ln for ln in chunk.text.splitlines() if ln.strip() and not ln.startswith("#")]
        assert content
        assert all(line in sentences for line in content), content


@pytest.mark.parametrize("body", [ENGLISH, JAPANESE, THAI], ids=["en", "ja", "th"])
def test_every_sentence_is_covered(body: str) -> None:
    chunks = chunk_markdown(body, max_tokens=60, overlap_tokens=10)
    covered = {line for c in chunks for line in c.text.splitlines()}
    assert sentence_set(body) <= covered


@pytest.mark.parametrize("body", [ENGLISH, JAPANESE, THAI], ids=["en", "ja", "th"])
def test_every_chunk_starts_with_its_heading(body: str) -> None:
    chunks = chunk_markdown(body, max_tokens=40, overlap_tokens=10)
    for chunk in chunks:
        assert chunk.heading.startswith("# ")
        assert chunk.text.startswith(chunk.heading)
    assert {c.heading.splitlines()[-1] for c in chunks} >= {
        line for line in body.splitlines() if line.startswith("## ")
    }


def test_heading_chain_keeps_the_document_title() -> None:
    chunks = chunk_markdown(ENGLISH, max_tokens=200)
    assert chunks[0].heading == "# Claim deadlines\n## Reporting"
    assert chunks[-1].heading == "# Claim deadlines\n## Payment"


def test_sections_do_not_share_chunks() -> None:
    chunks = chunk_markdown(ENGLISH, max_tokens=500)
    assert len(chunks) == 2
    assert "Payment" not in chunks[0].text
    assert "Report the incident" not in chunks[1].text


def test_overlap_repeats_the_last_sentences() -> None:
    body = "# T\n\n" + " ".join(f"Sentence number {i} is here." for i in range(12))
    chunks = chunk_markdown(body, max_tokens=24, overlap_tokens=10)
    assert len(chunks) > 2
    for before, after in zip(chunks, chunks[1:], strict=False):
        last = before.text.splitlines()[-1]
        assert last in after.text.splitlines()


def test_no_overlap_means_no_repeated_sentences() -> None:
    body = "# T\n\n" + " ".join(f"Sentence number {i} is here." for i in range(12))
    chunks = chunk_markdown(body, max_tokens=24, overlap_tokens=0)
    lines = [ln for c in chunks for ln in c.text.splitlines() if ln.startswith("Sentence")]
    assert len(lines) == len(set(lines)) == 12


def test_indexes_are_sequential() -> None:
    chunks = chunk_markdown(ENGLISH, max_tokens=30)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_oversized_sentence_is_split_on_words_then_characters() -> None:
    words = " ".join(["word"] * 40)
    pieces = split_oversized(words, 10, estimate_tokens)
    assert len(pieces) > 1
    assert all(estimate_tokens(p) <= 10 for p in pieces)
    assert " ".join(pieces) == words
    unbroken = "あ" * 100
    pieces = split_oversized(unbroken, 10, estimate_tokens)
    assert all(estimate_tokens(p) <= 10 for p in pieces)
    assert "".join(pieces) == unbroken


def test_body_before_any_heading_is_chunked() -> None:
    chunks = chunk_markdown("Just text. More text.", max_tokens=50)
    assert [c.heading for c in chunks] == [""]
    assert chunks[0].text == "Just text.\nMore text."


def test_empty_body_gives_no_chunks() -> None:
    assert chunk_markdown("\n\n") == []
    assert chunk_markdown("# Only a heading\n") == []


def test_japanese_costs_more_tokens_per_character_than_english() -> None:
    assert estimate_tokens("あ" * 40) > estimate_tokens("a" * 40)
    assert estimate_tokens("漢" * 40) > estimate_tokens("ก" * 40) > estimate_tokens("a" * 40)


@pytest.mark.parametrize(
    ("max_tokens", "overlap"),
    [(0, 0), (-5, 0), (10, -1), (10, 10), (10, 11)],
)
def test_invalid_settings_are_rejected(max_tokens: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        chunk_markdown(ENGLISH, max_tokens=max_tokens, overlap_tokens=overlap)


def test_real_policy_documents_chunk_within_the_limit() -> None:
    for doc in load_policy_documents():
        chunks = chunk_markdown(doc.body, max_tokens=120, overlap_tokens=20)
        assert chunks, doc.doc_id
        assert all(c.tokens <= 120 for c in chunks), doc.doc_id
        sentences = sentence_set(doc.body)
        for chunk in chunks:
            content = [
                ln for ln in chunk.text.splitlines() if ln.strip() and not ln.startswith("#")
            ]
            assert all(line in sentences for line in content), (doc.doc_id, content)

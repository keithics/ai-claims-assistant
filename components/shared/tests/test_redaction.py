import pytest

from shared import redact

EMAILS = [
    ("My email is anna.cruz+claims@example.com please", "My email is [EMAIL] please"),
    ("メールはtest@example.co.jpです", "メールは[EMAIL]です"),
    ("อีเมล somchai_k@example.th ครับ", "อีเมล [EMAIL] ครับ"),
    ("Kirim ke budi@mail.example.id.", "Kirim ke [EMAIL]."),
]

POLICY_NUMBERS = [
    ("Policy POL-PH-1234567 is active", "Policy [POLICY] is active"),
    ("Nomor polis POL-ID-20481234", "Nomor polis [POLICY]"),
    ("証券番号POL-JP-998877です", "証券番号[POLICY]です"),
    ("POL-123456", "[POLICY]"),
]

CLAIM_IDS = [
    ("Status of PH-1042?", "Status of [CLAIM_ID]?"),
    ("SG-2001 and TH-3300", "[CLAIM_ID] and [CLAIM_ID]"),
    ("請求JP-1042の状況", "請求[CLAIM_ID]の状況"),
    ("เคลม TH-1042 ครับ", "เคลม [CLAIM_ID] ครับ"),
    ("fixture ZZ-5001 works", "fixture [CLAIM_ID] works"),
]

PHONES = [
    ("Call +63 917 123 4567", "Call [PHONE]"),
    ("Call 0917 123 4567", "Call [PHONE]"),
    ("Call +65 9123 4567", "Call [PHONE]"),
    ("Call 9123 4567", "Call [PHONE]"),
    ("Hubungi +62 812-3456-7890", "Hubungi [PHONE]"),
    ("Hubungi 0812-3456-7890", "Hubungi [PHONE]"),
    ("Hubungi 081234567890", "Hubungi [PHONE]"),
    ("โทร 081-234-5678 ครับ", "โทร [PHONE] ครับ"),
    ("โทร +66 81 234 5678", "โทร [PHONE]"),
    ("電話は090-1234-5678です", "電話は[PHONE]です"),
    ("電話は03-1234-5678です", "電話は[PHONE]です"),
    ("TEL +81 90-1234-5678", "TEL [PHONE]"),
]

NATIONAL_IDS = [
    ("PhilSys 1234-5678901-2", "PhilSys [NATIONAL_ID]"),
    ("PhilSys 123456789012", "PhilSys [NATIONAL_ID]"),
    ("NRIC S1234567D", "NRIC [NATIONAL_ID]"),
    ("FIN G7654321K", "FIN [NATIONAL_ID]"),
    ("NIK 3201234567890123", "NIK [NATIONAL_ID]"),
    ("NIK 3201 2345 6789 0123", "NIK [NATIONAL_ID]"),
    ("บัตรประชาชน 1-2345-67890-12-3 ครับ", "บัตรประชาชน [NATIONAL_ID] ครับ"),
    ("บัตรประชาชน 1234567890123", "บัตรประชาชน [NATIONAL_ID]"),
    ("マイナンバーは1234 5678 9012です", "マイナンバーは[NATIONAL_ID]です"),
    ("マイナンバー123456789012", "マイナンバー[NATIONAL_ID]"),
]

UNCHANGED = [
    "How do I file a claim?",
    "I must file within 30 days of the incident on 2026-10-25.",
    "The deductible is THB 1,500 and the limit is PHP 250,000.",
    "事故から30日以内に請求してください。免責は1万円です。",
    "ต้องยื่นเรื่องภายใน 15 วัน ค่าเสียหายส่วนแรก 1,500 บาท",
    "Klaim harus diajukan dalam 14 hari, biaya Rp 500.000.",
    "Article 12 and section 3 apply. Room 1204, 8 documents.",
    "",
]


@pytest.mark.parametrize(
    ("text", "expected"),
    EMAILS + POLICY_NUMBERS + CLAIM_IDS + PHONES + NATIONAL_IDS,
)
def test_masks_pii(text: str, expected: str) -> None:
    assert redact(text) == expected


@pytest.mark.parametrize("text", UNCHANGED)
def test_text_without_pii_is_unchanged(text: str) -> None:
    assert redact(text) == text


def test_masks_several_kinds_in_one_text() -> None:
    text = "Claim PH-1042 for POL-PH-1234567, reach me at a@b.com or 0917 123 4567."
    assert redact(text) == "Claim [CLAIM_ID] for [POLICY], reach me at [EMAIL] or [PHONE]."


def test_masks_japanese_sentence_with_several_kinds() -> None:
    text = "契約者(POL-JP-998877)の電話は090-1234-5678、メールはtaro@example.jpです。"
    assert redact(text) == "契約者([POLICY])の電話は[PHONE]、メールは[EMAIL]です。"


def test_policy_number_is_not_also_treated_as_a_claim_id() -> None:
    assert redact("POL-PH-1234567") == "[POLICY]"


def test_redaction_is_idempotent() -> None:
    once = redact("PH-1042 a@b.com +63 917 123 4567 S1234567D POL-SG-123456")
    assert redact(once) == once

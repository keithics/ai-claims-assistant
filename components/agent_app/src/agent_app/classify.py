import re

from router import Intent, Risk

CLAIM_ID = re.compile(r"\b[A-Za-z]{2}-\d{3,6}\b")
DATE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")

STATUS_WORDS = (
    "status", "update", "check", "where is", "progress", "paid", "approved", "rejected",
    "ano na", "tingnan", "nabayaran", "unsa na", "tan-awa", "nabayran", "balita",
    "status", "cek", "bagaimana", "sudah dibayar", "kabar",
    "สถานะ", "เช็ก", "ความคืบหน้า", "จ่ายเงินแล้ว",
    "状況", "確認", "進み具合", "どうなり", "支払われ",
)  # fmt: skip
INCIDENT_WORDS = (
    "accident", "stolen", "flood", "hospital", "admitted", "damage", "broke", "hit", "burst",
    "aksidente", "nabangga", "ninakaw", "binaha", "na-admit", "nabasag",
    "nabangga", "gikawat", "nabaha", "nabuak",
    "kecelakaan", "ditabrak", "dicuri", "dirawat", "pecah", "kebocoran",
    "อุบัติเหตุ", "ถูกชน", "ถูกขโมย", "นอนโรงพยาบาล", "ร้าว", "รั่ว",
    "追突", "盗まれ", "入院", "壊れ", "割れ",
)  # fmt: skip
RULE_WORDS = (
    "days", "deadline", "how long", "excess", "waiting period", "pre-approval", "pre approval",
    "police report", "limit", "not covered", "covered", "how many", "how much", "documents",
    "araw", "ilang", "magkano", "waiting", "pre-approval", "kailan", "ka adlaw", "pila",
    "unsa ka dugay",
    "hari", "berapa", "batas", "masa tunggu", "dijamin", "dokumen",
    "กี่วัน", "เท่าไร", "ระยะรอ", "คุ้มครอง", "กี่", "เอกสาร",
    "何日", "いくら", "待機期間", "補償", "期限", "免責", "書類", "事前承認",
)  # fmt: skip
RISKY_WORDS = (
    "ignore your instructions", "ignore previous", "system prompt", "without approval",
    "i do not need to approve", "approve my claim", "approve it", "hidden instructions",
    "huwag mo nang pansinin", "system prompt", "hindi ko aprubahan", "pakiaprubahan",
    "ayaw na tagda", "dili nako i-aprobar", "i-aprobar ang",
    "abaikan instruksi", "tidak perlu menyetujui", "setujui klaim",
    "ไม่ต้องสนใจคำสั่ง", "ไม่ต้องอนุมัติ", "ช่วยอนุมัติ",
    "指示は無視", "承認なしで", "承認してください",
    "address and phone", "home address", "alamat dan nomor", "ที่อยู่และเบอร์",
    "住所と電話", "address at telepono", "address ug telepono",
)  # fmt: skip


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def classify(message: str, country: str | None = None) -> tuple[Intent, Risk]:
    text = message.lower()
    claim_ids = CLAIM_ID.findall(message)
    foreign = country is not None and any(
        cid.split("-", 1)[0].lower() != country for cid in claim_ids
    )
    filing = DATE.search(message) is not None and _has(text, INCIDENT_WORDS)

    if foreign or _has(text, RISKY_WORDS):
        return ("claim_status" if claim_ids else "other"), "high"
    if filing and not (claim_ids and _has(text, STATUS_WORDS)):
        return "claim_filing", "high"
    if claim_ids:
        return "claim_status", "low"
    if _has(text, RULE_WORDS):
        return "country_rule", "low"
    return "faq", "low"

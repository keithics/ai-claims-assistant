import unicodedata

RAW_STRONG: tuple[str, ...] = (
    "end my life",
    "kill myself",
    "want to die",
    "wanna die",
    "hurt myself",
    "harm myself",
    "cutting myself",
    "cut myself",
    "do not want to live",
    "don't want to live",
    "no reason to live",
    "tapusin ang buhay ko",
    "tapusin ko ang buhay",
    "patayin ang sarili",
    "sinasaktan ko ang sarili",
    "saktan ang sarili",
    "gusto ko nang mamatay",
    "magpakamatay ako",
    "tapuson akong kinabuhi",
    "tapuson nako akong kinabuhi",
    "gisakit nako akong kaugalingon",
    "samdan akong kaugalingon",
    "gusto na nako mamatay",
    "mopatay sa akong kaugalingon",
    "mengakhiri hidup",
    "ingin mati",
    "tidak ingin hidup",
    "melukai diri sendiri",
    "menyakiti diri sendiri",
    "ingin bunuh diri",
    "mau bunuh diri",
    "อยากจบชีวิต",
    "จบชีวิตตัวเอง",
    "อยากตาย",
    "ทำร้ายตัวเอง",
    "ฆ่าตัวตายดี",
    "死にたい",
    "消えてしまいたい",
    "自分を傷つけ",
    "命を絶ちたい",
    "自殺したい",
)
RAW_WEAK: tuple[str, ...] = (
    "self-harm",
    "self harm",
    "suicide",
    "suicidal",
    "magpakamatay",
    "bunuh diri",
    "ฆ่าตัวตาย",
    "自殺",
    "自死",
)
RAW_INSURANCE: tuple[str, ...] = (
    "policy",
    "cover",
    "claim",
    "insurance",
    "exclusion",
    "benefit",
    "payout",
    "polisi",
    "polis",
    "asuransi",
    "klaim",
    "seguro",
    "saklaw",
    "ประกัน",
    "กรมธรรม์",
    "เคลม",
    "คุ้มครอง",
    "保険",
    "補償",
    "請求",
    "約款",
    "免責",
)


def _normalise(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


STRONG = tuple(_normalise(phrase) for phrase in RAW_STRONG)
WEAK = tuple(_normalise(word) for word in RAW_WEAK)
INSURANCE = tuple(_normalise(word) for word in RAW_INSURANCE)


def is_self_harm(message: str) -> bool:
    text = _normalise(message)
    if any(phrase in text for phrase in STRONG):
        return True
    asks_about_cover = any(word in text for word in INSURANCE)
    return any(word in text for word in WEAK) and not asks_about_cover

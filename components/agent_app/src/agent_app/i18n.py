LANGUAGE_NAMES = {
    "en": "English",
    "fil": "Filipino",
    "ceb": "Cebuano",
    "id": "Bahasa Indonesia",
    "th": "Thai",
    "ja": "Japanese",
}

NOTICES = {
    "en": "I am an AI assistant. You can ask for a human agent at any time: {handoff}.",
    "fil": "AI assistant po ako. Maaari kayong humingi ng taong ahente anumang oras: {handoff}.",
    "ceb": "AI assistant ko. Pwede ka mangayo og tawhanong ahente bisan unsang orasa: {handoff}.",
    "id": "Saya asisten AI. Anda dapat meminta agen manusia kapan saja: {handoff}.",
    "th": "ฉันเป็นผู้ช่วย AI คุณสามารถขอคุยกับเจ้าหน้าที่ได้ทุกเมื่อ: {handoff}",
    "ja": "私はAIアシスタントです。いつでも担当者におつなぎできます:{handoff}",
}


def notice(language: str, handoff: str) -> str:
    return NOTICES[language].format(handoff=handoff)


HANDOFF = {
    "en": "I cannot handle this request right now. Please contact a human agent: {handoff}.",
    "fil": "Hindi ko po ito maasikaso ngayon. Makipag-ugnayan po sa taong ahente: {handoff}.",
    "ceb": "Dili nako kini maatiman karon. Palihug kontaka ang tawhanong ahente: {handoff}.",
    "id": (
        "Saya tidak dapat menangani permintaan ini sekarang. "
        "Silakan hubungi agen manusia: {handoff}."
    ),
    "th": "ตอนนี้ฉันไม่สามารถดำเนินการเรื่องนี้ได้ โปรดติดต่อเจ้าหน้าที่: {handoff}",
    "ja": "現在このご依頼にはお応えできません。担当者にご連絡ください:{handoff}",
}


def handoff_message(language: str, handoff: str) -> str:
    return HANDOFF[language].format(handoff=handoff)


FILTERED = {
    "en": (
        "I cannot help with that request. You can ask me about a claim, "
        "or reach a human agent: {handoff}."
    ),
    "fil": (
        "Hindi ko po matutulungan ang kahilingang iyon. Magtanong po tungkol sa claim "
        "o makipag-ugnayan sa taong ahente: {handoff}."
    ),
    "ceb": (
        "Dili nako matabangan ana nga hangyo. Pangutana bahin sa claim "
        "o kontaka ang tawhanong ahente: {handoff}."
    ),
    "id": (
        "Saya tidak dapat membantu permintaan itu. Tanyakan soal klaim "
        "atau hubungi agen manusia: {handoff}."
    ),
    "th": "ฉันช่วยเรื่องนั้นไม่ได้ ถามเกี่ยวกับเคลมได้ หรือติดต่อเจ้าหน้าที่: {handoff}",
    "ja": (
        "そのご依頼にはお応えできません。保険金請求についてお尋ねいただくか、"
        "担当者にご連絡ください:{handoff}"
    ),
}


def filtered_message(language: str, handoff: str) -> str:
    return FILTERED[language].format(handoff=handoff)


SELF_HARM = {
    "en": (
        "I'm really sorry you are going through this. I can't help with that here, but you do "
        "not have to face it alone. Please reach out to someone you trust or to local emergency "
        "or crisis services right now. If you would like to speak to a person, you can contact: "
        "{handoff}."
    ),
    "fil": (
        "Pasensya na po at pinagdaraanan ninyo ito. Hindi ko po ito matutulungan dito, pero "
        "hindi po kayo nag-iisa. Makipag-ugnayan po agad sa taong pinagkakatiwalaan ninyo o sa "
        "lokal na emergency o crisis services. "
        "Kung gusto ninyong makausap ang isang tao: {handoff}."
    ),
    "ceb": (
        "Pasayloa ko nga naagi nimo kini. Dili ko makatabang ani dinhi, apan dili ka nag-inusara. "
        "Palihug kontaka dayon ang usa ka tawo nga kasaligan nimo o ang lokal nga emergency o "
        "crisis services. Kung gusto ka makigsulti sa tawo: {handoff}."
    ),
    "id": (
        "Saya turut prihatin Anda mengalami hal ini. Saya tidak dapat membantu soal itu di sini, "
        "tetapi Anda tidak sendirian. Segera hubungi orang yang Anda percaya atau layanan darurat "
        "atau krisis setempat. Jika ingin berbicara dengan petugas: {handoff}."
    ),
    "th": (
        "ฉันเสียใจที่คุณกำลังเผชิญเรื่องนี้ ฉันช่วยเรื่องนี้ตรงนี้ไม่ได้ "
        "แต่คุณไม่ต้องเผชิญคนเดียว โปรดติดต่อคนที่คุณไว้ใจหรือหน่วยบริการฉุกเฉินหรือสายด่วนช่วยเหลือในพื้นที่ทันที "
        "หากต้องการคุยกับเจ้าหน้าที่: {handoff}"
    ),
    "ja": (
        "おつらい状況の中、お話しいただきありがとうございます。ここではお力になれませんが、"
        "一人で抱え込まないでください。信頼できる方や、お近くの緊急窓口・相談窓口にすぐご連絡ください。"
        "担当者と話したい場合はこちらです:{handoff}"
    ),
}

OUT_OF_SCOPE = {
    "en": (
        "I can only help with insurance claims and policy questions for {country}. "
        "For anything else, or to speak to a person, contact: {handoff}."
    ),
    "fil": (
        "Insurance claims at mga tanong sa polisiya para sa {country} lang po ang matutulungan ko. "
        "Para sa iba o para makausap ang isang tao: {handoff}."
    ),
    "ceb": (
        "Insurance claims ug mga pangutana sa polisiya para sa {country} ra ang matabangan nako. "
        "Para sa uban o makigsulti sa tawo: {handoff}."
    ),
    "id": (
        "Saya hanya dapat membantu soal klaim asuransi dan pertanyaan polis untuk {country}. "
        "Untuk hal lain, atau berbicara dengan petugas: {handoff}."
    ),
    "th": (
        "ฉันช่วยได้เฉพาะเรื่องเคลมประกันและคำถามเกี่ยวกับกรมธรรม์ของ {country} เท่านั้น "
        "หากต้องการเรื่องอื่นหรือคุยกับเจ้าหน้าที่: {handoff}"
    ),
    "ja": (
        "{country}の保険金請求と保険契約に関するご質問のみお手伝いできます。"
        "それ以外のご用件や担当者へのご連絡はこちらです:{handoff}"
    ),
}


def self_harm_message(language: str, handoff: str) -> str:
    return SELF_HARM[language].format(handoff=handoff)


def out_of_scope_message(language: str, country: str, handoff: str) -> str:
    return OUT_OF_SCOPE[language].format(country=country, handoff=handoff)


CANNOT_FINISH = {
    "en": (
        "I could not finish this request. Please try rephrasing it, "
        "or I can connect you with a human agent."
    ),
    "fil": (
        "Hindi ko po natapos ang kahilingang ito. Subukan pong baguhin ang pagkakasabi, "
        "o maaari ko kayong ikonekta sa taong ahente."
    ),
    "ceb": (
        "Wala nako nahuman kini nga hangyo. Sulayi pag-usab sa lahi nga pagkasulti, "
        "o mahimo tika ikonektar sa tawhanong ahente."
    ),
    "id": (
        "Saya tidak dapat menyelesaikan permintaan ini. Coba ubah kalimatnya, "
        "atau saya dapat menghubungkan Anda dengan agen manusia."
    ),
    "th": ("ฉันไม่สามารถทำคำขอนี้ให้เสร็จได้ ลองเปลี่ยนวิธีพิมพ์ หรือฉันสามารถเชื่อมต่อคุณกับเจ้าหน้าที่ได้"),
    "ja": (
        "このご依頼を完了できませんでした。表現を変えてお試しいただくか、"
        "担当者におつなぎいたします。"
    ),
}

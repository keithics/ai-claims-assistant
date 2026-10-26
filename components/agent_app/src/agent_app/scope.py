import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

Embed = Callable[..., list[list[float]]]
CLAIM_ID = re.compile(r"\b[A-Za-z]{2}-\d{3,6}\b")

EXEMPLARS: Mapping[str, tuple[str, ...]] = {
    "en": (
        "Hello, can you help me?",
        "Thank you for your help",
        "What can you help me with?",
        "What is the status of my claim?",
        "I want to file a claim for my car accident",
        "How do I make a claim?",
        "I want to talk to a human agent",
        "I have a complaint about my claim",
        "What documents do I need for a claim?",
        "What is covered by my policy?",
    ),
    "fil": (
        "Kumusta, matutulungan mo ba ako?",
        "Salamat sa tulong",
        "Ano ang status ng claim ko?",
        "Gusto kong mag-file ng claim",
        "Paano ako magsasampa ng claim?",
        "Gusto kong makausap ang taong ahente",
        "Anong mga dokumento ang kailangan ko?",
    ),
    "ceb": (
        "Kumusta, matabangan ba ko nimo?",
        "Salamat sa tabang",
        "Unsa na ang status sa akong claim?",
        "Gusto ko mag-file og claim",
        "Unsaon nako pag-file og claim?",
        "Gusto nako makigsulti sa tawhanong ahente",
        "Unsa nga mga dokumento ang kinahanglan nako?",
    ),
    "id": (
        "Halo, bisakah Anda membantu saya?",
        "Terima kasih atas bantuannya",
        "Bagaimana status klaim saya?",
        "Saya ingin mengajukan klaim",
        "Bagaimana cara mengajukan klaim?",
        "Saya ingin berbicara dengan petugas manusia",
        "Dokumen apa yang saya perlukan?",
    ),
    "th": (
        "สวัสดี ช่วยฉันได้ไหม",
        "ขอบคุณสำหรับความช่วยเหลือ",
        "สถานะเคลมของฉันเป็นอย่างไร",
        "ฉันอยากยื่นเคลม",
        "ยื่นเคลมอย่างไร",
        "ขอคุยกับเจ้าหน้าที่",
        "ต้องใช้เอกสารอะไรบ้าง",
    ),
    "ja": (
        "こんにちは、助けてもらえますか",
        "ありがとうございました",
        "請求の状況を教えてください",
        "保険金を請求したいです",
        "請求の手順を教えてください",
        "担当者と話したいです",
        "必要な書類は何ですか",
    ),
}


OFF_TOPIC: Mapping[str, tuple[str, ...]] = {
    "en": (
        "How do I cook pasta carbonara?",
        "Help me debug my JavaScript code",
        "Compose a short story about a dragon",
        "Which political party is the best?",
        "What should I take for a stomach ache?",
        "Is bitcoin a good investment?",
        "Who won the football match yesterday?",
        "Recommend a hotel in Tokyo",
    ),
    "fil": (
        "Paano magluto ng sinigang?",
        "Tulungan mo akong ayusin ang JavaScript code ko",
        "Magkwento ka tungkol sa isang dragon",
        "Aling partido pulitikal ang pinakamahusay?",
        "Ano ang dapat kong inumin para sa sakit ng tiyan?",
        "Magandang investment ba ang bitcoin?",
        "Sino ang nanalo sa laro kahapon?",
        "Magrekomenda ka ng hotel sa Tokyo",
    ),
    "ceb": (
        "Unsaon pagluto og tinola?",
        "Tabangi ko pag-ayo sa akong JavaScript code",
        "Sugiri ko og istorya bahin sa usa ka dragon",
        "Unsang partido politikal ang pinakamaayo?",
        "Unsa akong imnon para sa sakit sa tiyan?",
        "Maayo ba nga investment ang bitcoin?",
        "Kinsa ang nidaog sa dula gahapon?",
        "Irekomenda ko og hotel sa Tokyo",
    ),
    "id": (
        "Bagaimana cara memasak nasi goreng?",
        "Bantu saya memperbaiki kode JavaScript saya",
        "Buatkan cerita pendek tentang naga",
        "Partai politik mana yang terbaik?",
        "Obat apa untuk sakit perut?",
        "Apakah bitcoin investasi yang bagus?",
        "Siapa yang menang pertandingan sepak bola kemarin?",
        "Rekomendasikan hotel di Tokyo",
    ),
    "th": (
        "ทำผัดกะเพราอย่างไร",
        "ช่วยแก้โค้ด JavaScript ของฉันหน่อย",
        "แต่งเรื่องสั้นเกี่ยวกับมังกร",
        "พรรคการเมืองไหนดีที่สุด",
        "ปวดท้องควรกินยาอะไร",
        "บิตคอยน์เป็นการลงทุนที่ดีไหม",
        "เมื่อวานใครชนะการแข่งขันฟุตบอล",
        "แนะนำโรงแรมในโตเกียวหน่อย",
    ),
    "ja": (
        "パスタの作り方を教えてください",
        "JavaScriptのコードのバグを直してください",
        "ドラゴンについての短い物語を書いてください",
        "どの政党がいちばん良いですか",
        "お腹が痛いときは何を飲めばいいですか",
        "ビットコインは良い投資ですか",
        "昨日のサッカーの試合は誰が勝ちましたか",
        "東京のおすすめのホテルを教えてください",
    ),
}


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


@dataclass
class ScopeGuard:
    embed: Embed
    topics: Mapping[str, Sequence[str]]
    margin: float
    _vectors: dict[str, tuple[list[list[float]], list[list[float]]]] = field(default_factory=dict)

    def _exemplar_vectors(self, country: str) -> tuple[list[list[float]], list[list[float]]]:
        if country not in self._vectors:
            inside = [p for group in EXEMPLARS.values() for p in group]
            inside += list(self.topics.get(country, ()))
            outside = [p for group in OFF_TOPIC.values() for p in group]
            vectors = self.embed(inside + outside, country=country)
            self._vectors[country] = (vectors[: len(inside)], vectors[len(inside) :])
        return self._vectors[country]

    def score(self, message: str, country: str) -> tuple[float, float]:
        inside, outside = self._exemplar_vectors(country)
        query = self.embed([message], country=country)[0]
        return (
            max(cosine(query, v) for v in inside),
            max(cosine(query, v) for v in outside),
        )

    def out_of_scope(
        self, message: str, country: str, *, has_history: bool
    ) -> tuple[bool, float | None]:
        if has_history or CLAIM_ID.search(message):
            return False, None
        inside, outside = self.score(message, country)
        closeness = inside - outside
        return closeness < self.margin, closeness

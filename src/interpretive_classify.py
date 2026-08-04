import re

from .llm_client import LLMClient
from .poem_model import Poem, ThemeTag

# 전고(Allusion)는 이 프로젝트 범위에서 완전히 제외되므로(계획서 Global Constraints
# 참고) 원본 시구 텍스트가 아니다. 임백호집 골드 파일에는 <Line> 안에 자기닫힘
# <Allusion .../> 요소(속성만 있고 내용 없음)와, 드물게 편집자 주석인
# <Annotation>...</Annotation>(poem-level Metadata의 Annotation과는 별개)이 섞여
# 있으므로, LLM 프롬프트나 evidence 환각 검증에 쓰일 순수 텍스트를 만들기 전에
# 이 두 요소를 통째로(속성값 포함) 제거해야 한다.
_ELEMENT_STRIP = re.compile(r"<Allusion\b[^>]*/>|<Annotation\b[^>]*>.*?</Annotation>", re.DOTALL)
_TAG_STRIP = re.compile(r"</?(term|d|rhyme)>")

THEME_CATEGORIES = {
    "mountain": ("산악", ["山", "石", "登", "望", "觀"]),
    "water": ("강해", ["水", "海", "湖", "川", "浦"]),
    "astro": ("천문", ["日", "月", "星", "雷", "雨", "雪", "風"]),
    "season": ("계절", ["節", "春", "夏", "秋", "冬"]),
    "animal": ("동물", ["禽", "獸", "鱗", "蟲"]),
    "plant": ("식물", ["花", "樹", "菓", "草"]),
    "travel": ("유람", ["遊", "過", "行", "宿"]),
    "donate": ("기증", ["贈", "答", "和"]),
    "farewell": ("송별", ["送", "別", "留別"]),
    "meet": ("회방", ["訪", "會", "見"]),
    "sympathy": ("애상", ["挽", "恨", "哀悼", "弔古"]),
    "reminiscence": ("회고", ["懷", "憶", "追"]),
    "frontier": ("변새", ["邊", "塞"]),
    "desire": ("염정", ["閨怨", "宮詞"]),
    "dream": ("기몽", ["夢"]),
    "prosper": ("현달", ["慶", "賀", "喜"]),
    "tranquility": ("한적", ["閑", "居", "退"]),
    "banquet": ("연회", ["宴", "樂", "曲", "茶酒"]),
    "person": ("인물", ["人物", "漁釣", "豪俠"]),
    "taoism": ("도교", ["仙", "道"]),
    "buddhism": ("불교", ["釋", "佛", "寺刹", "僧"]),
    "structure": ("건물", ["樓", "亭", "臺", "閣", "堂"]),
    "object": ("기용", ["器"]),
    "literature": ("문방", ["文", "讀", "觀"]),
    "picture": ("도화", ["畵", "圖", "題畵"]),
    "others": ("기타", []),
}

SYSTEM_PROMPT = """\
당신은 한국 한시 태깅 전문가입니다. 시 한 편을 보고 아래 세 가지를 판정해
submit_result 도구로 제출하세요.

1. 형식(basetype/detailtype)
   - 근체시: 절구(4구)·율시(8구)·배율(8구 초과)
   - 고체시: 고시·악부·사(詞)·사(辭)·부(賦)·잡체시(雜體詩)·과체시(科體詩)
   - 제목이 '~歌', '~行', '~引', '~謠'로 끝나면 고체시(악부/고시)일 가능성이 높습니다.

2. 대장(couplets): 근체시의 중간 구-쌍(절구 제외) 중 실제로 문법·의미가
   대응하는 경우만 [상구번호, 하구번호]로 나열하세요. 위치상 대장이 가능해
   보여도 실제 대응이 약하면 포함하지 마세요. 절구는 항상 빈 리스트입니다.

3. 주제(themes): 아래 24개 카테고리 중 해당하는 것을 다중 선택하세요.
   각 항목은 category(영문 코드), basis(title/term/title, term), evidence(제목
   또는 시어에서 실제로 등장하는 글자 그대로), label_ko(한글 라벨)를 포함합니다.
   evidence는 반드시 시의 제목 또는 본문에 실제로 나오는 글자만 사용하세요.
   카테고리 표: {categories}
""".format(
    categories=", ".join(f"{k}({v[0]})" for k, v in THEME_CATEGORIES.items())
)

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "basetype": {"type": "string", "enum": ["근체시", "고체시"]},
        "detailtype": {"type": "string"},
        "couplets": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
        },
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "basis": {"type": "string"},
                    "evidence": {"type": "string"},
                    "label_ko": {"type": "string"},
                },
                "required": ["category", "basis", "evidence", "label_ko"],
            },
        },
    },
    "required": ["basetype", "detailtype", "couplets", "themes"],
}


def _plain(xml_fragment: str) -> str:
    without_out_of_scope_elements = _ELEMENT_STRIP.sub("", xml_fragment)
    return _TAG_STRIP.sub("", without_out_of_scope_elements)


def _evidence_exists_in_poem(evidence: str, poem_plain_text: str) -> bool:
    tokens = evidence.replace(",", " ").split()
    return all(token in poem_plain_text for token in tokens)


def classify_form_couplet_theme(poem: Poem, llm_client: LLMClient) -> tuple[Poem, list[dict]]:
    flags: list[dict] = []
    title_plain = _plain(poem.title_xml)
    body_plain = "\n".join(_plain(ln.content_xml) for ln in poem.lines)
    # "\n"으로 구분해 제목-첫구, 구-구 경계에서 우연히 이어붙여진 글자열이
    # 실제로는 존재하지 않는 evidence로 잘못 검증되는 것을 방지한다.
    full_text = title_plain + "\n" + body_plain

    user_prompt = (
        f"제목: {title_plain}\n"
        f"자수: {poem.charactercount}\n"
        f"구수: {len(poem.lines)}\n"
        "본문:\n" + "\n".join(f"{ln.order}구: {_plain(ln.content_xml)}" for ln in poem.lines)
    )

    result = llm_client.complete(SYSTEM_PROMPT, user_prompt, _RESPONSE_SCHEMA)

    poem.basetype = result["basetype"]
    poem.detailtype = result["detailtype"]

    couplet_orders = {order for pair in result["couplets"] for order in pair}
    for line in poem.lines:
        line.in_couplet = line.order in couplet_orders

    accepted_themes = []
    for theme in result["themes"]:
        if _evidence_exists_in_poem(theme["evidence"], full_text):
            accepted_themes.append(
                ThemeTag(
                    category=theme["category"],
                    basis=theme["basis"],
                    evidence=theme["evidence"],
                    label_ko=theme["label_ko"],
                )
            )
        else:
            flags.append(
                {
                    "poem_id": poem.id,
                    "item": "Theme",
                    "reason": f"evidence 미검증(환각 의심): {theme['evidence']}",
                }
            )
    poem.themes = accepted_themes

    return poem, flags

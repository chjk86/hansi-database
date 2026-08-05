import re

from src.llm_client import LLMClient
from src.poem_model import Poem

_ELEMENT_STRIP = re.compile(r"<Allusion\b[^>]*/>|<Annotation\b[^>]*>.*?</Annotation>", re.DOTALL)
_TAG_STRIP = re.compile(r"</?(term|d|rhyme)>")

_FORM_SYSTEM_PROMPT = """\
당신은 한국 한시 형식 분류 전문가입니다. 시 한 편을 보고 형식을 판정해
submit_result 도구로 제출하세요.

- 근체시: 절구(4구)·율시(8구)·배율(8구 초과) — 근체시로 판단되면 detailtype에는
  당신이 생각하는 값을 넣어도 되지만, 실제로는 구수로 기계적으로 재확정되므로
  절구/율시/배율 여부에 대한 고민보다 근체시/고체시 판정 자체에 집중하세요.
- 고체시: 고시·악부·사(詞)·사(辭)·부(賦)·잡체시(雜體詩)·과체시(科體詩) 중
  detailtype을 정확히 판단하세요. 제목이 '~歌', '~行', '~引', '~謠'로 끝나면
  고체시(악부/고시)일 가능성이 높습니다.
"""

_FORM_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "basetype": {"type": "string", "enum": ["근체시", "고체시"]},
        "detailtype": {"type": "string"},
    },
    "required": ["basetype", "detailtype"],
}


def _plain_form_body(poem: Poem) -> str:
    def plain(xml_fragment: str) -> str:
        without_out_of_scope = _ELEMENT_STRIP.sub("", xml_fragment)
        return _TAG_STRIP.sub("", without_out_of_scope)

    title_plain = plain(poem.title_xml)
    body_plain = "\n".join(plain(ln.content_xml) for ln in poem.lines)
    return title_plain + "\n" + body_plain


def _geunche_detailtype(line_count: int) -> str:
    if line_count == 4:
        return "절구"
    if line_count == 8:
        return "율시"
    return "배율"


def classify_form(poem: Poem, llm_client: LLMClient) -> Poem:
    title_plain = _TAG_STRIP.sub("", _ELEMENT_STRIP.sub("", poem.title_xml))
    user_prompt = (
        f"제목: {title_plain}\n"
        f"자수: {poem.charactercount}\n"
        f"구수: {len(poem.lines)}\n"
    )

    result = llm_client.complete(_FORM_SYSTEM_PROMPT, user_prompt, _FORM_RESPONSE_SCHEMA)

    poem.basetype = result["basetype"]
    if poem.basetype == "근체시":
        poem.detailtype = _geunche_detailtype(len(poem.lines))
    else:
        poem.detailtype = result["detailtype"]

    return poem

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


_COUPLET_SYSTEM_PROMPT = """\
당신은 한국 한시 대장(對仗) 판정 전문가입니다. 근체시의 중간 구-쌍 중 실제로
문법·의미가 대응하는 경우만 [상구번호, 하구번호]로 나열해 submit_result 도구로
제출하세요. 위치상 대장이 가능해 보여도 실제 대응이 약하면 포함하지 마세요.
확신이 없으면 빈 리스트를 반환하세요.
"""

_COUPLET_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "couplets": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
        },
    },
    "required": ["couplets"],
}


def classify_couplet(poem: Poem, llm_client: LLMClient) -> Poem:
    user_prompt = "본문:\n" + "\n".join(
        f"{ln.order}구: {_TAG_STRIP.sub('', _ELEMENT_STRIP.sub('', ln.content_xml))}"
        for ln in poem.lines
    )

    result = llm_client.complete(_COUPLET_SYSTEM_PROMPT, user_prompt, _COUPLET_RESPONSE_SCHEMA)

    couplet_orders = {order for pair in result["couplets"] for order in pair}
    for line in poem.lines:
        line.in_couplet = line.order in couplet_orders

    return poem


_RHYME_TAG_RE = re.compile(r"<rhyme>(.)</rhyme>")

_TERM_SYSTEM_PROMPT = """\
당신은 한국 한시 시어(詩語) 분석 전문가입니다. 아래 시구들에서 의미적으로
중요한 시어(2자 이상의 명사어·형용사어·안긴 어휘)의 경계를 문맥과 문학적 판단만으로
정하세요. 부정어는 상태·정서를 구체화하는 경우만(예: 無消息) 포함하고, 단순
조동사·기능어(예: 不敢)는 제외합니다. 판단한 시어는 원문 글자를 그대로
text 필드에 담아 submit_result 도구로 제출하세요. 시구마다 시어가 없을 수도, 여러
개일 수도 있습니다.
"""

_TERM_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "spans": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["line_id", "text"],
            },
        },
    },
    "required": ["spans"],
}


def _plain_and_rhyme_index(content_xml: str) -> tuple[str, int | None]:
    """기존 term/d 태그를 모두 제거한 순수 텍스트와, <rhyme>로 감싸인 글자의
    순수 텍스트 기준 인덱스(없으면 None)를 반환한다."""
    without_term_d = re.sub(r"</?(term|d)>", "", content_xml)
    m = _RHYME_TAG_RE.search(without_term_d)
    plain = _RHYME_TAG_RE.sub(r"\1", without_term_d)
    rhyme_index = None
    if m:
        prefix = without_term_d[: m.start()]
        prefix_plain = _RHYME_TAG_RE.sub(r"\1", prefix)
        rhyme_index = len(prefix_plain)
    return plain, rhyme_index


def _rebuild_line_with_spans(
    plain: str, rhyme_index: int | None, spans: list[tuple[int, int, str]]
) -> str:
    """spans: (start, end, label) 정렬된 겹치지 않는 구간 리스트."""
    spans = sorted(spans, key=lambda s: s[0])

    def wrap_char_at(text: str, idx: int) -> str:
        if idx is None or not (0 <= idx < len(text)):
            return text
        return text[:idx] + f"<rhyme>{text[idx]}</rhyme>" + text[idx + 1 :]

    out = []
    cursor = 0
    for start, end, label in spans:
        gap = plain[cursor:start]
        if rhyme_index is not None and cursor <= rhyme_index < start:
            gap = wrap_char_at(gap, rhyme_index - cursor)
        out.append(gap)

        span_text = plain[start:end]
        if rhyme_index is not None and start <= rhyme_index < end:
            span_text = wrap_char_at(span_text, rhyme_index - start)
        out.append(f"<{label}>{span_text}</{label}>")
        cursor = end
    tail = plain[cursor:]
    if rhyme_index is not None and cursor <= rhyme_index < len(plain):
        tail = wrap_char_at(tail, rhyme_index - cursor)
    out.append(tail)
    return "".join(out)


def _find_unclaimed_occurrence(plain: str, text: str, claimed: list[tuple[int, int]]) -> int:
    """plain에서 text가 나타나는 위치 중, claimed(이미 다른 span이 차지한 (start, end)
    구간들)와 겹치지 않는 가장 왼쪽 occurrence의 시작 인덱스를 반환한다. 없으면 -1.
    LLM이 시구 내 span들을 읽기 순서와 다르게 반환하더라도(=순서 무관) 올바른 위치를
    찾기 위해 단일 커서 대신 이 방식을 사용한다."""
    search_from = 0
    while True:
        idx = plain.find(text, search_from)
        if idx == -1:
            return -1
        end = idx + len(text)
        if not any(idx < c_end and end > c_start for c_start, c_end in claimed):
            return idx
        search_from = idx + 1


def classify_term_d(
    poem: Poem, dict_index, llm_client: LLMClient
) -> tuple[Poem, list[dict]]:
    flags: list[dict] = []
    plains: dict[str, tuple[str, int | None]] = {
        ln.id: _plain_and_rhyme_index(ln.content_xml) for ln in poem.lines
    }

    user_prompt = "시구:\n" + "\n".join(
        f"{ln.id}: {plains[ln.id][0]}" for ln in poem.lines
    )
    result = llm_client.complete(_TERM_SYSTEM_PROMPT, user_prompt, _TERM_RESPONSE_SCHEMA)

    spans_by_line: dict[str, list[tuple[int, int, str]]] = {ln.id: [] for ln in poem.lines}
    claimed_by_line: dict[str, list[tuple[int, int]]] = {ln.id: [] for ln in poem.lines}
    for span in result["spans"]:
        line_id = span["line_id"]
        text = span["text"]
        if line_id not in plains:
            flags.append(
                {"poem_id": poem.id, "item": "term/D", "reason": f"알 수 없는 line_id: {line_id}"}
            )
            continue
        plain, _ = plains[line_id]
        start = _find_unclaimed_occurrence(plain, text, claimed_by_line[line_id])
        if start == -1:
            flags.append(
                {
                    "poem_id": poem.id,
                    "item": "term/D",
                    "reason": f"{line_id}: LLM이 반환한 시어 '{text}'가 원문에 없음(환각 의심)",
                }
            )
            continue
        end = start + len(text)
        label = "term" if dict_index.contains(text) else "d"
        spans_by_line[line_id].append((start, end, label))
        claimed_by_line[line_id].append((start, end))

    new_lines = []
    for line in poem.lines:
        plain, rhyme_index = plains[line.id]
        new_content = _rebuild_line_with_spans(plain, rhyme_index, spans_by_line[line.id])
        new_lines.append(
            type(line)(id=line.id, order=line.order, content_xml=new_content, in_couplet=line.in_couplet)
        )
    poem.lines = new_lines

    return poem, flags

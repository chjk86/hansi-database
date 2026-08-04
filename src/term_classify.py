import re

from .dict_index import DictIndex
from .llm_client import LLMClient
from .poem_model import Line, Poem
from .segment import generate_candidates

_TAG_PATTERN = re.compile(r"<(term|d)>(.*?)</\1>", re.DOTALL)

TERM_CLASSIFY_SYSTEM_PROMPT = """\
당신은 한국 한시 시어(詩語) 태깅 전문가입니다. 아래 규칙을 따라 애매한 시어 구간의
정확한 경계와 term/D 여부를 판정하세요.

- term: 『한어대사전』에 등재된 시어. D: 등재되지 않았지만 분석상 의미 있는 어휘.
- 부정어 처리: 無消息, 無情처럼 상태·정서를 구체화하거나 不同처럼 반대 뜻으로 굳어진
  경우는 태깅하되, 不敢·不能처럼 단순 조동사·기능어인 경우는 태깅하지 않습니다.
- 3자 시어(안긴 어휘)는 수식어 없이 의미가 급변하거나 고유한 어휘로 쓰일 때만 묶습니다.
- 반드시 원문 글자를 그대로 사용하고, 새로운 글자를 만들어내지 않습니다.
"""


def _strip_tags(content_xml: str) -> str:
    return _TAG_PATTERN.sub(lambda m: m.group(2), content_xml)


def _existing_hint(content_xml: str) -> tuple[int, int] | None:
    """content_xml 안의 첫 <term> 태그 위치를 순수 텍스트 기준 (start, end)로 반환."""
    plain = _strip_tags(content_xml)
    m = _TAG_PATTERN.search(content_xml)
    if not m:
        return None
    prefix_plain = _strip_tags(content_xml[: m.start()])
    start = len(prefix_plain)
    end = start + len(m.group(2))
    return start, end, plain


def _rebuild_line(plain: str, spans: list[tuple[int, int, str]]) -> str:
    """spans: (start, end, label) 정렬된 리스트. 겹치지 않는다고 가정."""
    spans = sorted(spans, key=lambda s: s[0])
    out = []
    cursor = 0
    for start, end, label in spans:
        out.append(plain[cursor:start])
        out.append(f"<{label}>{plain[start:end]}</{label}>")
        cursor = end
    out.append(plain[cursor:])
    return "".join(out)


def classify_poem_terms(
    poem: Poem, dict_index: DictIndex, llm_client: LLMClient
) -> tuple[Poem, list[dict]]:
    flags: list[dict] = []
    confirmed_spans: dict[str, list[tuple[int, int, str]]] = {}
    ambiguous_requests = []

    for line in poem.lines:
        hint = _existing_hint(line.content_xml)
        if hint is None:
            confirmed_spans[line.id] = []
            continue
        hint_start, hint_end, plain = hint
        candidates = generate_candidates(plain, hint_start, hint_end, dict_index)

        if len(candidates) == 1:
            c = candidates[0]
            label = "term" if c.in_dict else "d"
            confirmed_spans[line.id] = [(c.start, c.end, label)]
        else:
            ambiguous_requests.append(
                {
                    "line_id": line.id,
                    "plain_text": plain,
                    "candidates": [
                        {"start": c.start, "end": c.end, "text": c.text, "in_dict": c.in_dict}
                        for c in candidates
                    ],
                }
            )
            confirmed_spans[line.id] = []  # LLM 응답으로 채워질 예정

    if ambiguous_requests:
        user_prompt = (
            "다음 시구들의 애매한 시어 구간을 판정해 resolved_spans로 반환하세요.\n"
            f"{ambiguous_requests}"
        )
        schema = {
            "type": "object",
            "properties": {
                "resolved_spans": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line_id": {"type": "string"},
                            "start": {"type": "integer"},
                            "end": {"type": "integer"},
                            "text": {"type": "string"},
                            "label": {"type": "string", "enum": ["term", "d"]},
                        },
                        "required": ["line_id", "start", "end", "text", "label"],
                    },
                }
            },
            "required": ["resolved_spans"],
        }
        response = llm_client.complete(TERM_CLASSIFY_SYSTEM_PROMPT, user_prompt, schema)
        for span in response["resolved_spans"]:
            confirmed_spans[span["line_id"]].append((span["start"], span["end"], span["label"]))
            flags.append(
                {
                    "poem_id": poem.id,
                    "item": "term/D",
                    "reason": f"{span['line_id']}: term/D 분절 LLM 판정",
                }
            )

    new_lines = []
    for line in poem.lines:
        hint = _existing_hint(line.content_xml)
        if hint is None:
            new_lines.append(line)
            continue
        _, _, plain = hint
        new_content = _rebuild_line(plain, confirmed_spans[line.id])
        new_lines.append(Line(id=line.id, order=line.order, content_xml=new_content))

    poem.lines = new_lines
    return poem, flags

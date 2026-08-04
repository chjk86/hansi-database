import re

from .dict_index import DictIndex
from .llm_client import LLMClient
from .poem_model import Line, Poem
from .segment import generate_candidates

_TAG_PATTERN = re.compile(r"<(term|d)>(.*?)</\1>", re.DOTALL)
_RHYME_PATTERN = re.compile(r"<(rhyme)>(.*?)</\1>", re.DOTALL)
_ALL_TAGS_RE = re.compile(r"</?(term|d|rhyme)>")

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
    """<term>/<d>/<rhyme> 마커를 모두 제거한 순수 텍스트를 반환한다.

    <term>가 <rhyme>을 품는 경우(예: <term>御<rhyme>風</rhyme></term>)가 실제
    데이터에 흔하므로(지천집 기준 전체 라인의 17%), term/d 태그만 벗기면
    <rhyme> 마크업 문자가 "순수 텍스트"에 그대로 섞여 들어가 힌트 길이/사전
    조회가 오염된다. 세 태그 마커를 한 번에 모두 지워야 진짜 순수 텍스트가 된다.
    """
    return _ALL_TAGS_RE.sub("", content_xml)


def _tag_spans(content_xml: str, pattern: re.Pattern) -> list[tuple[int, int]]:
    """content_xml 안의 pattern에 매치되는 모든 태그 위치를 순수 텍스트 기준
    (start, end) 리스트로 반환한다. term/d 힌트와 rhyme 위치를 동일한 좌표계
    (전 태그 제거 순수 텍스트)로 계산하기 위한 공용 헬퍼."""
    spans: list[tuple[int, int]] = []
    cursor_plain = 0
    cursor_xml = 0
    for m in pattern.finditer(content_xml):
        prefix_plain = _strip_tags(content_xml[cursor_xml : m.start()])
        start = cursor_plain + len(prefix_plain)
        inner_plain = _strip_tags(m.group(2))
        end = start + len(inner_plain)
        spans.append((start, end))
        cursor_plain = end
        cursor_xml = m.end()
    return spans


def _existing_hints(content_xml: str) -> tuple[str, list[tuple[int, int]]]:
    """content_xml 안의 모든 <term>/<d> 태그 위치를 순수 텍스트 기준 (start, end)
    리스트로 반환한다. 원본 19개 문집 데이터에서 <term> 태그는 서로 겹치지
    않으므로(각 문집 파일에서 확인됨) 그대로 힌트로 사용해도 안전하다."""
    plain = _strip_tags(content_xml)
    hints = _tag_spans(content_xml, _TAG_PATTERN)
    return plain, hints


def _wrap_rhyme(plain: str, start: int, end: int, rhyme_spans: list[tuple[int, int]]) -> str:
    """plain[start:end] 구간 중 rhyme_spans에 포함된 부분을 <rhyme> 태그로 감싸 반환한다."""
    contained = sorted(r for r in rhyme_spans if start <= r[0] and r[1] <= end)
    out = []
    cursor = start
    for r_start, r_end in contained:
        out.append(plain[cursor:r_start])
        out.append(f"<rhyme>{plain[r_start:r_end]}</rhyme>")
        cursor = r_end
    out.append(plain[cursor:end])
    return "".join(out)


def _rebuild_line(
    plain: str, spans: list[tuple[int, int, str]], rhyme_spans: list[tuple[int, int]]
) -> str:
    """spans: (start, end, label) 리스트, 겹치지 않는다고 가정. rhyme_spans는
    term/d 스팬 내부(중첩) 또는 바깥(단독)에 있을 수 있으며, 각 위치에 맞게
    <rhyme> 태그를 되살려 넣는다."""
    spans = sorted(spans, key=lambda s: s[0])
    out = []
    cursor = 0
    for start, end, label in spans:
        out.append(_wrap_rhyme(plain, cursor, start, rhyme_spans))
        out.append(f"<{label}>{_wrap_rhyme(plain, start, end, rhyme_spans)}</{label}>")
        cursor = end
    out.append(_wrap_rhyme(plain, cursor, len(plain), rhyme_spans))
    return "".join(out)


def classify_poem_terms(
    poem: Poem, dict_index: DictIndex, llm_client: LLMClient
) -> tuple[Poem, list[dict]]:
    flags: list[dict] = []
    confirmed_spans: dict[str, list[tuple[int, int, str]]] = {}
    ambiguous_requests = []
    # line_id별로 LLM에 보낸 원본 힌트 경계를 순서대로 보관한다. resolved_spans
    # 응답에서 어떤 line_id가 예상보다 적게(또는 전혀) 돌아오지 않았는지 판정해
    # 원본 경계를 <term>으로 되살리는 fallback에 쓰인다.
    ambiguous_hints_by_line: dict[str, list[tuple[int, int]]] = {}

    for line in poem.lines:
        plain, hints = _existing_hints(line.content_xml)
        confirmed_spans[line.id] = []
        for hint_start, hint_end in hints:
            candidates = generate_candidates(plain, hint_start, hint_end, dict_index)
            if len(candidates) == 1:
                c = candidates[0]
                label = "term" if c.in_dict else "d"
                confirmed_spans[line.id].append((c.start, c.end, label))
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
                ambiguous_hints_by_line.setdefault(line.id, []).append((hint_start, hint_end))

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
        resolved_count_by_line: dict[str, int] = {}
        for span in response["resolved_spans"]:
            line_id = span["line_id"]
            if line_id not in ambiguous_hints_by_line:
                # 요청한 적 없는(환각) line_id -- confirmed_spans에 해당 키가 없을 수
                # 있어 그대로 append하면 KeyError로 시 전체 분류가 날아간다. 조용히
                # 버리지 않고 QA 플래그만 남긴 뒤 건너뛴다.
                flags.append(
                    {
                        "poem_id": poem.id,
                        "item": "term/D",
                        "reason": f"{line_id}: 요청하지 않은 line_id의 LLM 응답을 무시함(환각 의심)",
                    }
                )
                continue
            confirmed_spans[line_id].append((span["start"], span["end"], span["label"]))
            resolved_count_by_line[line_id] = resolved_count_by_line.get(line_id, 0) + 1
            flags.append(
                {
                    "poem_id": poem.id,
                    "item": "term/D",
                    "reason": f"{line_id}: term/D 분절 LLM 판정",
                }
            )

        # LLM이 요청했던 애매 구간 중 일부(또는 전부)에 대해 응답을 주지 않은
        # line_id는, 그 구간의 term/D 판정 정보가 조용히 사라지는 대신 원래
        # <term>/<d> 경계(재분류 이전의 사전 힌트)를 <term>으로 그대로 되살려
        # 보존하고 사람이 검토할 수 있도록 QA 플래그를 남긴다.
        for line_id, hints in ambiguous_hints_by_line.items():
            received = resolved_count_by_line.get(line_id, 0)
            missing_hints = hints[received:]
            for hint_start, hint_end in missing_hints:
                confirmed_spans[line_id].append((hint_start, hint_end, "term"))
                flags.append(
                    {
                        "poem_id": poem.id,
                        "item": "term/D",
                        "reason": (
                            f"{line_id}: LLM 응답 누락({hint_start}-{hint_end}) -- "
                            "원본 경계를 <term>으로 유지(fallback)"
                        ),
                    }
                )

    new_lines = []
    for line in poem.lines:
        plain, hints = _existing_hints(line.content_xml)
        if not hints:
            new_lines.append(line)
            continue
        rhyme_spans = _tag_spans(line.content_xml, _RHYME_PATTERN)
        new_content = _rebuild_line(plain, confirmed_spans[line.id], rhyme_spans)
        new_lines.append(Line(id=line.id, order=line.order, content_xml=new_content))

    poem.lines = new_lines
    return poem, flags

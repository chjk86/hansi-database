from dataclasses import dataclass

from .dict_index import DictIndex


@dataclass
class SpanCandidate:
    start: int
    end: int
    text: str
    in_dict: bool


def generate_candidates(
    plain_text: str, hint_start: int, hint_end: int, dict_index: DictIndex
) -> list[SpanCandidate]:
    """hint 주변(±2자)에서 사전 등재 여부를 기준으로 경계 후보를 생성한다.

    사전에 등재된 조합 중 가장 긴 것을 우선하고, 등재된 조합이 전혀 없으면
    원래 힌트 그대로를 사전 미등재(in_dict=False) 후보로 반환한다.
    """
    search_start = max(0, hint_start - 2)
    search_end = min(len(plain_text), hint_end + 2)

    dict_hits: list[SpanCandidate] = []
    for start in range(search_start, search_end):
        max_len = min(dict_index.max_word_length, search_end - start)
        for length in range(max_len, 1, -1):  # 1글자 표제어는 시어 태깅 대상이 아니므로 제외
            end = start + length
            candidate_text = plain_text[start:end]
            if dict_index.contains(candidate_text):
                dict_hits.append(SpanCandidate(start, end, candidate_text, True))

    # 원래 힌트 구간과 겹치는 사전 히트만 채택 (완전히 무관한 위치의 우연한 매칭 배제)
    overlapping = [
        c for c in dict_hits if not (c.end <= hint_start or c.start >= hint_end)
    ]
    if overlapping:
        overlapping.sort(key=lambda c: (-(c.end - c.start), c.start))
        return overlapping

    return [
        SpanCandidate(hint_start, hint_end, plain_text[hint_start:hint_end], False)
    ]

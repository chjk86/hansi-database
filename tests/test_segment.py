from src.dict_index import DictIndex
from src.segment import generate_candidates

WORDS = {"草衣", "長安", "先祖", "遺蹤", "衣", "先", "祖"}


def _idx():
    return DictIndex(set(WORDS))


def test_exact_hint_match_returns_single_high_confidence_candidate():
    # 시구 "先祖遺蹤在" 중 힌트가 가리키는 0-2("先祖")가 사전에 등재
    cands = generate_candidates("先祖遺蹤在", hint_start=0, hint_end=2, dict_index=_idx())
    assert len(cands) == 1
    assert cands[0].text == "先祖"
    assert cands[0].in_dict is True


def test_hint_boundary_off_by_one_is_corrected_by_dictionary():
    # 힌트가 "先祖遺"(0-3)로 잘못 잡혀 있어도 사전에 없는 3자 조합이므로
    # 사전에 있는 2자 조합("先祖")을 후보로 우선 제안해야 한다
    cands = generate_candidates("先祖遺蹤在", hint_start=0, hint_end=3, dict_index=_idx())
    texts = [c.text for c in cands if c.in_dict]
    assert "先祖" in texts


def test_no_dictionary_match_yields_out_of_dict_candidate():
    idx = DictIndex(set())  # 빈 사전
    cands = generate_candidates("先祖遺蹤在", hint_start=0, hint_end=2, dict_index=idx)
    assert len(cands) == 1
    assert cands[0].text == "先祖"
    assert cands[0].in_dict is False

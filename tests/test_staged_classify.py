from src.llm_client import FakeLLMClient
from src.poem_model import Line, Poem
from experiments.staged_classify import classify_form, classify_couplet


def _quatrain():
    return Poem(
        id="P1",
        title_xml="贈<d>眞鑑</d>",
        lines=[
            Line(id="L1", order=1, content_xml="夜伴<term>林僧</term>宿"),
            Line(id="L2", order=2, content_xml="<d>重雲</d>濕<term>草<rhyme>衣</rhyme></term>"),
            Line(id="L3", order=3, content_xml="<term>巖扉</term>開<term>晩日</term>"),
            Line(id="L4", order=4, content_xml="<d>棲鳥</d>始<term>驚<rhyme>飛</rhyme></term>"),
        ],
        charactercount="오언",
    )


def test_geunche_detailtype_is_computed_from_line_count_not_llm():
    # LLM이 절구를 "율시"로 잘못 말해도, 근체시로 확정된 이상 4구=절구 규칙이 덮어써야 한다
    llm = FakeLLMClient(responses=[{"basetype": "근체시", "detailtype": "율시"}])

    result = classify_form(_quatrain(), llm)

    assert result.basetype == "근체시"
    assert result.detailtype == "절구"  # LLM 응답이 아니라 규칙으로 확정됨


def test_gochesi_detailtype_comes_from_llm_unchanged():
    llm = FakeLLMClient(responses=[{"basetype": "고체시", "detailtype": "악부"}])

    result = classify_form(_quatrain(), llm)

    assert result.basetype == "고체시"
    assert result.detailtype == "악부"  # 고체시는 구수 규칙이 없으므로 LLM 응답 그대로


def test_eight_lines_geunche_becomes_yulsi():
    poem = Poem(
        id="P2",
        lines=[Line(id=f"L{i}", order=i, content_xml="字字") for i in range(1, 9)],
        charactercount="오언",
    )
    llm = FakeLLMClient(responses=[{"basetype": "근체시", "detailtype": "아무값"}])

    result = classify_form(poem, llm)

    assert result.detailtype == "율시"


def _yulsi_with_lines():
    return Poem(
        id="P3",
        basetype="근체시",
        detailtype="율시",
        lines=[Line(id=f"L{i}", order=i, content_xml="字字") for i in range(1, 9)],
        charactercount="오언",
    )


def test_couplet_flags_only_llm_confirmed_pairs():
    poem = _yulsi_with_lines()
    llm = FakeLLMClient(responses=[{"couplets": [[5, 6]]}])

    result = classify_couplet(poem, llm)

    in_couplet_orders = [ln.order for ln in result.lines if ln.in_couplet]
    assert in_couplet_orders == [5, 6]


def test_couplet_empty_response_flags_nothing():
    poem = _yulsi_with_lines()
    llm = FakeLLMClient(responses=[{"couplets": []}])

    result = classify_couplet(poem, llm)

    assert all(not ln.in_couplet for ln in result.lines)

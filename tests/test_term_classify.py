from src.dict_index import DictIndex
from src.llm_client import FakeLLMClient
from src.poem_model import Line, Poem
from src.term_classify import classify_poem_terms

WORDS = {"先祖", "遺蹤", "草衣", "重雲"}


def _idx():
    return DictIndex(set(WORDS))


def test_dict_confirmed_span_becomes_term_without_llm_call():
    poem = Poem(
        id="P1",
        lines=[Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在")],
    )
    llm = FakeLLMClient(responses=[])  # 호출되면 즉시 예외 -> 호출 안 됨을 검증

    result, flags = classify_poem_terms(poem, _idx(), llm)

    assert result.lines[0].content_xml == "<term>先祖</term>遺蹤在"
    assert llm.calls == []


def test_dict_unregistered_span_becomes_d_without_llm_call():
    poem = Poem(
        id="P1",
        lines=[Line(id="L1", order=1, content_xml="<term>重雲</term>濕草衣")],
    )
    idx = DictIndex({"重雲"} - {"重雲"})  # 빈 사전 -> 미등재
    llm = FakeLLMClient(responses=[])

    result, flags = classify_poem_terms(poem, idx, llm)

    assert result.lines[0].content_xml == "<d>重雲</d>濕草衣"
    assert llm.calls == []


def test_ambiguous_span_is_resolved_via_single_llm_call_per_poem():
    poem = Poem(
        id="P1",
        lines=[
            Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在"),
            Line(id="L2", order=2, content_xml="<term>重雲</term>濕草衣"),
        ],
    )
    # "先祖"와 "祖遺" 둘 다 사전에 등재되어 힌트(先祖)와 겹치는 후보가 2개 생성됨 -> 애매
    # (segment.generate_candidates는 1글자 표제어를 후보로 만들지 않으므로, 2글자 이상의
    # 겹치는 사전 후보가 최소 2개 있어야 실제로 애매 케이스가 트리거된다)
    # -> LLM이 "先"만 term으로 판단. L2는 "重雲"이 사전 미등재라 LLM 없이 D로 확정됨.
    idx = DictIndex({"先祖", "祖遺"})
    llm = FakeLLMClient(
        responses=[
            {
                "resolved_spans": [
                    {"line_id": "L1", "start": 0, "end": 1, "text": "先", "label": "term"},
                ]
            }
        ]
    )

    result, flags = classify_poem_terms(poem, idx, llm)

    assert len(llm.calls) == 1  # 시 1편당 1회로 묶임
    assert "<term>先</term>" in result.lines[0].content_xml
    assert any(f["poem_id"] == "P1" for f in flags)
    # 플래그 딕셔너리는 QA 로그 규격({"poem_id", "item", "reason"})을 따른다
    # (Task 7의 interpretive_classify.py와 동일 스키마, item은 고정 문자열 "term/D")
    assert flags[0]["item"] == "term/D"
    assert "L1" in flags[0]["reason"]

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


def test_line_with_multiple_term_tags_all_get_reclassified():
    poem = Poem(
        id="P19425",
        lines=[Line(id="L1", order=1, content_xml="<term>先祖</term><term>翼成</term>公寧越懸板韻")],
    )
    idx = DictIndex({"先祖"})  # "翼成"은 사전 미등재
    llm = FakeLLMClient(responses=[])

    result, flags = classify_poem_terms(poem, idx, llm)

    assert "<term>先祖</term>" in result.lines[0].content_xml
    assert "<d>翼成</d>" in result.lines[0].content_xml


def test_term_tag_with_nested_rhyme_tag_is_preserved_and_reclassified():
    # 실제 지천집 P1942502 라인 형태: 두 번째 <term>이 <rhyme>을 품고 있다.
    # 옛 _strip_tags/_existing_hint(단일 hint)는 <rhyme> 마크업 문자까지 힌트
    # 길이에 포함시켜 사전 조회를 오염시키고, 두 번째 태그 자체도 처리하지
    # 못했다(단일-hint 한계). 다중-hint 버전에서도 rhyme 마크업을 순수 텍스트
    # 계산에서 제외하지 않으면 "御風" 대신 "御<rhyme>風</rhyme>" 같은 오염된
    # 문자열로 사전을 조회하게 되어 term/D 판정이 항상 틀어진다.
    poem = Poem(
        id="P19425",
        lines=[Line(id="L2", order=2, content_xml="<term>玄孫</term>又<term>御<rhyme>風</rhyme></term>")],
    )
    idx = DictIndex({"玄孫"})  # "御風"은 사전 미등재
    llm = FakeLLMClient(responses=[])

    result, flags = classify_poem_terms(poem, idx, llm)

    assert result.lines[0].content_xml == "<term>玄孫</term>又<d>御<rhyme>風</rhyme></d>"


def test_missing_line_id_in_resolved_spans_falls_back_to_original_term_hint():
    # L1과 L2 둘 다 애매(사전에 겹치는 후보 2개 이상)해서 LLM에 보내지지만,
    # FakeLLMClient의 응답에는 L2에 대한 resolved_spans 항목이 아예 없다.
    poem = Poem(
        id="P1",
        lines=[
            Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在"),
            Line(id="L2", order=2, content_xml="<term>重雲</term>濕草衣"),
        ],
    )
    idx = DictIndex({"先祖", "祖遺", "重雲", "雲濕"})
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

    # L2는 LLM 응답이 없었지만 정보가 사라지지 않고 원래 힌트(重雲, 0-2)가
    # <term>으로 보존되어야 한다.
    assert "<term>重雲</term>" in result.lines[1].content_xml
    assert any(
        f["item"] == "term/D" and "L2" in f["reason"] and "누락" in f["reason"] for f in flags
    )


def test_hallucinated_line_id_in_resolved_spans_is_skipped_not_crashed():
    poem = Poem(
        id="P1",
        lines=[Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在")],
    )
    idx = DictIndex({"先祖", "祖遺"})  # 애매 -> LLM 호출 트리거
    llm = FakeLLMClient(
        responses=[
            {
                "resolved_spans": [
                    {"line_id": "L1", "start": 0, "end": 1, "text": "先", "label": "term"},
                    # L99는 ambiguous_requests에 없던 line_id (환각) -- KeyError 없이
                    # 안전하게 무시되어야 한다.
                    {"line_id": "L99", "start": 0, "end": 1, "text": "X", "label": "term"},
                ]
            }
        ]
    )

    result, flags = classify_poem_terms(poem, idx, llm)  # KeyError가 나면 안 됨

    assert "<term>先</term>" in result.lines[0].content_xml
    assert any(f["item"] == "term/D" and "L99" in f["reason"] for f in flags)


def test_bare_rhyme_tag_outside_any_term_is_left_untouched():
    # 실제 지천집 P1942504 라인 형태: <rhyme>이 어떤 <term>에도 속하지 않는다.
    poem = Poem(
        id="P19425",
        lines=[Line(id="L4", order=4, content_xml="<term>撫古</term>一江<rhyme>空</rhyme>")],
    )
    idx = DictIndex({"撫古"})
    llm = FakeLLMClient(responses=[])

    result, flags = classify_poem_terms(poem, idx, llm)

    assert result.lines[0].content_xml == "<term>撫古</term>一江<rhyme>空</rhyme>"

import json

from src.llm_client import FakeLLMClient
from src.poem_model import Line, Poem
from src.dict_index import DictIndex
from experiments.staged_classify import classify_form, classify_couplet, classify_term_d, classify_theme


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


def test_term_d_llm_proposes_spans_without_seeing_dictionary():
    poem = Poem(
        id="P4",
        lines=[Line(id="L1", order=1, content_xml="夜伴林僧宿")],  # 태그 없는 순수 원문
    )
    # "無關語"는 원문에 전혀 등장하지 않는 미끼(sentinel) 사전 표제어. "林僧"은 원문에도
    # 등장하므로 그것만으로는 leak 여부를 판별할 수 없다 -- user_prompt에 있어도 그냥
    # 원문 텍스트일 뿐 사전 후보 주입인지 구분이 안 된다. 미끼 표제어가 프롬프트
    # 어디에도 없어야 "사전 후보를 프롬프트에 넣지 않았다"를 실제로 검증한 것이 된다.
    idx = DictIndex({"林僧", "無關語"})
    llm = FakeLLMClient(responses=[{"spans": [{"line_id": "L1", "text": "林僧"}]}])

    result, flags = classify_term_d(poem, idx, llm)

    # 시스템 프롬프트 문자열 자체에 사전 후보가 하드코딩되어 있지 않은지 확인
    assert "林僧" not in llm.calls[0]["system"]
    # system/user/schema를 통틀어 원문에 없는 미끼 표제어가 절대 등장하면 안 됨 --
    # 등장한다면 프롬프트 조립 코드가 dict_index를 참조해 사전 후보를 주입했다는 뜻
    call_json = json.dumps(llm.calls[0], ensure_ascii=False)
    assert "無關語" not in call_json
    assert result.lines[0].content_xml == "夜伴<term>林僧</term>宿"
    assert flags == []


def test_term_d_out_of_order_spans_all_resolve_correctly():
    # LLM 응답의 span 순서가 시구 내 읽기 순서와 다를 수 있다 (林僧이 원문에서는
    # 뒤에 나오지만 응답 리스트에서는 먼저 나옴). 단일 커서로 순서대로만 찾으면
    # 뒤에 나오는 "夜伴"을 못 찾고 환각으로 오판하게 된다 -- 이를 방지해야 한다.
    poem = Poem(
        id="P8",
        lines=[Line(id="L1", order=1, content_xml="夜伴林僧宿")],
    )
    idx = DictIndex(set())
    llm = FakeLLMClient(
        responses=[
            {
                "spans": [
                    {"line_id": "L1", "text": "林僧"},  # 원문에서는 뒤(index 2)
                    {"line_id": "L1", "text": "夜伴"},  # 원문에서는 앞(index 0)
                ]
            }
        ]
    )

    result, flags = classify_term_d(poem, idx, llm)

    assert result.lines[0].content_xml == "<d>夜伴</d><d>林僧</d>宿"
    assert flags == []


def test_term_d_repeated_text_picks_the_intended_later_occurrence():
    # "山中"이 시구에 두 번 등장한다(index 0과 index 3). LLM은 "花"(index 2) 다음에
    # 두 번째 "山中"(index 3)을 의도해서 반환한다. 단순히 "겹치지 않는 가장 왼쪽
    # occurrence"만 찾으면 이미 처리된 앞부분과 안 겹치는 첫 번째 "山中"(index 0)을
    # 잘못 골라버린다 -- 환각 플래그도 없이 조용히 틀린 위치에 태그가 붙는 버그.
    # claimed 구간의 가장 오른쪽 끝 이후에서 먼저 찾도록 하여 반복 텍스트에서
    # "다음에 나오는" occurrence를 올바르게 선택해야 한다.
    poem = Poem(
        id="P9",
        lines=[Line(id="L1", order=1, content_xml="山中花山中")],
    )
    idx = DictIndex(set())
    llm = FakeLLMClient(
        responses=[
            {
                "spans": [
                    {"line_id": "L1", "text": "花"},
                    {"line_id": "L1", "text": "山中"},  # 의도: 두 번째 山中(index 3)
                ]
            }
        ]
    )

    result, flags = classify_term_d(poem, idx, llm)

    # 첫 번째 "山中"(index 0)은 그대로 남고, "花" 뒤의 두 번째 "山中"만 태그된다
    assert result.lines[0].content_xml == "山中<d>花</d><d>山中</d>"
    assert flags == []


def test_term_d_span_not_in_dictionary_becomes_d():
    poem = Poem(
        id="P5",
        lines=[Line(id="L1", order=1, content_xml="重雲濕草衣")],
    )
    idx = DictIndex(set())  # 빈 사전 -> 무조건 미등재
    llm = FakeLLMClient(responses=[{"spans": [{"line_id": "L1", "text": "重雲"}]}])

    result, flags = classify_term_d(poem, idx, llm)

    assert result.lines[0].content_xml == "<d>重雲</d>濕草衣"


def test_term_d_preserves_rhyme_tag_position():
    poem = Poem(
        id="P6",
        lines=[Line(id="L1", order=1, content_xml="草<rhyme>衣</rhyme>")],
    )
    idx = DictIndex({"草衣"})
    llm = FakeLLMClient(responses=[{"spans": [{"line_id": "L1", "text": "草衣"}]}])

    result, flags = classify_term_d(poem, idx, llm)

    assert result.lines[0].content_xml == "<term>草<rhyme>衣</rhyme></term>"


def test_term_d_hallucinated_span_text_is_flagged_and_skipped():
    poem = Poem(
        id="P7",
        lines=[Line(id="L1", order=1, content_xml="夜伴林僧宿")],
    )
    idx = DictIndex(set())
    llm = FakeLLMClient(responses=[{"spans": [{"line_id": "L1", "text": "存在しない"}]}])

    result, flags = classify_term_d(poem, idx, llm)

    assert result.lines[0].content_xml == "夜伴林僧宿"  # 원문 그대로, 태그 없음
    assert len(flags) == 1
    assert flags[0]["item"] == "term/D"


def test_theme_uses_term_tagged_poem_as_context():
    poem = Poem(
        id="P8",
        title_xml="贈<d>眞鑑</d>",
        lines=[
            Line(id="L1", order=1, content_xml="夜伴<term>林僧</term>宿"),
            Line(id="L2", order=2, content_xml="<d>重雲</d>濕<term>草<rhyme>衣</rhyme></term>"),
        ],
    )
    llm = FakeLLMClient(
        responses=[
            {
                "themes": [
                    {"category": "donate", "basis": "title", "evidence": "贈", "label_ko": "기증"},
                    {
                        "category": "buddhism",
                        "basis": "term",
                        "evidence": "林僧 草衣",
                        "label_ko": "불교",
                    },
                ]
            }
        ]
    )

    result, flags = classify_theme(poem, llm)

    # term/D 태깅이 유지된 채 LLM에 전달되었는지 확인 (plain text로 대체되면
    # 조용히 통과해서는 안 됨 -- Theme 단계는 term/D 태깅을 근거로 판단해야 한다)
    assert "<term>林僧</term>" in llm.calls[0]["user"]
    assert "<d>重雲</d>" in llm.calls[0]["user"]

    assert len(result.themes) == 2
    assert result.themes[0].category == "donate"
    assert flags == []


def test_theme_evidence_hallucination_is_rejected():
    poem = Poem(id="P9", title_xml="題", lines=[Line(id="L1", order=1, content_xml="山")])
    llm = FakeLLMClient(
        responses=[
            {
                "themes": [
                    {
                        "category": "farewell",
                        "basis": "term",
                        "evidence": "존재하지않는단어",
                        "label_ko": "송별",
                    }
                ]
            }
        ]
    )

    result, flags = classify_theme(poem, llm)

    assert result.themes == []
    assert len(flags) == 1
    assert flags[0]["item"] == "Theme"

from src.llm_client import FakeLLMClient
from src.poem_model import Line, Poem
from src.interpretive_classify import classify_form_couplet_theme


def _quatrain():
    return Poem(
        id="P1",
        title_xml="贈<d>眞鑑</d>",
        lines=[
            Line(id="L1", order=1, content_xml="夜伴<term>林僧</term>宿"),
            Line(id="L2", order=2, content_xml="<d>重雲</d>濕<term>草衣</term>"),
            Line(id="L3", order=3, content_xml="<term>巖扉</term>開<term>晩日</term>"),
            Line(id="L4", order=4, content_xml="<d>棲鳥</d>始<term>驚飛</term>"),
        ],
        charactercount="오언",
    )


def test_quatrain_gets_basetype_and_detailtype_from_llm():
    llm = FakeLLMClient(
        responses=[
            {
                "basetype": "근체시",
                "detailtype": "절구",
                "couplets": [],
                "themes": [
                    {"category": "donate", "basis": "title", "evidence": "贈", "label_ko": "기증"},
                    {
                        "category": "buddhism",
                        "basis": "term",
                        "evidence": "林僧 草衣",
                        "label_ko": "불교",
                    },
                ],
            }
        ]
    )

    result, flags = classify_form_couplet_theme(_quatrain(), llm)

    assert result.basetype == "근체시"
    assert result.detailtype == "절구"
    assert len(result.themes) == 2
    assert result.themes[0].category == "donate"


def test_couplet_flags_are_applied_to_matching_lines():
    poem = Poem(
        id="P2",
        title_xml="題",
        lines=[Line(id=f"L{i}", order=i, content_xml="字字字") for i in range(1, 9)],
        charactercount="오언",
    )
    llm = FakeLLMClient(
        responses=[
            {
                "basetype": "근체시",
                "detailtype": "율시",
                "couplets": [[5, 6]],
                "themes": [],
            }
        ]
    )

    result, flags = classify_form_couplet_theme(poem, llm)

    in_couplet_orders = [ln.order for ln in result.lines if ln.in_couplet]
    assert in_couplet_orders == [5, 6]


def test_evidence_spanning_title_line_boundary_is_flagged_and_dropped():
    # title_plain("贈眞鑑") ends with "鑑" and line 1's plain text ("夜伴林僧宿") starts
    # with "夜". Naive concatenation without a separator would make "鑑夜" a substring
    # of full_text even though these two characters are never actually adjacent in the
    # poem (they only touch because title and body got joined). A fabricated evidence
    # of "鑑夜" must be rejected, not accepted.
    llm = FakeLLMClient(
        responses=[
            {
                "basetype": "근체시",
                "detailtype": "절구",
                "couplets": [],
                "themes": [
                    {
                        "category": "others",
                        "basis": "title",
                        "evidence": "鑑夜",
                        "label_ko": "기타",
                    }
                ],
            }
        ]
    )

    result, flags = classify_form_couplet_theme(_quatrain(), llm)

    assert result.themes == []
    assert any(f["item"] == "Theme" and "환각 의심" in f["reason"] for f in flags)


def test_evidence_not_found_in_poem_text_is_flagged_and_dropped():
    llm = FakeLLMClient(
        responses=[
            {
                "basetype": "근체시",
                "detailtype": "절구",
                "couplets": [],
                "themes": [
                    {
                        "category": "farewell",
                        "basis": "term",
                        "evidence": "존재하지않는단어",
                        "label_ko": "송별",
                    }
                ],
            }
        ]
    )

    result, flags = classify_form_couplet_theme(_quatrain(), llm)

    assert result.themes == []  # 근거 없는 Theme는 채택하지 않음
    assert any(f["item"] == "Theme" and "환각 의심" in f["reason"] for f in flags)

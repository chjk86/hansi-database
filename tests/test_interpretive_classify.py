from src.llm_client import FakeLLMClient
from src.poem_model import Line, Poem
from src.interpretive_classify import classify_form_couplet_theme, _plain


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


def test_plain_strips_allusion_self_closing_element_entirely():
    # 실제 임백호집 골드 파일 형태(P1714202): <Allusion .../>는 전고(이 프로젝트
    # 범위 밖) 주석이며 속성값(source/originaltext 등)에 시 본문과 무관한 긴
    # 한문 텍스트가 들어있다. 태그 마커만 벗기면 속성값 문자열이 그대로 "순수
    # 텍스트"에 섞여 LLM 프롬프트/환각 검증에 오염을 일으키므로 요소 전체가
    # 사라져야 한다.
    xml_fragment = (
        "<d>北客</d>困<d>炊<rhyme>蒸</rhyme></d>"
        '<Allusion id="" target="炊蒸" type="D" source="昌黎先生集" '
        'chapter="鄭羣贈簟" originaltext="自從五月困暑濕 如坐深甑遭烝炊"/>'
    )

    plain = _plain(xml_fragment)

    assert "Allusion" not in plain
    assert "昌黎先生集" not in plain
    assert "originaltext" not in plain
    assert plain == "北客困炊蒸"


def test_plain_strips_inline_annotation_element_entirely():
    # 실제 임백호집 골드 파일 형태(P1709104): <Line> 안에 등장하는 <Annotation>은
    # poem-level Metadata의 <Annotation>(별도 필드, poem.annotation)과 다른,
    # 편집자가 달아둔 인라인 주석이다. 이 역시 시 본문이 아니므로 완전히
    # 제거되어야 한다.
    xml_fragment = "<d>蘿逕</d>有<term>遺<rhyme>蹤</rhyme></term><Annotation>毗盧頂 人跡不到</Annotation>"

    plain = _plain(xml_fragment)

    assert "Annotation" not in plain
    assert "毗盧頂" not in plain
    assert plain == "蘿逕有遺蹤"


def test_evidence_hallucination_check_ignores_allusion_attribute_text():
    # evidence 환각 검증(full_text)도 _plain을 통해 만들어지므로, Allusion 속성값
    # 안에 우연히 등장하는 한자 조합을 LLM이 evidence로 제출해도 "실제 시에 등장"
    # 한 것으로 잘못 검증되면 안 된다.
    poem = Poem(
        id="P1",
        title_xml="題",
        lines=[
            Line(
                id="L1",
                order=1,
                content_xml=(
                    "<d>北客</d>困<d>炊蒸</d>"
                    '<Allusion id="" target="炊蒸" type="D" source="昌黎先生集" '
                    'chapter="鄭羣贈簟" originaltext="自從五月困暑濕"/>'
                ),
            )
        ],
        charactercount="오언",
    )
    llm = FakeLLMClient(
        responses=[
            {
                "basetype": "근체시",
                "detailtype": "절구",
                "couplets": [],
                "themes": [
                    {
                        "category": "others",
                        "basis": "term",
                        "evidence": "昌黎先生集",
                        "label_ko": "기타",
                    }
                ],
            }
        ]
    )

    result, flags = classify_form_couplet_theme(poem, llm)

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

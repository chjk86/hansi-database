from src.poem_model import Line, Poem, ThemeTag
from src.validate import validate_poem


def test_valid_poem_has_no_issues():
    poem = Poem(
        id="P1",
        title_xml="題",
        lines=[Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在")],
        themes=[ThemeTag(category="donate", basis="title", evidence="題", label_ko="기증")],
    )
    issues = validate_poem(poem, original_plain_lookup={"L1": "先祖遺蹤在"})
    assert issues == []


def test_span_text_drift_is_detected():
    poem = Poem(
        id="P1",
        lines=[Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在")],
    )
    # 원문은 "先祖山蹤在"인데 태깅 결과 텍스트가 "先祖遺蹤在"로 달라짐 -> 훼손 감지
    issues = validate_poem(poem, original_plain_lookup={"L1": "先祖山蹤在"})
    assert any("원문 훼손" in issue for issue in issues)


def test_couplet_on_quatrain_is_detected():
    poem = Poem(
        id="P1",
        detailtype="절구",
        lines=[
            Line(id="L1", order=1, content_xml="字"),
            Line(id="L2", order=2, content_xml="字", in_couplet=True),
            Line(id="L3", order=3, content_xml="字", in_couplet=True),
            Line(id="L4", order=4, content_xml="字"),
        ],
    )
    issues = validate_poem(poem, original_plain_lookup={"L1": "字", "L2": "字", "L3": "字", "L4": "字"})
    assert any("절구에 Couplet" in issue for issue in issues)

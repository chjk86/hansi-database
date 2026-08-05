from src.poem_model import Line, Poem, ThemeTag
from experiments.build_report import build_comparison_report


def _poem(basetype, themes):
    return Poem(
        id="P1",
        title_xml="題",
        basetype=basetype,
        detailtype="절구",
        lines=[Line(id="L1", order=1, content_xml="<term>山</term>水")],
        themes=themes,
    )


def test_report_lists_each_model_result_for_same_poem():
    model_outputs = {
        "claude-opus-4.7": [_poem("근체시", [ThemeTag("mountain", "term", "山", "산악")])],
        "gemini-3-flash-preview": [_poem("근체시", [])],
        "gpt-5.5": [_poem("고체시", [ThemeTag("water", "term", "水", "강해")])],
    }

    report = build_comparison_report(model_outputs)

    assert "P1" in report
    assert "claude-opus-4.7" in report
    assert "gemini-3-flash-preview" in report
    assert "gpt-5.5" in report
    assert "산악" in report  # Claude 결과의 주제 라벨이 리포트에 나타나야 함
    assert "고체시" in report  # GPT 결과의 형식 판정이 리포트에 나타나야 함


def test_report_handles_mismatched_poem_counts_gracefully():
    # 한 모델이 크레딧 부족으로 중간에 멈춰 poem 수가 다를 수 있음
    model_outputs = {
        "claude-opus-4.7": [_poem("근체시", [])],
        "gemini-3-flash-preview": [],
    }

    report = build_comparison_report(model_outputs)

    assert "gemini-3-flash-preview" in report
    assert "결과 없음" in report or "누락" in report

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


def test_report_includes_원문_section_when_present_in_model_outputs():
    # 설계 스펙의 리포트 레이아웃은 원문 -> Claude -> Gemini -> GPT다. run_comparison.py의
    # main()이 output_원문.xml을 쓰고 build_report.py의 main()이 그걸 model_outputs
    # 의 "원문" 키로 넘긴다고 가정할 때, build_comparison_report는 다른 모델과
    # 동일한 매커니즘으로 원문 섹션을 렌더링할 수 있어야 한다 (특수 케이스 코드 없이).
    model_outputs = {
        "원문": [_poem("", [])],
        "claude-opus-4.7": [_poem("근체시", [])],
    }

    report = build_comparison_report(model_outputs)

    assert "--- 원문 ---" in report
    # 원문이 model_outputs에 실제로 존재하므로 "결과 없음" 처리가 잘못 걸리면 안 된다
    sections = report.split("--- ")
    wonmun_section = next(s for s in sections if s.startswith("원문"))
    assert "결과 없음" not in wonmun_section
    # 원문 섹션이 claude 섹션보다 먼저 나와야 한다 (원문 -> Claude -> ... 순서)
    assert report.index("--- 원문 ---") < report.index("--- claude-opus-4.7 ---")


def test_report_shows_failure_marker_for_crashed_poem_not_empty_result():
    # 실패(예: classify_form에서 RetryExhaustedError)와 "정상 처리됐지만 결과가
    # 없음"은 render 결과가 똑같으면 안 된다 -- qa_flags에 "처리 실패" 행이 있는
    # 모델의 섹션에서만 실패 표시가 나타나야 한다.
    model_outputs = {
        "claude-opus-4.7": [_poem("근체시", [])],  # 정상 처리, 주제만 없음
        "gpt-5.5": [_poem("", [])],  # classify_form에서 실패해 미분류 상태로 남음
    }
    qa_flags = {
        "gpt-5.5": {
            "P1": [
                {
                    "poem_id": "P1",
                    "collection": "지천집",
                    "item": "처리 실패",
                    "reason": "[gpt-5.5] RetryExhaustedError: ...",
                }
            ]
        },
    }

    report = build_comparison_report(model_outputs, qa_flags)

    sections = report.split("--- ")
    claude_section = next(s for s in sections if s.startswith("claude-opus-4.7"))
    gpt_section = next(s for s in sections if s.startswith("gpt-5.5"))

    assert "처리 실패" not in claude_section
    assert "(없음)" in claude_section  # 정상적인 "주제 없음"은 그대로 보여야 함
    assert "처리 실패" in gpt_section

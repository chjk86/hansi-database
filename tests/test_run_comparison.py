from src.dict_index import DictIndex
from src.llm_client import FakeLLMClient
from src.poem_model import Line, Poem
from experiments.run_comparison import run_staged_pipeline


def test_run_staged_pipeline_processes_quatrain_without_couplet_call():
    poem = Poem(
        id="P1",
        title_xml="題",
        lines=[Line(id=f"L{i}", order=i, content_xml="字字") for i in range(1, 5)],
        charactercount="오언",
    )
    idx = DictIndex(set())
    # 절구(4구)이므로 Couplet 호출은 없어야 함 -> Form, term/D, Theme 3번만 큐에 준비
    llm = FakeLLMClient(
        responses=[
            {"basetype": "근체시", "detailtype": "율시"},  # Form (detailtype은 규칙으로 덮임)
            {"spans": []},  # term/D
            {"themes": []},  # Theme
        ]
    )

    result_poems, qa_log = run_staged_pipeline([poem], idx, llm, model_label="test-model")

    assert len(result_poems) == 1
    assert result_poems[0].detailtype == "절구"
    assert len(llm.calls) == 3  # Couplet 호출이 생략되었는지 확인


def test_run_staged_pipeline_calls_couplet_for_yulsi():
    poem = Poem(
        id="P2",
        title_xml="題",
        lines=[Line(id=f"L{i}", order=i, content_xml="字字") for i in range(1, 9)],
        charactercount="오언",
    )
    idx = DictIndex(set())
    llm = FakeLLMClient(
        responses=[
            {"basetype": "근체시", "detailtype": "율시"},  # Form
            {"couplets": []},  # Couplet
            {"spans": []},  # term/D
            {"themes": []},  # Theme
        ]
    )

    result_poems, qa_log = run_staged_pipeline([poem], idx, llm, model_label="test-model")

    assert len(llm.calls) == 4  # 8구=율시이므로 Couplet 호출이 있어야 함


def test_run_staged_pipeline_keeps_term_flags_when_theme_step_later_fails():
    # term/D 단계가 성공해 QA 플래그를 만들어냈는데, 그 뒤 Theme 단계가 (예:
    # RetryExhaustedError로) 실패하면, 이전에는 term_flags가 theme_flags와 같은
    # qa_log.add 루프에 함께 묶여 있어서 Theme가 실패하는 순간 term/D 플래그까지
    # 통째로 유실됐다. term/D 성공 직후 바로 기록되어야 이 시나리오에서도
    # term/D 플래그가 살아남는다.
    poem = Poem(
        id="P_TERM_THEN_THEME_FAIL",
        title_xml="題",
        lines=[Line(id="L1", order=1, content_xml="字字")],
        charactercount="오언",
    )
    idx = DictIndex(set())
    llm = FakeLLMClient(
        responses=[
            {"basetype": "고체시", "detailtype": "고시"},  # Form
            {"spans": [{"line_id": "L1", "text": "不存在"}]},  # term/D: 원문에 없는
            # 텍스트 -> 환각 의심 플래그 발생. 그 뒤 Theme 응답을 큐에 넣지 않아
            # classify_theme 호출 시 FakeLLMClient가 RetryExhaustedError를 던진다.
        ]
    )

    result_poems, qa_log = run_staged_pipeline([poem], idx, llm, model_label="test-model")

    assert len(result_poems) == 1
    # term/D 플래그는 Theme의 실패와 무관하게 기록되어 있어야 한다
    assert qa_log.has_entry("P_TERM_THEN_THEME_FAIL", "term/D")
    # Theme 단계 실패 자체도 "처리 실패"로 기록된다
    assert qa_log.has_entry("P_TERM_THEN_THEME_FAIL", "처리 실패")


def test_run_staged_pipeline_continues_after_poem_failure():
    # P_OK(절구, 4구)가 먼저 처리되어 정확히 3개 응답(Form/term-D/Theme, Couplet은
    # 절구라 생략)을 전부 소비한다. 그다음 P_FAIL 처리 시 큐가 완전히 비어 있으므로
    # classify_form의 첫 호출에서 FakeLLMClient가 RetryExhaustedError를 던진다 --
    # 이 실패가 P_OK의 결과나 이후 처리에 영향을 주지 않는지 검증한다.
    poems = [
        Poem(
            id="P_OK",
            title_xml="B",
            lines=[Line(id=f"L{i}", order=i, content_xml="字字") for i in range(1, 5)],
            charactercount="오언",
        ),
        Poem(id="P_FAIL", title_xml="A", lines=[Line(id="L1", order=1, content_xml="字字字字")], charactercount="오언"),
    ]
    idx = DictIndex(set())
    llm = FakeLLMClient(
        responses=[
            {"basetype": "근체시", "detailtype": "율시"},  # P_OK Form (detailtype은 규칙으로 절구로 덮임)
            {"spans": []},  # P_OK term/D
            {"themes": []},  # P_OK Theme
            # P_FAIL 차례엔 큐가 비어 있어 classify_form이 RetryExhaustedError로 실패한다
        ]
    )

    result_poems, qa_log = run_staged_pipeline(poems, idx, llm, model_label="test-model")

    assert len(result_poems) == 2  # P_FAIL도 원본 그대로 결과 리스트에 포함됨
    ok_result = next(p for p in result_poems if p.id == "P_OK")
    assert ok_result.detailtype == "절구"  # P_OK는 정상적으로 끝까지 처리됨
    fail_result = next(p for p in result_poems if p.id == "P_FAIL")
    assert fail_result.basetype == ""  # P_FAIL은 classify_form에서 실패해 미분류 상태로 남음

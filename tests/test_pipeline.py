import json

from src.dict_index import DictIndex
from src.llm_client import FakeLLMClient
from src.pipeline import run_pipeline
from src.xml_io import parse_collection, write_collection
from src.poem_model import Line, Poem


class _FailFirstThenSucceedLLMClient:
    """첫 호출은 예외를 발생시키고, 이후 호출은 지정된 응답을 순서대로 반환한다.
    개별 시 처리 실패가 전체 파이프라인을 중단시키지 않는지 검증하기 위한 테스트 전용 스텁.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def complete(self, system, user, response_schema):
        self.calls.append({"system": system, "user": user, "schema": response_schema})
        if len(self.calls) == 1:
            raise RuntimeError("simulated LLM failure on first poem")
        return self._responses.pop(0)


def _write_fixture(path):
    poems = [
        Poem(
            id="P1",
            title_xml="題",
            lines=[
                Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L2", order=2, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L3", order=3, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L4", order=4, content_xml="<term>先祖</term>遺蹤在"),
            ],
            charactercount="오언",
        )
    ]
    write_collection(path, poems)


def test_pipeline_produces_output_and_qa_files(tmp_path):
    input_path = tmp_path / "in.xml"
    _write_fixture(input_path)
    output_path = tmp_path / "out.xml"
    qa_path = tmp_path / "qa.csv"
    checkpoint_path = tmp_path / "checkpoint.json"

    dict_index = DictIndex({"先祖"})
    llm = FakeLLMClient(
        responses=[
            {
                "basetype": "근체시",
                "detailtype": "절구",
                "couplets": [],
                "themes": [],
            }
        ]
    )

    run_pipeline(input_path, output_path, qa_path, checkpoint_path, dict_index, llm, collection_name="테스트문집")

    assert output_path.exists()
    assert qa_path.exists()
    result_poems = parse_collection(output_path)
    assert result_poems[0].basetype == "근체시"


def test_pipeline_skips_already_checkpointed_poems(tmp_path):
    input_path = tmp_path / "in.xml"
    _write_fixture(input_path)
    output_path = tmp_path / "out.xml"
    qa_path = tmp_path / "qa.csv"
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text(json.dumps({"done_poem_ids": ["P1"]}), encoding="utf-8")

    # 이전 실행에서 이미 분류까지 완료된 output_path를 시뮬레이션한다.
    # (체크포인트만 있고 output_path에 결과가 없으면 재처리 대상으로 간주해야 하므로,
    #  이 output_path가 진짜 "이미 처리됨"의 근거가 된다.)
    already_classified = [
        Poem(
            id="P1",
            title_xml="題",
            lines=[
                Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L2", order=2, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L3", order=3, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L4", order=4, content_xml="<term>先祖</term>遺蹤在"),
            ],
            charactercount="오언",
            basetype="근체시",
            detailtype="절구",
        )
    ]
    write_collection(output_path, already_classified)

    dict_index = DictIndex({"先祖"})
    llm = FakeLLMClient(responses=[])  # 호출되면 즉시 실패 -> 스킵됐는지 검증

    run_pipeline(input_path, output_path, qa_path, checkpoint_path, dict_index, llm, collection_name="테스트문집")

    # P1이 체크포인트에 있어 LLM이 호출되지 않아야 함
    assert llm.calls == []

    # 스킵된 P1은 raw input이 아니라 이전 output_path의 분류 결과를 그대로 유지해야 함
    result_poems = parse_collection(output_path)
    assert result_poems[0].basetype == "근체시"
    assert result_poems[0].detailtype == "절구"


def test_pipeline_resume_preserves_couplet_lines(tmp_path):
    """A poem with couplet-paired lines gets <Couplet>-wrapped when written.
    On resume, previously_processed is rebuilt from parse_collection(output_path) --
    this must recover ALL of the poem's lines (not just the non-couplet ones),
    not just its basetype/detailtype fields.
    """
    input_path = tmp_path / "in.xml"
    _write_fixture(input_path)
    output_path = tmp_path / "out.xml"
    qa_path = tmp_path / "qa.csv"
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text(json.dumps({"done_poem_ids": ["P1"]}), encoding="utf-8")

    # 이전 실행에서 이미 분류 및 대장(couplet) 판정까지 완료된 output_path를 시뮬레이션한다.
    already_classified = [
        Poem(
            id="P1",
            title_xml="題",
            lines=[
                Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L2", order=2, content_xml="<term>先祖</term>遺蹤在", in_couplet=True),
                Line(id="L3", order=3, content_xml="<term>先祖</term>遺蹤在", in_couplet=True),
                Line(id="L4", order=4, content_xml="<term>先祖</term>遺蹤在"),
            ],
            charactercount="칠언",
            basetype="근체시",
            detailtype="율시",
        )
    ]
    write_collection(output_path, already_classified)

    dict_index = DictIndex({"先祖"})
    llm = FakeLLMClient(responses=[])  # 호출되면 즉시 실패 -> 스킵됐는지 검증

    run_pipeline(input_path, output_path, qa_path, checkpoint_path, dict_index, llm, collection_name="테스트문집")

    assert llm.calls == []

    result_poems = parse_collection(output_path)
    assert len(result_poems) == 1
    result_lines = result_poems[0].lines
    # 대장(Couplet)으로 묶여 <text>의 손자 노드가 된 L2/L3을 포함해 4구 전부가 살아남아야 함
    assert [ln.id for ln in result_lines] == ["L1", "L2", "L3", "L4"]
    assert [ln.order for ln in result_lines] == [1, 2, 3, 4]
    assert all(ln.content_xml == "<term>先祖</term>遺蹤在" for ln in result_lines)

    # in_couplet 플래그 자체도 정확히 복원되어야, resume 도중 매 시마다 이루어지는
    # 증분 write_collection 호출이 다시 <Couplet>로 감싸 쓸 수 있다 (두 번째 write 사이클).
    by_id = {ln.id: ln for ln in result_lines}
    assert by_id["L1"].in_couplet is False
    assert by_id["L2"].in_couplet is True
    assert by_id["L3"].in_couplet is True
    assert by_id["L4"].in_couplet is False

    # run_pipeline이 스킵된 P1을 processed에 넣고 매 시 처리 후 write_collection을 다시
    # 호출하므로(2번째 write 사이클), 최종 파일에도 <Couplet> 래핑이 그대로 남아있어야 한다.
    raw = output_path.read_text(encoding="utf-8")
    assert "<Couplet>" in raw
    assert raw.index("<Couplet>") < raw.index('id="L2"')
    assert raw.index("</Couplet>") > raw.index('id="L3"')


def test_pipeline_continues_after_individual_poem_failure(tmp_path):
    input_path = tmp_path / "in.xml"
    poems = [
        Poem(
            id="P1",
            title_xml="題1",
            lines=[
                Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L2", order=2, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L3", order=3, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L4", order=4, content_xml="<term>先祖</term>遺蹤在"),
            ],
            charactercount="오언",
        ),
        Poem(
            id="P2",
            title_xml="題2",
            lines=[
                Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L2", order=2, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L3", order=3, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L4", order=4, content_xml="<term>先祖</term>遺蹤在"),
            ],
            charactercount="오언",
        ),
    ]
    write_collection(input_path, poems)
    output_path = tmp_path / "out.xml"
    qa_path = tmp_path / "qa.csv"
    checkpoint_path = tmp_path / "checkpoint.json"

    dict_index = DictIndex({"先祖"})
    llm = _FailFirstThenSucceedLLMClient(
        responses=[
            {
                "basetype": "근체시",
                "detailtype": "절구",
                "couplets": [],
                "themes": [],
            }
        ]
    )

    run_pipeline(input_path, output_path, qa_path, checkpoint_path, dict_index, llm, collection_name="테스트문집")

    # P1은 실패했지만 P2는 정상 처리되어야 하고, 전체 실행은 예외 없이 끝나야 함
    result_poems = parse_collection(output_path)
    assert [p.id for p in result_poems] == ["P1", "P2"]
    assert result_poems[1].basetype == "근체시"

    qa_text = qa_path.read_text(encoding="utf-8-sig")
    assert "처리 실패" in qa_text
    assert "P1" in qa_text

    # 실패한 P1은 체크포인트에 기록되지 않아야 재시도 대상이 된다
    checkpoint_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint_data["done_poem_ids"] == ["P2"]

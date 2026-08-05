from pathlib import Path

from src.dict_index import DictIndex
from src.llm_client import LLMClient, TimelyLLMClient
from src.poem_model import Poem
from src.qa_log import QALog
from src.xml_io import parse_collection, write_collection

from experiments.staged_classify import (
    classify_couplet,
    classify_form,
    classify_term_d,
    classify_theme,
)

_EXTRACTED_PATH = (
    Path(__file__).resolve().parent.parent
    / "extracted"
    / "대상데이터_제목내용시어운자대장태그"
    / "태깅_지천집.txt"
)
_OUTPUT_DIR = Path(__file__).resolve().parent / "2026-08-05-model-comparison"

# 슬라이스가 index 0이 아니라 60에서 시작하는 이유: 실제 태깅_지천집.txt는
# index 0-87이 전부 4구(절구)이고 8구(율시) 이상은 index 88부터 시작한다.
# classify_couplet은 basetype=="근체시" and detailtype!="절구"인 경우에만
# 호출되므로, index 0부터 50수를 뽑으면 전부 절구라 Couplet 단계가 표본에서
# 단 한 번도 실행되지 않아 4단계 파이프라인 중 하나가 비교 데이터 없이
# 남는다. index 60-109는 절구 구간의 끝자락과 율시 구간의 시작을 모두
# 포함해 네 단계 전부를 실제로 실행시킨다. 그래도 여전히 고정된 재현
# 가능한 슬라이스다 -- 설계 스펙의 "왜 처음 50수"라는 근거는 재현성이지
# 반드시 index 0이어야 한다는 뜻이 아니었다.
_SLICE_START = 60
_POEM_COUNT = 50

_MODELS = {
    "claude-opus-4.7": "anthropic/claude-opus-4.7",
    "gemini-3-flash-preview": "google/gemini-3-flash-preview",
    "gpt-5.5": "openai/gpt-5.5",
}


def run_staged_pipeline(
    poems: list[Poem], dict_index: DictIndex, llm_client: LLMClient, model_label: str
) -> tuple[list[Poem], QALog]:
    qa_log = QALog()
    results = []

    for poem in poems:
        try:
            poem = classify_form(poem, llm_client)

            if poem.basetype == "근체시" and poem.detailtype != "절구":
                poem = classify_couplet(poem, llm_client)

            poem, term_flags = classify_term_d(poem, dict_index, llm_client)
            for flag in term_flags:
                qa_log.add(flag["poem_id"], "지천집", flag["item"], flag["reason"])

            poem, theme_flags = classify_theme(poem, llm_client)
            for flag in theme_flags:
                qa_log.add(flag["poem_id"], "지천집", flag["item"], flag["reason"])
        except Exception as exc:  # noqa: BLE001
            # poem이 여기서 results에 담기는 시점의 상태는 실패한 단계에 따라
            # 다르다: classify_form에서 실패하면 미분류 상태 그대로이고, 이후
            # 단계(Couplet/term-D/Theme)에서 실패하면 그 앞 단계까지는 이미
            # poem 객체에 in-place로 반영된 "부분 태깅" 상태로 남는다. 어느
            # 쪽이든 QA 로그에 실패가 기록되므로, 재검토가 필요한 시를 판단할
            # 때는 이 QA 로그를 기준으로 삼아야 한다(poem 자체의 필드만 봐서는
            # 완전 처리인지 부분 처리인지 구분할 수 없음).
            qa_log.add(poem.id, "지천집", "처리 실패", f"[{model_label}] {exc}")

        results.append(poem)

    return results, qa_log


def main() -> None:
    dict_index = DictIndex.load(Path(__file__).resolve().parent.parent / ".cache" / "dict_index.pkl")

    # 원문(가공 전) 슬라이스를 그대로 저장해 둔다 -- 지천집에는 Form/Couplet/Theme의
    # 골드 스탠다드가 없으므로, 사전 기반 <term> 태깅이 들어있는 원문이 세 모델의
    # term/D 판정을 비교할 수 있는 유일한 참조 기준이 된다. build_report.py가
    # output_원문.xml로 다시 읽어 리포트에 나란히 배치한다.
    original_poems = parse_collection(_EXTRACTED_PATH)[_SLICE_START : _SLICE_START + _POEM_COUNT]
    write_collection(_OUTPUT_DIR / "output_원문.xml", original_poems)

    for label, model_name in _MODELS.items():
        print(f"=== {label} 실행 중 ===")
        # 매 모델마다 원본 poem 객체를 새로 파싱해 이전 모델의 결과가 섞이지 않게 한다
        poems_for_model = parse_collection(_EXTRACTED_PATH)[_SLICE_START : _SLICE_START + _POEM_COUNT]
        llm_client = TimelyLLMClient(model=model_name)

        result_poems, qa_log = run_staged_pipeline(poems_for_model, dict_index, llm_client, label)

        write_collection(_OUTPUT_DIR / f"output_{label}.xml", result_poems)
        qa_log.write_csv(_OUTPUT_DIR / f"qa_{label}.csv")
        print(f"{label}: {len(result_poems)}수 완료")


if __name__ == "__main__":
    main()

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
            poem, theme_flags = classify_theme(poem, llm_client)

            for flag in term_flags + theme_flags:
                qa_log.add(flag["poem_id"], "지천집", flag["item"], flag["reason"])
        except Exception as exc:  # noqa: BLE001
            qa_log.add(poem.id, "지천집", "처리 실패", f"[{model_label}] {exc}")

        results.append(poem)

    return results, qa_log


def main() -> None:
    all_poems = parse_collection(_EXTRACTED_PATH)
    target_poems = all_poems[:_POEM_COUNT]
    dict_index = DictIndex.load(Path(__file__).resolve().parent.parent / ".cache" / "dict_index.pkl")

    for label, model_name in _MODELS.items():
        print(f"=== {label} 실행 중 ===")
        # 매 모델마다 원본 poem 객체를 새로 파싱해 이전 모델의 결과가 섞이지 않게 한다
        poems_for_model = parse_collection(_EXTRACTED_PATH)[:_POEM_COUNT]
        llm_client = TimelyLLMClient(model=model_name)

        result_poems, qa_log = run_staged_pipeline(poems_for_model, dict_index, llm_client, label)

        write_collection(_OUTPUT_DIR / f"output_{label}.xml", result_poems)
        qa_log.write_csv(_OUTPUT_DIR / f"qa_{label}.csv")
        print(f"{label}: {len(result_poems)}수 완료")


if __name__ == "__main__":
    main()

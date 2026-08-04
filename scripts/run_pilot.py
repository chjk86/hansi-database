"""지천집(224수)을 대상으로 전체 파이프라인을 실행한다."""

from src import config
from src.dict_index import DictIndex
from src.llm_client import GeminiLLMClient
from src.pipeline import run_pipeline

RUN_DATE = "20260804"  # 실행 시 실제 날짜로 교체

if __name__ == "__main__":
    dict_index = DictIndex.load(config.CACHE_DIR / "dict_index.pkl")
    llm_client = GeminiLLMClient(model=config.LLM_MODEL)

    run_pipeline(
        input_path=config.EXTRACTED_DIR / "태깅_지천집.txt",
        output_path=config.OUTPUT_DIR / f"완성본_지천집_황정욱_자동태깅_{RUN_DATE}.xml",
        qa_path=config.QA_DIR / f"지천집_검토필요_{RUN_DATE}.csv",
        checkpoint_path=config.CACHE_DIR / "checkpoint_지천집.json",
        dict_index=dict_index,
        llm_client=llm_client,
        collection_name="지천집",
    )
    print("지천집 파일럿 완료")

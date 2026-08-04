"""임백호집 723수 중 뒤쪽 100수를 hold-out으로 감추고, 파이프라인이 예측한
Theme/Basetype/Couplet을 실제 정답과 대조해 정확도를 출력한다."""

import copy

from src import config
from src.dict_index import DictIndex
from src.interpretive_classify import classify_form_couplet_theme
from src.llm_client import GeminiLLMClient
from src.poem_model import Poem
from src.xml_io import parse_collection

HOLDOUT_SIZE = 100


def _strip_answers(poem: Poem) -> Poem:
    blanked = copy.deepcopy(poem)
    blanked.basetype = ""
    blanked.detailtype = ""
    blanked.themes = []
    for line in blanked.lines:
        line.in_couplet = False
    return blanked


def main() -> None:
    all_poems = parse_collection(config.GOLD_PATH)
    holdout = all_poems[-HOLDOUT_SIZE:]

    dict_index = DictIndex.load(config.CACHE_DIR / "dict_index.pkl")
    llm_client = GeminiLLMClient(model=config.LLM_MODEL)

    basetype_correct = 0
    detailtype_correct = 0
    theme_category_hits = 0
    theme_category_total = 0
    couplet_line_matches = 0
    couplet_line_total = 0

    for gold_poem in holdout:
        blanked = _strip_answers(gold_poem)
        predicted, _ = classify_form_couplet_theme(blanked, llm_client)

        if predicted.basetype == gold_poem.basetype:
            basetype_correct += 1
        if predicted.detailtype == gold_poem.detailtype:
            detailtype_correct += 1

        gold_categories = {t.category for t in gold_poem.themes}
        pred_categories = {t.category for t in predicted.themes}
        theme_category_hits += len(gold_categories & pred_categories)
        theme_category_total += len(gold_categories)

        gold_couplet_orders = {ln.order for ln in gold_poem.lines if ln.in_couplet}
        pred_couplet_orders = {ln.order for ln in predicted.lines if ln.in_couplet}
        couplet_line_matches += len(gold_couplet_orders & pred_couplet_orders)
        couplet_line_total += len(gold_couplet_orders)

    n = len(holdout)
    print(f"hold-out 표본: {n}수")
    print(f"Basetype 정확도: {basetype_correct}/{n} ({basetype_correct/n:.1%})")
    print(f"Detailtype 정확도: {detailtype_correct}/{n} ({detailtype_correct/n:.1%})")
    if theme_category_total:
        print(f"Theme 카테고리 재현율: {theme_category_hits}/{theme_category_total} ({theme_category_hits/theme_category_total:.1%})")
    if couplet_line_total:
        print(f"Couplet 구-라인 재현율: {couplet_line_matches}/{couplet_line_total} ({couplet_line_matches/couplet_line_total:.1%})")


if __name__ == "__main__":
    main()

"""Step 2: clean the raw thesaurus and split it into two confidence tiers.

Rationale (found empirically while tuning against the corpus, see README):
  - Many <term> tags mark generic line-level emphasis, not frontier-specific
    vocabulary, so `term`-only tokens are dropped entirely.
  - Even after that, a handful of very common classical-poetry stock phrases
    (千里, 萬里, 明月, 黃昏, ...) slipped in because they happened to co-occur
    with real frontier evidence at least once. These are demoted to a
    "generic" tier: they never trigger a positive verdict on their own, they
    only get reported as supporting context alongside a real "specific" hit.

Usage: python 02_build_tiers.py
Reads:  ../thesaurus/thesaurus_raw.json
Writes: ../thesaurus/thesaurus_final.json  (merged, cleaned, freq>=2)
        ../thesaurus/thesaurus_tiers.json  (specific / generic_support_only split)
"""
import json
from collections import Counter

RAW_PATH = "../thesaurus/thesaurus_raw.json"
FINAL_PATH = "../thesaurus/thesaurus_final.json"
TIERS_PATH = "../thesaurus/thesaurus_tiers.json"

# Data-entry placeholders left over from an incomplete annotation pass.
PLACEHOLDER = {"한자", "시어", "국문주제명", "영문주제명", ""}

# Manually curated: common classical-poetry stock phrases that are not
# distinctively about the frontier, found by inspecting false positives
# during pilot testing against 눌재집/박상 etc.
STOPWORDS = {
    "千里", "萬里", "平生", "絶句", "不可", "回首", "靑山", "不見", "文章", "天地",
    "風流", "白首", "明月", "先生", "落日", "戰", "悠悠", "歸來", "雪", "關",
    "黃昏", "一片", "千古", "白日", "相思", "西風", "東風", "少年", "昨夜",
    "日暮", "那堪", "何時", "多少", "古詩", "李白", "黃金", "男子", "中國",
    "三千", "高會", "白馬", "民獻", "經營", "日落", "杜陵", "詩史", "不堪",
    "九重", "南北", "堂堂", "上策", "使相", "觀察", "朝廷", "意氣", "書生",
    "蝦蟆", "王家", "匏繫", "天涯", "茫茫", "遠遊",
    "列國", "驅使", "心折", "馬上", "郵亭", "翰墨", "功名", "迍邅", "山城",
}

MIN_FREQ = 2


def main():
    raw = json.load(open(RAW_PATH, encoding="utf-8"))
    term_freq = dict(raw["term_freq"])
    evidence_freq = dict(raw["evidence_freq"])
    allusion_freq = dict(raw["allusion_freq"])

    combined = Counter()
    sources = {}
    for tok, c in term_freq.items():
        if tok in PLACEHOLDER:
            continue
        combined[tok] += c
        sources.setdefault(tok, set()).add("term")
    for tok, c in evidence_freq.items():
        if tok in PLACEHOLDER:
            continue
        combined[tok] += c
        sources.setdefault(tok, set()).add("evidence")

    final = [
        (tok, c, sorted(sources[tok]))
        for tok, c in combined.items()
        if c >= MIN_FREQ
    ]
    final.sort(key=lambda x: -x[1])

    allusion_clean = sorted(
        ((t, c) for t, c in allusion_freq.items() if t and t not in PLACEHOLDER),
        key=lambda x: -x[1],
    )

    json.dump(
        {
            "terms": [{"token": t, "freq": c, "sources": s} for t, c, s in final],
            "allusions": [{"token": t, "freq": c} for t, c in allusion_clean],
        },
        open(FINAL_PATH, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=2,
    )
    print(f"final thesaurus (freq>={MIN_FREQ}): {len(final)} tokens -> {FINAL_PATH}")

    # both-source (term+evidence) tokens plus multi-char evidence-only tokens
    # form the "specific" (decisive) tier; anything in STOPWORDS is demoted
    # to "generic" (supporting-only, never decisive on its own).
    both = {tok for tok, c, s in final if set(s) == {"evidence", "term"}}
    specific = set(both)
    for tok, c, s in final:
        if set(s) == {"evidence"} and len(tok) >= 2:
            specific.add(tok)

    generic = specific & STOPWORDS
    specific -= STOPWORDS

    json.dump(
        {"specific": sorted(specific), "generic_support_only": sorted(generic)},
        open(TIERS_PATH, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=2,
    )
    print(f"specific (decisive) tier: {len(specific)}")
    print(f"generic (supporting-only) tier: {len(generic)}")
    print(f"saved {TIERS_PATH}")


if __name__ == "__main__":
    main()

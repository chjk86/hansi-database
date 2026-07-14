"""Step 8: score the ENTIRE 문집총간 corpus (651 collections, ~368,800 poems)
with the rule-based matcher and the trained TF-IDF model, then produce a
ranked shortlist for LLM verification (see 09_llm_verify_shortlist.py).

Doing this over every individual collection file (not the master aggregate)
matters: many poem titles are reused Yuefu titles (塞下曲, 出塞, 從軍行, ...)
written by dozens of unrelated poets across history. A different poet's own
"塞下曲" is its own candidate poem and must not be silently excluded just
because some other author's "塞下曲" happens to already be gold-tagged --
exclusion-by-title is therefore only applied within the 12 gold-covered
collections (`common.AUTHOR_FILE`), never corpus-wide.

Local scoring of the whole corpus is fast (~30s total); this script does NOT
call any API.

Usage: python 08_score_full_corpus.py --top 1000
Writes: ../results/full_corpus_shortlist.json   (top N candidates for LLM review)
        ../results/full_corpus_scoring_summary.txt
"""
import argparse
import glob
import json
import os
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from common import (
    parse_gold_poems, full_plain, title_plain, author_of, is_frontier,
    load_collection, title_in_gold, AUTHOR_FILE,
)

GOLD_PATH = "../data/변새시_2차정리본.txt"
CORPUS_DIR = "../../2025_munzip_title_text_ver/"
TIERS_PATH = "../thesaurus/thesaurus_tiers.json"
SHORTLIST_PATH = "../results/full_corpus_shortlist.json"
SUMMARY_PATH = "../results/full_corpus_scoring_summary.txt"


def train_model(rule_classify):
    poems = parse_gold_poems(GOLD_PATH)
    pos_texts = [full_plain(p) for p in poems if is_frontier(p)]

    gold_titles = {a: set() for a in AUTHOR_FILE}
    for p in poems:
        a = author_of(p)
        if a in gold_titles:
            gold_titles[a].add(title_plain(p))

    neg_texts = []
    for author, fn in AUTHOR_FILE.items():
        for title, body in load_collection(CORPUS_DIR + fn):
            if title_in_gold(title, gold_titles[author]):
                continue
            full = title + body
            if not rule_classify(full):
                neg_texts.append(full)

    X_texts = pos_texts + neg_texts
    y = np.array([1] * len(pos_texts) + [0] * len(neg_texts))
    vec = TfidfVectorizer(analyzer="char", ngram_range=(2, 3), min_df=2)
    X = vec.fit_transform(X_texts)
    clf = LogisticRegression(class_weight="balanced", max_iter=2000)
    clf.fit(X, y)
    return vec, clf, gold_titles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=1000)
    args = ap.parse_args()

    tiers = json.load(open(TIERS_PATH, encoding="utf-8"))
    specific = set(tiers["specific"])
    rule_classify = lambda t: any(x in t for x in specific)

    t0 = time.time()
    vec, clf, gold_titles = train_model(rule_classify)
    print(f"model trained in {time.time()-t0:.1f}s")

    # collection filename -> author, for the 12 gold-covered files (used to
    # apply title-based exclusion only there).
    file_to_author = {fn: a for a, fn in AUTHOR_FILE.items()}

    files = sorted(
        os.path.basename(p) for p in glob.glob(CORPUS_DIR + "*.txt")
        if os.path.basename(p) != "0000.문집총간한시모음.txt"
    )
    print(f"scoring {len(files)} collection files...")

    all_scores = []  # (fn, title, tfidf_proba, rule_hit)
    t0 = time.time()
    n_poems = 0
    for fn in files:
        rows = load_collection(CORPUS_DIR + fn)
        if not rows:
            continue
        author = file_to_author.get(fn)
        gt = gold_titles.get(author, set()) if author else set()

        titles = []
        texts = []
        for title, body in rows:
            if author and title_in_gold(title, gt):
                continue
            titles.append(title)
            texts.append(title + body)

        if not texts:
            continue
        n_poems += len(texts)
        rule_hits = [rule_classify(t) for t in texts]
        proba = clf.predict_proba(vec.transform(texts))[:, 1]
        for title, p, rh in zip(titles, proba, rule_hits):
            all_scores.append((fn, title, float(p), bool(rh)))

    dt = time.time() - t0
    print(f"scored {n_poems} poems across {len(files)} files in {dt:.1f}s")

    all_scores.sort(key=lambda x: -x[2])
    top = all_scores[:args.top]

    json.dump(
        [{"file": fn, "title": t, "tfidf_proba": p, "rule_hit": rh} for fn, t, p, rh in top],
        open(SHORTLIST_PATH, "w", encoding="utf-8"),
        ensure_ascii=False, indent=2,
    )

    n_tfidf_pos = sum(1 for _, _, p, _ in all_scores if p >= 0.5)
    n_rule_hit = sum(1 for _, _, _, rh in all_scores if rh)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write(f"total poems scored (excluding gold-known within the 12 collections): {n_poems}\n")
        f.write(f"scoring time: {dt:.1f}s\n")
        f.write(f"TF-IDF proba >= 0.5: {n_tfidf_pos} ({n_tfidf_pos/n_poems*100:.2f}%)\n")
        f.write(f"rule-based hit: {n_rule_hit} ({n_rule_hit/n_poems*100:.2f}%)\n\n")
        f.write(f"top {args.top} shortlist saved to {SHORTLIST_PATH}\n\n")
        f.write("=== top 50 preview ===\n")
        for fn, t, p, rh in top[:50]:
            f.write(f"{p:.3f}\t{'rule' if rh else '    '}\t{fn}\t{t}\n")

    print(f"TF-IDF>=0.5: {n_tfidf_pos} ({n_tfidf_pos/n_poems*100:.2f}%)   rule-hit: {n_rule_hit} ({n_rule_hit/n_poems*100:.2f}%)")
    print(f"saved shortlist ({len(top)}) to {SHORTLIST_PATH}")
    print(f"saved summary to {SUMMARY_PATH}")


if __name__ == "__main__":
    main()

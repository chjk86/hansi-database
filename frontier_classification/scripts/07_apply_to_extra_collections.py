"""Step 7: apply the trained classifiers to the 8 collections that have no
gold labels yet (`common.EXTRA_COLLECTION_FILE`) -- the "확대 적용" stage from
the research proposal.

For each poem in those collections this reports:
  - rule: whether any "specific" thesaurus term hits (see 03_rule_classifier.py)
  - tfidf_proba: the TF-IDF+LogisticRegression model's predicted probability

Since there is no ground truth here, results are for triage/review, not a
final verdict -- rank by tfidf_proba and read the top of each collection.

Usage: python 07_apply_to_extra_collections.py [--top 40]
Writes: ../results/extra_collections_scored.txt
"""
import argparse
import json

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from common import (
    parse_gold_poems, full_plain, title_plain, author_of, is_frontier,
    load_collection, title_in_gold, AUTHOR_FILE, EXTRA_COLLECTION_FILE,
)

GOLD_PATH = "../data/변새시_2차정리본.txt"
CORPUS_BASE = "../../2025_munzip_title_text_ver/"
TIERS_PATH = "../thesaurus/thesaurus_tiers.json"
OUT_PATH = "../results/extra_collections_scored.txt"


def rule_classify_factory():
    specific = set(json.load(open(TIERS_PATH, encoding="utf-8"))["specific"])
    return lambda text: any(t in text for t in specific)


def train_model(rule_classify):
    """Same training recipe as 04_tfidf_classifier.py: gold positives vs.
    same-author poems the rule-based matcher doesn't flag at all."""
    poems = parse_gold_poems(GOLD_PATH)
    pos_texts = [full_plain(p) for p in poems if is_frontier(p)]

    gold_titles = {a: set() for a in AUTHOR_FILE}
    for p in poems:
        a = author_of(p)
        if a in gold_titles:
            gold_titles[a].add(title_plain(p))

    neg_texts = []
    for author, fn in AUTHOR_FILE.items():
        for title, body in load_collection(CORPUS_BASE + fn):
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
    print(f"trained on {len(pos_texts)} positive / {len(neg_texts)} negative")
    return vec, clf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=40, help="how many top-scoring poems to print per collection")
    args = ap.parse_args()

    rule_classify = rule_classify_factory()
    vec, clf = train_model(rule_classify)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for coll_name, fn in EXTRA_COLLECTION_FILE.items():
            rows = load_collection(CORPUS_BASE + fn)
            texts = [title + body for title, body in rows]
            rule_hits = [rule_classify(t) for t in texts]
            proba = clf.predict_proba(vec.transform(texts))[:, 1]

            order = np.argsort(proba)[::-1]
            n_rule = sum(rule_hits)
            n_tfidf = int((proba >= 0.5).sum())

            f.write(f"\n=== {coll_name} ({fn}) : {len(rows)}수, "
                    f"규칙기반 걸림 {n_rule}건, TF-IDF>=0.5 {n_tfidf}건 ===\n")
            shown = 0
            for i in order:
                if proba[i] < 0.3:
                    break
                title = rows[i][0]
                f.write(f"{proba[i]:.3f}\t{'rule' if rule_hits[i] else '    '}\t{title}\n")
                shown += 1
                if shown >= args.top:
                    break

            print(f"{coll_name}: {len(rows)}수, 규칙기반 {n_rule}건, TF-IDF>=0.5 {n_tfidf}건")

    print(f"\nsaved {OUT_PATH}")


if __name__ == "__main__":
    main()

"""Step 5: use the trained TF-IDF model to arbitrate the rule-based classifier's
"ambiguous" pool (poems the rule-based matcher flags but that were held out of
TF-IDF training because we have no trustworthy label for them).

This is the step that produced the headline finding: of ~3,893 rule-flagged
poems, TF-IDF agrees with only a small fraction -- and manually spot-checking
both ends of the score range shows TF-IDF is right to disagree (see README).

Usage: python 05_score_ambiguous.py
Writes: ../results/ambiguous_scored.txt
"""
import json

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from common import (
    parse_gold_poems, full_plain, title_plain, author_of, is_frontier,
    load_collection, title_in_gold, AUTHOR_FILE,
)

GOLD_PATH = "../data/변새시_2차정리본.txt"
CORPUS_BASE = "../../2025_munzip_title_text_ver/"
TIERS_PATH = "../thesaurus/thesaurus_tiers.json"
OUT_PATH = "../results/ambiguous_scored.txt"


def rule_classify_factory():
    specific = set(json.load(open(TIERS_PATH, encoding="utf-8"))["specific"])
    return lambda text: any(t in text for t in specific)


def main():
    rule_classify = rule_classify_factory()
    poems = parse_gold_poems(GOLD_PATH)
    pos_texts = [full_plain(p) for p in poems if is_frontier(p)]

    gold_titles = {a: set() for a in AUTHOR_FILE}
    for p in poems:
        a = author_of(p)
        if a in gold_titles:
            gold_titles[a].add(title_plain(p))

    neg_texts, ambiguous = [], []
    for author, fn in AUTHOR_FILE.items():
        for title, body in load_collection(CORPUS_BASE + fn):
            if title_in_gold(title, gold_titles[author]):
                continue
            full = title + body
            (ambiguous if rule_classify(full) else neg_texts).append((author, title, full))

    X_train_texts = pos_texts + [t for _, _, t in neg_texts]
    y_train = np.array([1] * len(pos_texts) + [0] * len(neg_texts))

    vec = TfidfVectorizer(analyzer="char", ngram_range=(2, 3), min_df=2)
    Xtr = vec.fit_transform(X_train_texts)
    clf = LogisticRegression(class_weight="balanced", max_iter=2000)
    clf.fit(Xtr, y_train)

    amb_texts = [t for _, _, t in ambiguous]
    proba = clf.predict_proba(vec.transform(amb_texts))[:, 1]
    order = np.argsort(proba)[::-1]
    n_pos = int((proba >= 0.5).sum())

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(f"ambiguous pool total: {len(ambiguous)}\n")
        f.write(f"TF-IDF predicts POSITIVE (p>=0.5): {n_pos} ({n_pos/len(ambiguous)*100:.1f}%)\n")
        f.write(f"TF-IDF predicts NEGATIVE (p<0.5): {len(ambiguous)-n_pos} "
                f"({(len(ambiguous)-n_pos)/len(ambiguous)*100:.1f}%)\n\n")

        f.write("=== TOP 30 highest-probability ambiguous poems (likely real, gold-missed frontier poems) ===\n")
        for i in order[:30]:
            a, t, _ = ambiguous[i]
            f.write(f"{proba[i]:.3f}\t{a}\t{t}\n")

        f.write("\n=== BOTTOM 30 lowest-probability ambiguous poems (likely rule-based false positives) ===\n")
        for i in order[::-1][:30]:
            a, t, _ = ambiguous[i]
            f.write(f"{proba[i]:.3f}\t{a}\t{t}\n")

    print(f"ambiguous pool: {len(ambiguous)}, TF-IDF agrees on {n_pos} ({n_pos/len(ambiguous)*100:.1f}%)")
    print(f"saved {OUT_PATH}")


if __name__ == "__main__":
    main()

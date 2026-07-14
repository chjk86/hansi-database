"""Step 4: TF-IDF (character n-gram) + Logistic Regression classifier.

Classical Chinese/hanja poetry has no whitespace word boundaries, so this
uses character bigram/trigram TF-IDF features instead of word tokens.

Training data:
  - positive: the 223 gold-tagged frontier poems
  - negative: poems from the same 12 authors that the rule-based classifier
    (step 3) does NOT flag at all (i.e. zero "specific" thesaurus hits).
    Poems the rule-based classifier DOES flag are held out of training
    entirely as an "ambiguous" pool -- see 05_score_ambiguous.py -- since we
    don't have trustworthy labels for them either way.

Usage: python 04_tfidf_classifier.py
Writes: ../results/tfidf_vs_rule_results.txt
"""
import json
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import precision_recall_fscore_support, average_precision_score

from common import (
    parse_gold_poems, full_plain, title_plain, author_of, is_frontier,
    load_collection, title_in_gold, AUTHOR_FILE,
)

# NOTE: module names starting with a digit can't be `import`-ed directly, so
# the rule-based classifier logic is duplicated here (rule_classify_factory)
# rather than imported from 03_rule_classifier.py. Keep the thesaurus tiers
# file as the single source of truth if you change the wordlists.

GOLD_PATH = "../data/변새시_2차정리본.txt"
CORPUS_BASE = "../../2025_munzip_title_text_ver/"
TIERS_PATH = "../thesaurus/thesaurus_tiers.json"
OUT_PATH = "../results/tfidf_vs_rule_results.txt"


def rule_classify_factory():
    tiers = json.load(open(TIERS_PATH, encoding="utf-8"))
    specific = set(tiers["specific"])

    def classify(text):
        return any(t in text for t in specific)
    return classify


def build_dataset(rule_classify):
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

    return pos_texts, neg_texts, ambiguous


def main():
    rule_classify = rule_classify_factory()
    pos_texts, neg_rows, ambiguous = build_dataset(rule_classify)
    neg_texts = [t for _, _, t in neg_rows]

    print(f"positives: {len(pos_texts)}  clean negatives: {len(neg_texts)}  "
          f"ambiguous (excluded): {len(ambiguous)}")

    X_texts = pos_texts + neg_texts
    y = np.array([1] * len(pos_texts) + [0] * len(neg_texts))

    vec = TfidfVectorizer(analyzer="char", ngram_range=(2, 3), min_df=2)
    X = vec.fit_transform(X_texts)
    print("feature matrix:", X.shape)

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    tfidf_scores, rule_scores, coefs = [], [], []

    for tr, te in skf.split(X, y):
        clf = LogisticRegression(class_weight="balanced", max_iter=2000)
        clf.fit(X[tr], y[tr])
        pred = clf.predict(X[te])
        proba = clf.predict_proba(X[te])[:, 1]
        p, r, f1, _ = precision_recall_fscore_support(y[te], pred, average="binary", zero_division=0)
        ap = average_precision_score(y[te], proba)
        tfidf_scores.append((p, r, f1, ap))
        coefs.append(clf.coef_[0])

        test_texts = [X_texts[i] for i in te]
        rule_pred = np.array([1 if rule_classify(t) else 0 for t in test_texts])
        pr, rr, rf1, _ = precision_recall_fscore_support(y[te], rule_pred, average="binary", zero_division=0)
        rule_scores.append((pr, rr, rf1))

    tfidf_scores = np.array(tfidf_scores)
    rule_scores = np.array(rule_scores)
    mean_coef = np.mean(coefs, axis=0)
    feat_names = vec.get_feature_names_out()
    top_idx = np.argsort(mean_coef)[::-1][:40]

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(f"dataset: {len(pos_texts)} positive, {len(neg_texts)} negative (clean), "
                f"{len(ambiguous)} excluded ambiguous\n")
        f.write(f"feature matrix shape: {X.shape}\n\n")
        f.write("=== TF-IDF + LogisticRegression (5-fold CV) -- the real comparison numbers ===\n")
        f.write(f"precision: {tfidf_scores[:,0].mean():.3f} +- {tfidf_scores[:,0].std():.3f}\n")
        f.write(f"recall:    {tfidf_scores[:,1].mean():.3f} +- {tfidf_scores[:,1].std():.3f}\n")
        f.write(f"f1:        {tfidf_scores[:,2].mean():.3f} +- {tfidf_scores[:,2].std():.3f}\n")
        f.write(f"avg_precision (PR-AUC): {tfidf_scores[:,3].mean():.3f}\n\n")
        f.write("=== Rule-based on the SAME folds (NOTE: circular / optimistic -- see README) ===\n")
        f.write(f"precision: {rule_scores[:,0].mean():.3f} +- {rule_scores[:,0].std():.3f}\n")
        f.write(f"recall:    {rule_scores[:,1].mean():.3f} +- {rule_scores[:,1].std():.3f}\n")
        f.write(f"f1:        {rule_scores[:,2].mean():.3f} +- {rule_scores[:,2].std():.3f}\n\n")
        f.write("=== Top 40 char n-gram features (positive class) ===\n")
        for i in top_idx:
            f.write(f"{feat_names[i]}\t{mean_coef[i]:.3f}\n")

    print(f"saved {OUT_PATH}")


if __name__ == "__main__":
    main()

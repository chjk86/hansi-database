"""Step 10: Naive Bayes and (linear) SVM classifiers, on the same char n-gram
TF-IDF features as 04_tfidf_classifier.py, for a fuller "전통적 머신러닝" comparison
(the research proposal names rule-based / traditional ML / LLM as the three
methods to compare -- 04 covered one traditional-ML variant (LogisticRegression);
this adds the other two commonly cited ones).

Produces, for each of the two models:
  - 5-fold cross-validated precision/recall/F1 (added to results/*.txt)
  - a per-poem judgment file with title + full text + prediction + a reason
    (the model's top-weighted n-gram features that are actually present in
    that poem), for the SAME two poem sets already covered by the LLM
    (results/llm_gold_recall_sample.txt and llm_ambiguous_sample.txt) so all
    three methods can be compared side by side on identical poems.

Usage: python 10_naive_bayes_svm_classifier.py
Writes:
    ../results/nb_svm_cv_results.txt
    ../results/nb_gold_recall_sample.txt
    ../results/nb_ambiguous_sample.txt
    ../results/svm_gold_recall_sample.txt
    ../results/svm_ambiguous_sample.txt
"""
import json
import random

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import precision_recall_fscore_support

from common import (
    parse_gold_poems, full_plain, title_plain, author_of, is_frontier,
    load_collection, title_in_gold, AUTHOR_FILE,
)

GOLD_PATH = "../data/변새시_2차정리본.txt"
CORPUS_BASE = "../../2025_munzip_title_text_ver/"
TIERS_PATH = "../thesaurus/thesaurus_tiers.json"


def rule_classify_factory():
    specific = set(json.load(open(TIERS_PATH, encoding="utf-8"))["specific"])
    return lambda text: any(t in text for t in specific)


def build_dataset(rule_classify):
    """Same recipe as 04_tfidf_classifier.py: gold positives vs. same-author
    poems the rule-based matcher never flags, holding out the rule-flagged
    'ambiguous' pool since we have no trustworthy label for it either way."""
    poems = parse_gold_poems(GOLD_PATH)
    pos = [(author_of(p), title_plain(p), full_plain(p)) for p in poems if is_frontier(p)]

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

    return pos, neg_texts, ambiguous


def top_reasons(text, feature_names, weights, k=6):
    """Which of the model's top-weighted (frontier-indicative) n-grams are
    actually present in this poem -- used as a stand-in for a natural
    language 'reason', the same idea as the top-feature list already
    reported for TF-IDF+LogisticRegression."""
    order = np.argsort(weights)[::-1]
    hits = []
    for i in order:
        f = feature_names[i]
        if f.strip() and f in text:
            hits.append(f.strip())
            if len(hits) >= k:
                break
    return hits


def write_sample_file(path, rows, vec, clf, feature_names, weights, proba_fn):
    with open(path, "w", encoding="utf-8") as f:
        for author, title, text in rows:
            X = vec.transform([text])
            pred = clf.predict(X)[0]
            proba = proba_fn(X)[0]
            reasons = top_reasons(text, feature_names, weights)
            f.write(f"### {title}  ({author})\n")
            f.write(f"판정: {'변새시' if pred == 1 else '변새시 아님'}  (확률 {proba:.3f})\n")
            f.write(f"근거 자질(모델이 학습한 상위 판별 n-gram 중 이 시에 실제로 등장한 것): "
                    f"{', '.join(reasons) if reasons else '(해당 없음)'}\n")
            f.write(f"본문: {text}\n\n")


def main():
    rule_classify = rule_classify_factory()
    pos, neg_rows, ambiguous = build_dataset(rule_classify)
    pos_texts = [t for _, _, t in pos]
    neg_texts = [t for _, _, t in neg_rows]

    print(f"positives: {len(pos_texts)}  clean negatives: {len(neg_texts)}  "
          f"ambiguous (excluded from training): {len(ambiguous)}")

    X_texts = pos_texts + neg_texts
    y = np.array([1] * len(pos_texts) + [0] * len(neg_texts))

    vec = TfidfVectorizer(analyzer="char", ngram_range=(2, 3), min_df=2)
    X = vec.fit_transform(X_texts)
    feature_names = vec.get_feature_names_out()

    # ---- 5-fold cross-validated metrics for both models ----
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    nb_scores, svm_scores = [], []
    for tr, te in skf.split(X, y):
        nb = MultinomialNB()
        nb.fit(X[tr], y[tr])
        p, r, f1, _ = precision_recall_fscore_support(y[te], nb.predict(X[te]), average="binary", zero_division=0)
        nb_scores.append((p, r, f1))

        svm = CalibratedClassifierCV(LinearSVC(class_weight="balanced", max_iter=5000), cv=3)
        svm.fit(X[tr], y[tr])
        p, r, f1, _ = precision_recall_fscore_support(y[te], svm.predict(X[te]), average="binary", zero_division=0)
        svm_scores.append((p, r, f1))

    nb_scores = np.array(nb_scores)
    svm_scores = np.array(svm_scores)

    with open("../results/nb_svm_cv_results.txt", "w", encoding="utf-8") as f:
        f.write(f"dataset: {len(pos_texts)} positive, {len(neg_texts)} negative (clean), "
                f"{len(ambiguous)} excluded ambiguous\n\n")
        f.write("=== Naive Bayes (MultinomialNB), 5-fold CV ===\n")
        f.write(f"precision: {nb_scores[:,0].mean():.3f} +- {nb_scores[:,0].std():.3f}\n")
        f.write(f"recall:    {nb_scores[:,1].mean():.3f} +- {nb_scores[:,1].std():.3f}\n")
        f.write(f"f1:        {nb_scores[:,2].mean():.3f} +- {nb_scores[:,2].std():.3f}\n\n")
        f.write("=== Linear SVM (LinearSVC, Platt-calibrated), 5-fold CV ===\n")
        f.write(f"precision: {svm_scores[:,0].mean():.3f} +- {svm_scores[:,0].std():.3f}\n")
        f.write(f"recall:    {svm_scores[:,1].mean():.3f} +- {svm_scores[:,1].std():.3f}\n")
        f.write(f"f1:        {svm_scores[:,2].mean():.3f} +- {svm_scores[:,2].std():.3f}\n")
    print("saved ../results/nb_svm_cv_results.txt")

    # ---- final models trained on everything, for the per-poem sample files ----
    nb_final = MultinomialNB().fit(X, y)
    svm_final = CalibratedClassifierCV(LinearSVC(class_weight="balanced", max_iter=5000), cv=3).fit(X, y)

    nb_weights = nb_final.feature_log_prob_[1] - nb_final.feature_log_prob_[0]
    # LinearSVC coefficients live inside each calibrated sub-estimator; average them
    svm_weights = np.mean(
        [est.estimator.coef_[0] for est in svm_final.calibrated_classifiers_], axis=0
    )

    # same two poem sets the LLM was run on, for direct side-by-side comparison
    gold_rows = pos  # all 255 known-frontier gold poems (author, title, text)

    random.seed(42)
    ambiguous_sample = random.sample(ambiguous, min(40, len(ambiguous)))

    write_sample_file("../results/nb_gold_recall_sample.txt", gold_rows, vec, nb_final,
                       feature_names, nb_weights, lambda Xs: nb_final.predict_proba(Xs)[:, 1])
    write_sample_file("../results/nb_ambiguous_sample.txt", ambiguous_sample, vec, nb_final,
                       feature_names, nb_weights, lambda Xs: nb_final.predict_proba(Xs)[:, 1])
    write_sample_file("../results/svm_gold_recall_sample.txt", gold_rows, vec, svm_final,
                       feature_names, svm_weights, lambda Xs: svm_final.predict_proba(Xs)[:, 1])
    write_sample_file("../results/svm_ambiguous_sample.txt", ambiguous_sample, vec, svm_final,
                       feature_names, svm_weights, lambda Xs: svm_final.predict_proba(Xs)[:, 1])

    print("saved nb_gold_recall_sample.txt, nb_ambiguous_sample.txt, "
          "svm_gold_recall_sample.txt, svm_ambiguous_sample.txt")


if __name__ == "__main__":
    main()

"""Step 3: rule-based (thesaurus-matching) frontier-poem classifier.

Decision rule: a poem is classified frontier iff it contains at least one
token from the "specific" tier. Tokens in the "generic" tier never trigger a
positive verdict by themselves -- they are only reported as supporting
context alongside a real "specific" hit (per-author testing showed that
letting generic words vote on their own, even in twos, re-introduces the
false-positive flood that motivated this design).

Can be run standalone to sanity-check recall against the gold data and to
pilot-test against each of the 12 gold-covered author collections.

Usage: python 03_rule_classifier.py
"""
import json
import re

from common import (
    parse_gold_poems, full_plain, title_plain, author_of, is_frontier,
    load_collection, AUTHOR_FILE,
)

TIERS_PATH = "../thesaurus/thesaurus_tiers.json"
GOLD_PATH = "../data/변새시_1차정리본.txt"
CORPUS_BASE = "../../2025_munzip_title_text_ver/"


def load_tiers():
    tiers = json.load(open(TIERS_PATH, encoding="utf-8"))
    return set(tiers["specific"]), set(tiers["generic_support_only"])


def make_classifier(specific, generic):
    def classify(text):
        specific_hits = [t for t in specific if t in text]
        if not specific_hits:
            return False, [], []
        generic_hits = [t for t in generic if t in text]
        return True, specific_hits, generic_hits
    return classify


def check_gold_recall(classify):
    poems = parse_gold_poems(GOLD_PATH)
    frontier_poems = [p for p in poems if is_frontier(p)]
    tp = sum(1 for p in frontier_poems if classify(full_plain(p))[0])
    print(f"gold recall: {tp}/{len(frontier_poems)} ({tp/len(frontier_poems)*100:.1f}%)")
    return tp, len(frontier_poems)


def pilot_all_authors(classify):
    poems = parse_gold_poems(GOLD_PATH)
    gold_titles = {a: set() for a in AUTHOR_FILE}
    for p in poems:
        a = author_of(p)
        if a in gold_titles:
            gold_titles[a].add(title_plain(p))

    print(f"{'author':8}{'total':>8}{'gold':>6}{'flagged':>9}{'other':>8}{'rate%':>8}")
    for author, fn in AUTHOR_FILE.items():
        rows = load_collection(CORPUS_BASE + fn)
        flagged = 0
        skipped = 0
        for title, body in rows:
            if title in gold_titles[author]:
                skipped += 1
                continue
            pred, _, _ = classify(title + body)
            if pred:
                flagged += 1
        other = len(rows) - skipped
        rate = flagged / other * 100 if other else 0
        print(f"{author:8}{len(rows):>8}{skipped:>6}{flagged:>9}{other:>8}{rate:>7.2f}")


if __name__ == "__main__":
    specific, generic = load_tiers()
    print(f"specific tier: {len(specific)}  generic (supporting) tier: {len(generic)}")
    classify = make_classifier(specific, generic)
    check_gold_recall(classify)
    print()
    pilot_all_authors(classify)

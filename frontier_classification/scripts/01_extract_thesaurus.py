"""Step 1: mine candidate frontier-vocabulary from the gold-annotated poems.

Pulls three sources of candidate terms out of every poem tagged category="frontier":
  - <term>...</term> spans (line-level emphasis markup)
  - the `evidence="title:... term:..."` attribute on the frontier <Theme> tag itself
  - <Allusion target="..."/> targets (classical allusions)

Usage: python 01_extract_thesaurus.py
Reads:  ../data/변새시_2차정리본.txt
Writes: ../thesaurus/thesaurus_raw.json
"""
import json
import re
from collections import Counter

from common import parse_gold_poems, is_frontier

GOLD_PATH = "../data/변새시_2차정리본.txt"
OUT_PATH = "../thesaurus/thesaurus_raw.json"


def main():
    poems = parse_gold_poems(GOLD_PATH)
    print(f"total poems parsed: {len(poems)}")

    term_counter = Counter()
    evidence_counter = Counter()
    allusion_counter = Counter()
    n_frontier = 0

    for p in poems:
        if not is_frontier(p):
            continue
        n_frontier += 1

        for t in re.findall(r"<term>([^<]*)</term>", p):
            term_counter[t] += 1

        for m in re.finditer(r'<Theme category="[Ff]rontier"[^>]*evidence="([^"]*)"', p):
            cleaned = re.sub(r"(title|term):", "", m.group(1))
            for w in cleaned.split():
                evidence_counter[w] += 1

        for t in re.findall(r'<Allusion[^>]*target="([^"]*)"', p):
            allusion_counter[t] += 1

    print(f"frontier poems: {n_frontier}")
    print(f"unique <term> tokens: {len(term_counter)}")
    print(f"unique evidence tokens: {len(evidence_counter)}")
    print(f"unique allusion targets: {len(allusion_counter)}")

    json.dump(
        {
            "num_poems": len(poems),
            "num_frontier_poems": n_frontier,
            "term_freq": term_counter.most_common(),
            "evidence_freq": evidence_counter.most_common(),
            "allusion_freq": allusion_counter.most_common(),
        },
        open(OUT_PATH, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=2,
    )
    print(f"saved {OUT_PATH}")


if __name__ == "__main__":
    main()

"""2단계: <term> 감사 (리포트 전용, 수정 없음) → reports/95_term_audit.md

- 1글자 term (매뉴얼: term은 명사·형용사 2+글자)
- 2+글자인데 한어대사전 미등재 (매뉴얼: 등재어만 term)
→ 3단계 term/d 재분절 / 검수 인계.
"""
from __future__ import annotations
import os, sys, re, glob, collections

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from hansi import poemdoc

SRC = "01_enriched"
HEADS = "assets/hdc_headwords.txt"
REP = "reports/95_term_audit.md"


def main():
    heads = set(open(HEADS, encoding="utf-8").read().split())
    rep = ["# 95_term_audit — <term> 감사 (수정 없음)", ""]
    g_single = collections.Counter()
    g_notdict = collections.Counter()
    tot = 0
    for path in sorted(glob.glob(os.path.join(SRC, "*.xml"))):
        mj = os.path.splitext(os.path.basename(path))[0]
        text = open(path, encoding="utf-8").read()
        terms = [re.sub(r"<[^>]+>", "", t) for t in re.findall(r"<term>(.*?)</term>", text, re.S)]
        tot += len(terms)
        single = [t for t in terms if len(t) == 1]
        notdict = [t for t in terms if len(t) >= 2 and t not in heads]
        g_single.update(single)
        g_notdict.update(notdict)
        rep.append(f"\n## {mj}  (term {len(terms)})")
        rep.append(f"- 1글자 term: {len(single)}  {' '.join(sorted(set(single)))[:120]}")
        rep.append(f"- 사전 미등재(2+글자): {len(notdict)}")
        if notdict:
            top = collections.Counter(notdict).most_common(20)
            rep.append("  - " + " ".join(f"{w}×{c}" for w, c in top))
    rep.insert(2, f"**전체 term {tot} · 1글자 {sum(g_single.values())} (고유 {len(g_single)}) · "
              f"사전미등재 {sum(g_notdict.values())} (고유 {len(g_notdict)})**")
    rep.append("\n## 전체 빈출 (사전 미등재)")
    rep.append(" ".join(f"{w}×{c}" for w, c in g_notdict.most_common(60)))
    with open(REP, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rep))
    print(f"95_term_audit.md — term {tot}, 1글자 {sum(g_single.values())}, 사전미등재 {sum(g_notdict.values())}")


if __name__ == "__main__":
    main()

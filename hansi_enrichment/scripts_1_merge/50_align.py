"""1단계: 임백호집 통합본 vs 골드 대조 → reports/00_align_임백호집.md"""
from __future__ import annotations
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from hansi import poemdoc
from hansi.io import read_text

GOLD = "임백호집_3차완본_20260730.txt"
CORPUS = "00_corpus/임백호집.xml"
REP = "reports/00_align_임백호집.md"


def main():
    gold = poemdoc.parse_poems(read_text(GOLD))
    corp = poemdoc.parse_poems(open(CORPUS, encoding="utf-8").read())
    gset = {p.id for p in gold}
    cset = {p.id for p in corp}
    rep = ["# 00_align 임백호집", ""]
    rep.append(f"- 골드 {len(gold)}수, 통합본 {len(corp)}수")
    rep.append(f"- 골드에만: {sorted(gset - cset) or '없음'}")
    rep.append(f"- 통합본에만: {sorted(cset - gset) or '없음'}")
    # 내용 동일 여부
    graw = {p.id: p.raw for p in gold}
    diff = [pid for p in corp if (pid := p.id) in graw and p.raw != graw[pid]]
    rep.append(f"- id 공통이나 내용 상이: {len(diff)}수  {diff[:10]}")
    ok = not (gset - cset) and not (cset - gset)
    rep.append(f"\n**정합성: {'OK' if ok else '불일치 — 위 목록 확인'}**")
    with open(REP, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rep))
    print("\n".join(rep))


if __name__ == "__main__":
    main()

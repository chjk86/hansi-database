"""Themes 후보 스코어링 → Claude 판정 대기 배치(JSON).

  python 10_thesaurus.py holdout   임백호집 40수 홀드아웃 검증 배치
  python 10_thesaurus.py 고죽유고    고죽유고 전 시 배치
"""
from __future__ import annotations
import os, sys, json, random, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from hansi import poemdoc, themonto, xmlpoem as X
from hansi.io import read_text

GOLD = "임백호집_3차완본_20260730.txt"
OUT = "02_pilot"
BATCH = 20
TOPK = 6


def poem_view(raw: str):
    title = X.strip_tags(X.get_field(raw, "Title") or "")
    lines = [X.strip_tags(inner) for _, inner, _ in X.lines(raw)]
    return title, lines


DECISIVE_RATIO = 3.0
AUTO_RATIO = 6.0

# 제목 함정: 시소러스가 제목 키워드에 속는 패턴 → 자동채움 금지, Claude 판정으로
import re as _re
_TRAP = [
    _re.compile(r"[次和用酬][^。]{0,8}韻"),   # 차운/화운
    _re.compile(r"贈別|別[^。]{0,6}贈"),        # 贈別 = 실은 송별
    _re.compile(r"送(酒|米|炭|茶|柴|物|扇|筆|墨)"),  # 送+사물 = 送別 아님
    _re.compile(r"(曲|行|歌|引|吟|謠)\s*$"),     # 악부제 — 내용판정 필요
    _re.compile(r"題詠|帖字"),                   # 題詠 ≠ 題畵
]


def is_trap(title: str) -> bool:
    return any(rx.search(title) for rx in _TRAP)


def make_batches(poems, th, tag: str, gold_map=None, decisive_only=False):
    items = []
    for p in poems:
        # 이미 유효 <Theme> 있으면 건너뜀 (빈 <Themes>만 대상)
        tm = re.search(r"<Themes>(.*?)</Themes>", p.raw, re.S)
        if tm and re.search(r'<Theme\s+category="[a-z_]+"', tm.group(1)):
            continue
        sc = th.score(p.raw)
        mc = sc.most_common(TOPK)
        r = (mc[0][1] / mc[1][1]) if len(mc) >= 2 and mc[1][1] else (999 if mc else 0)
        decisive = bool(mc) and r >= DECISIVE_RATIO
        title, lines = poem_view(p.raw)
        has_title_hit = bool(mc and th.evidence_for(p.raw, mc[0][0])[0])
        tier = "skip"
        if decisive:
            if r >= AUTO_RATIO and has_title_hit and not is_trap(title):
                tier = "auto"
            else:
                tier = "judge"
        if decisive_only and tier == "skip":
            continue
        cands = []
        for c, s in mc:
            th_hit, tm_hit = th.evidence_for(p.raw, c)
            cands.append({"cat": c, "score": round(s, 1),
                          "title_hit": th_hit, "term_hit": tm_hit})
        it = {"id": p.id, "title": title, "lines": lines,
              "candidates": cands, "tier": tier,
              "thesaurus_top": mc[0][0] if mc else None}
        if gold_map is not None:
            it["_gold"] = gold_map.get(p.id, [])
        items.append(it)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"themes_batch_{tag}.json")
    batches = [items[i:i+BATCH] for i in range(0, len(items), BATCH)]
    json.dump({"tag": tag, "n": len(items), "batches": batches},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{path}: {len(items)}수 / {len(batches)}배치")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "holdout"
    gold_poems = poemdoc.parse_poems(read_text(GOLD))
    gold_map = {p.id: [c for c, _, _ in themonto.parse_gold_themes(p.raw)] for p in gold_poems}

    if mode == "holdout":
        random.seed(7)
        idx = list(range(len(gold_poems)))
        random.shuffle(idx)
        hold = set(idx[:40])
        train = [gold_poems[i].raw for i in idx if i not in hold]
        th = themonto.Thesaurus().fit(train)
        make_batches([gold_poems[i] for i in sorted(hold)], th, "holdout", gold_map)
    elif mode == "all":
        import glob
        th = themonto.Thesaurus().fit([p.raw for p in gold_poems])
        for f in sorted(glob.glob("01_enriched/*.xml")):
            mj = os.path.splitext(os.path.basename(f))[0]
            if mj == "임백호집":       # 골드 완비
                continue
            target = poemdoc.parse_poems(open(f, encoding="utf-8").read())
            make_batches(target, th, mj)
    else:
        th = themonto.Thesaurus().fit([p.raw for p in gold_poems])
        target = poemdoc.parse_poems(open(f"01_enriched/{mode}.xml", encoding="utf-8").read())
        make_batches(target, th, mode, decisive_only=("--decisive" in sys.argv))


if __name__ == "__main__":
    main()

"""1단계: 00_corpus XML 이상 검출 → reports/00_lint.md

1단계는 태그 오류를 고치지 않는다. 여기서는 분류·집계만 하고
2·3단계 검수 백로그로 넘긴다.

치명(1단계 차단 대상):
  - 미복구 Poem (</text>·</Poem> 복구 실패)
  - 중복 Poem id
  - <Metadata> 또는 <text> 블록 자체가 없음
검수 대상(집계만):
  - 인라인 태그(<term>/<d>/<rhyme>) 열림≠닫힘
  - <Line> 열림≠닫힘  (대개 '외부 Allusion 뒤 잉여 </Line>' 패턴)
  - <Couplet> 불균형, order 비연속, 미이스케이프 &
"""
from __future__ import annotations
import os, sys, re, glob, collections

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from hansi import poemdoc

OUT = "00_corpus"
REP = "reports"
INLINE = ["term", "d", "rhyme"]


def analyze(p: poemdoc.Poem):
    raw = p.raw
    fatal, review = [], collections.Counter()
    if not p.well_formed:
        fatal.append("Poem 미복구")
    if not re.search(r"<Metadata\b", raw, re.I) or not re.search(r"</Metadata\s*>", raw, re.I):
        fatal.append("Metadata 블록 없음/미완")
    if not re.search(r"<text\b", raw, re.I):
        fatal.append("text 블록 없음")
    for tag in INLINE:
        o = len(re.findall(rf"<{tag}(?:\s[^>]*)?>", raw))
        c = len(re.findall(rf"</{tag}\s*>", raw))
        if o != c:
            review[f"{tag} 태그 불균형"] += 1
    lo = len(re.findall(r"<Line(?:\s[^>]*)?>", raw, re.I))
    lc = len(re.findall(r"</Line\s*>", raw, re.I))
    if lo != lc:
        # 외부 Allusion 뒤 잉여 </Line> 인지
        if re.search(r"/>\s*</Line\s*>", raw):
            review["Allusion 외부배치 + 잉여 </Line>"] += 1
        else:
            review["Line 불균형(기타)"] += 1
    oc = len(re.findall(r"<Couplet(?:\s[^>]*)?>", raw, re.I))
    cc = len(re.findall(r"</Couplet\s*>", raw, re.I))
    if oc != cc:
        review["Couplet 불균형"] += 1
    if "&" in re.sub(r"&(amp|lt|gt|quot|apos|#x?\d+);", "", raw):
        review["미이스케이프 &"] += 1
    orders = [int(x) for x in re.findall(r'<Line\b[^>]*\border\s*=\s*"(\d+)"', raw)]
    if orders and orders != list(range(1, len(orders) + 1)):
        review["order 비연속"] += 1
    return fatal, review


def main():
    os.makedirs(REP, exist_ok=True)
    rep = ["# 00_lint 리포트", "",
           "1단계는 태그 오류를 수정하지 않음. 아래 '검수 대상'은 2·3단계 백로그.", ""]
    grand_fatal = 0
    grand_review = collections.Counter()
    for path in sorted(glob.glob(os.path.join(OUT, "*.xml"))):
        mj = os.path.splitext(os.path.basename(path))[0]
        poems = poemdoc.parse_poems(open(path, encoding="utf-8").read())
        ids = [p.id for p in poems]
        dups = sorted({x for x in ids if ids.count(x) > 1})
        fatal_lines, rev = [], collections.Counter()
        for p in poems:
            fa, rv = analyze(p)
            if fa:
                fatal_lines.append(f"  - {p.id}: {', '.join(fa)}")
            rev.update(rv)
        nfatal = len(fatal_lines) + len(dups)
        grand_fatal += nfatal
        grand_review.update(rev)
        rep.append(f"\n## {mj}  ({len(poems)}수)")
        rep.append(f"- 치명 {nfatal} · 검수대상 {sum(rev.values())}")
        if dups:
            rep.append(f"- **중복 id**: {' '.join(dups)}")
        if fatal_lines:
            rep.append("- **치명**:")
            rep.extend(fatal_lines[:30])
            if len(fatal_lines) > 30:
                rep.append(f"  … 외 {len(fatal_lines)-30}")
        if rev:
            rep.append("- 검수 대상:")
            for k, v in rev.most_common():
                rep.append(f"  - {k}: {v}수")
        if not (nfatal or rev):
            rep.append("- 이상 없음")

    rep.insert(4, f"**전체: 치명 {grand_fatal} · 검수대상 " +
              ", ".join(f"{k} {v}" for k, v in grand_review.most_common()) + "**")
    with open(os.path.join(REP, "00_lint.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rep))
    print(f"00_lint.md — 치명 {grand_fatal}")
    print("검수대상:", dict(grand_review.most_common()))


if __name__ == "__main__":
    main()

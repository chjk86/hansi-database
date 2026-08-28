"""2단계: 00_corpus/*.xml → 01_enriched/*.xml

스테이지 (시별):
  charcount  Charactercount 재계산·교정
  form       Basetype/Detailtype 판정
  rhyme      <rhyme> 재태깅 (수구압운·통운·환운)
  couplet    율시/배율 <Couplet>
  reschema   Themes 스키마 정리
리포트: reports/2x_*.md
term 감사는 별도: 95_term_audit.py
"""
from __future__ import annotations
import os, sys, glob, re, collections

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from hansi import poemdoc, form, rhymetag, couplet, themes, xmlpoem as X

SRC = "00_corpus"
DST = "01_enriched"
REP = "reports"


def enrich_poem(raw: str):
    flags = collections.Counter()
    title = X.strip_tags(X.get_field(raw, "Title") or "")

    # charcount + form
    f = form.classify(raw, title)
    old_cc = X.get_field(raw, "Charactercount") or ""
    old_bt = X.get_field(raw, "Basetype") or ""
    old_dt = X.get_field(raw, "Detailtype") or ""
    if f["charcount"]:
        if not old_cc:
            raw = X.set_field(raw, "Charactercount", f["charcount"])
            flags[f"charcount채움:∅→{f['charcount']}"] += 1
        elif f["charcount"] != old_cc:
            flags[f"charcount_불일치:{old_cc}(유지) vs {f['charcount']}(판정)"] += 1
    # 기존값이 있으면 존중(작업자·검수 판단). 비어있을 때만 채움. 불일치는 flag만.
    if f["basetype"]:
        if not old_bt:
            raw = X.set_field(raw, "Basetype", f["basetype"])
            flags[f"basetype채움:∅→{f['basetype']}"] += 1
        elif f["basetype"] != old_bt:
            flags[f"basetype_불일치:{old_bt}(유지) vs {f['basetype']}(판정)"] += 1
    if f["detailtype"]:
        if not old_dt:
            raw = X.set_field(raw, "Detailtype", f["detailtype"])
            flags[f"detailtype채움:∅→{f['detailtype']}"] += 1
        elif f["detailtype"] != old_dt:
            flags[f"detailtype_불일치:{old_dt}(유지) vs {f['detailtype']}(판정)"] += 1
    for fl in f["flags"]:
        if fl.startswith("form_uncertain"):
            flags[fl] += 1

    # rhyme
    raw, rfl = rhymetag.retag(raw, f["basetype"], f["detailtype"])
    for fl in rfl:
        flags[fl.split(":")[0].split("@")[0]] += 1

    # couplet
    raw, cfl = couplet.wrap(raw, f["basetype"], f["detailtype"])
    for fl in cfl:
        flags[fl.split(":")[0]] += 1

    # themes
    raw, tfl = themes.clean(raw)
    for fl in tfl:
        flags[fl] += 1

    return raw, flags


def main():
    os.makedirs(DST, exist_ok=True)
    os.makedirs(REP, exist_ok=True)
    grand = collections.Counter()
    rep = ["# 2단계 enrich 리포트", ""]
    for path in sorted(glob.glob(os.path.join(SRC, "*.xml"))):
        mj = os.path.splitext(os.path.basename(path))[0]
        poems = poemdoc.parse_poems(open(path, encoding="utf-8").read())
        agg = collections.Counter()
        out_blocks = []
        for p in poems:
            new_raw, fl = enrich_poem(p.raw)
            out_blocks.append(new_raw)
            agg.update(fl)
        with open(os.path.join(DST, mj + ".xml"), "w", encoding="utf-8", newline="\n") as f:
            f.write(poemdoc.wrap_corpus(out_blocks))
        grand.update(agg)
        rep.append(f"\n## {mj} ({len(poems)}수)")
        for k, v in agg.most_common():
            rep.append(f"- {k}: {v}")
    rep.insert(2, "**전체**: " + " · ".join(f"{k} {v}" for k, v in grand.most_common(25)))
    with open(os.path.join(REP, "2_enrich.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rep))
    print("01_enriched/ 작성. 상위 flags:")
    for k, v in grand.most_common(20):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

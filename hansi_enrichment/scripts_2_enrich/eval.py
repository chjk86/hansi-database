"""2단계 검증: 임백호집 입력본 → enrich → 3차완본 골드 대조."""
from __future__ import annotations
import os, sys, re, glob, collections, unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from hansi import poemdoc, xmlpoem as X, rhyme as R
from hansi.io import read_text
from enrich import enrich_poem

GOLD = "임백호집_3차완본_20260730.txt"
RAWDIR = "00_raw/4-1. 생성 데이터 [전원]/임백호집_임제"
INPUT_HINT = "4월 4주차"
REP = "reports/2_eval_임백호집.md"


def find_input():
    for f in os.listdir(RAWDIR):
        if INPUT_HINT in unicodedata.normalize("NFC", f) and f.endswith(".txt"):
            return os.path.join(RAWDIR, f)
    raise SystemExit("입력본 못 찾음")


def main():
    gold = {p.id: p for p in poemdoc.parse_poems(read_text(GOLD))}
    src = poemdoc.parse_poems(read_text(find_input()))

    bt = dt = cc = n = 0
    fill_bt_ok = fill_bt_n = 0    # 소스 비어있던 것만
    rh_tp = rh_fp = rh_fn = 0
    theory_bad = 0
    coup_ok = coup_tot = 0
    bt_conf = collections.Counter()
    dt_conf = collections.Counter()
    for p in src:
        g = gold.get(p.id)
        if not g:
            continue
        n += 1
        src_bt_empty = not (X.get_field(p.raw, "Basetype") or "")
        new_raw, _ = enrich_poem(p.raw)
        for tag, conf in (("Basetype", bt_conf), ("Detailtype", dt_conf)):
            gv = X.get_field(g.raw, tag) or ""
            nv = X.get_field(new_raw, tag) or ""
            if gv == nv:
                if tag == "Basetype":
                    bt += 1
                else:
                    dt += 1
            else:
                conf[(gv, nv)] += 1
        if src_bt_empty:
            fill_bt_n += 1
            fill_bt_ok += (X.get_field(g.raw, "Basetype") or "") == (X.get_field(new_raw, "Basetype") or "")
        if (X.get_field(g.raw, "Charactercount") or "") == (X.get_field(new_raw, "Charactercount") or ""):
            cc += 1
        # rhyme 위치
        gp = {o for o, _ in X.rhyme_chars(g.raw)}
        npz = {o for o, _ in X.rhyme_chars(new_raw)}
        rh_tp += len(gp & npz); rh_fn += len(gp - npz); rh_fp += len(npz - gp)
        rchars = [c for _, c in X.rhyme_chars(new_raw)]
        if len(rchars) >= 2 and not all(R.same_rhyme(rchars[0], c) for c in rchars[1:]):
            theory_bad += 1
        # couplet: 골드에 <Couplet> 있으면 대조
        g_cp = len(re.findall(r"<Couplet\b", g.raw))
        n_cp = len(re.findall(r"<Couplet\b", new_raw))
        if g_cp:
            coup_tot += 1
            coup_ok += (g_cp == n_cp)

    lines = [
        "# 2_eval 임백호집", "",
        f"- 대조 시: {n}",
        f"- **Basetype** 전체 {bt}/{n} ({100*bt/n:.1f}%) · 빈칸채움만 {fill_bt_ok}/{fill_bt_n} ({100*fill_bt_ok/max(fill_bt_n,1):.1f}%)  오분류 {dict(bt_conf)}",
        f"- **Detailtype** {dt}/{n} ({100*dt/n:.1f}%)  오분류 {dict(dt_conf)}",
        f"- **Charactercount** {cc}/{n} ({100*cc/n:.1f}%)",
        f"- **rhyme 위치** recall {rh_tp/(rh_tp+rh_fn):.3f} (FN {rh_fn}), "
        f"골드미태깅 추가 {rh_fp}",
        f"- rhyme 이론부정합 {theory_bad}수 (대개 골드 측성압운 오분류)",
        f"- Couplet: 골드 有 {coup_tot}수 중 일치 {coup_ok}",
    ]
    print("\n".join(lines))
    with open(REP, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()

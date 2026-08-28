"""Themes 제안 + 확신도 — 거의 전 시에 주분류 제안, 작업자가 %로 판단.

  python 30_suggest.py            # 01_enriched/*.xml → 02_suggested/*.xml + 확신도 TSV
  python 30_suggest.py <문집>

- conf ≥ FILL_MIN → <Themes> 에 주분류 1개 채움
- conf < FILL_MIN → 빈 <Themes> 유지 (신호 약함)
- 기존 유효 <Theme> 있으면 불변
- 모든 시 → reports/3_conf_<문집>.tsv (id·제목·제안·확신도·구간정밀도·근거·비고)
"""
from __future__ import annotations
import os, sys, re, glob, html

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from hansi import poemdoc, themonto, themconf, xmlpoem as X
from hansi.io import read_text

GOLD = "임백호집_3차완본_20260730.txt"
FILL_MIN = 40

# 임백호집 5-fold 캘리브레이션 (구간 → 실제 정밀도)
BUCKET_PREC = {10: .17, 20: .16, 30: .14, 40: .27, 50: .38, 60: .52, 70: .82, 80: .94, 90: .94}

LABELS = {
    "mountain": "산악", "water": "강해", "astro": "천문", "season": "계절",
    "animal": "동물", "plant": "식물", "travel": "유람", "donate": "기증",
    "farewell": "송별", "meet": "회방", "sympathy": "애상", "reminiscence": "회고",
    "frontier": "변새", "desire": "염정", "dream": "기몽", "prosper": "현달",
    "tranquility": "한적", "banquet": "연회", "person": "인물", "taoism": "도교",
    "buddhism": "불교", "structure": "건물", "object": "기용", "literature": "문방",
    "picture": "도화", "others": "기타",
}


def theme_tag(cat, th_hit, tm_hit):
    b, e = [], []
    if th_hit:
        b.append("title"); e.append("title:" + " ".join(th_hit))
    if tm_hit:
        b.append("term"); e.append("term:" + " ".join(tm_hit))
    if not b:
        b, e = ["term"], ["term:"]
    return (f'<Theme category="{cat}" basis="{", ".join(b)}" '
            f'evidence="{html.escape(", ".join(e), quote=True)}">{LABELS[cat]}</Theme>')


def set_themes(raw, tag):
    inner = f"\n        {tag}\n      " if tag else ""
    return re.sub(r"(<Themes>).*?(</Themes>)", lambda m: m.group(1) + inner + m.group(2),
                  raw, count=1, flags=re.S)


def run_one(mj, th):
    poems = poemdoc.parse_poems(open(f"01_enriched/{mj}.xml", encoding="utf-8").read())
    out, tsv = [], ["id\t제목\t제안분류\t확신도\t구간정밀도\t근거\t비고"]
    n_fill = n_weak = n_has = 0
    for p in poems:
        m = re.search(r"<Themes>(.*?)</Themes>", p.raw, re.S)
        if m and re.search(r'<Theme\s+category=', m.group(1)):
            n_has += 1
            out.append(p.raw)
            tsv.append(f"{p.id}\t{X.strip_tags(X.get_field(p.raw,'Title') or '')}\t(작업자 기입)\t-\t-\t-\t-")
            continue
        title = X.strip_tags(X.get_field(p.raw, "Title") or "")
        cat, conf, basis, th_h, tm_h, note = themconf.suggest(th, p.raw, title)
        prec = BUCKET_PREC.get((conf // 10) * 10, 0) if cat else 0
        if cat and conf >= FILL_MIN:
            out.append(set_themes(p.raw, theme_tag(cat, th_h, tm_h)))
            n_fill += 1
        else:
            out.append(p.raw)
            n_weak += 1
        tsv.append(f"{p.id}\t{title}\t{LABELS.get(cat,'-')}({cat or '-'})\t{conf}\t{prec:.0%}\t{basis}\t{note}")
    os.makedirs("02_suggested", exist_ok=True)
    with open(f"02_suggested/{mj}.xml", "w", encoding="utf-8", newline="\n") as f:
        f.write(poemdoc.wrap_corpus(out))
    os.makedirs("reports", exist_ok=True)
    with open(f"reports/3_conf_{mj}.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(tsv))
    return len(poems), n_fill, n_weak, n_has


def main():
    gold = poemdoc.parse_poems(read_text(GOLD))
    th = themonto.Thesaurus().fit([p.raw for p in gold])
    targets = [sys.argv[1]] if len(sys.argv) > 1 else \
        [os.path.splitext(os.path.basename(f))[0] for f in sorted(glob.glob("01_enriched/*.xml"))
         if "임백호집" not in f]
    T = [0, 0, 0, 0]
    rows = []
    for mj in targets:
        n, fill, weak, has = run_one(mj, th)
        rows.append(f"{mj:10} {n:>5}수  제안채움 {fill:>4}  신호약함 {weak:>4}  작업자기입 {has:>4}")
        for i, v in enumerate((n, fill, weak, has)):
            T[i] += v
    print("\n".join(rows))
    print(f"{'합계':10} {T[0]:>5}수  제안채움 {T[1]:>4}  신호약함 {T[2]:>4}  작업자기입 {T[3]:>4}")
    print(f"→ 분류율 {(T[1]+T[3])/T[0]:.0%}  (확신도 TSV: reports/3_conf_<문집>.tsv)")


if __name__ == "__main__":
    main()

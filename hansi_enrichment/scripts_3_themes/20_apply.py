"""Themes 자동채움 → 02_pilot/<문집>.xml  (Option B: 고신뢰만)

  python 20_apply.py <문집> [--judged]

tier:
  auto   제목 신호 + 점수비 ≥6 + 무함정 → 주분류 1개 자동채움 (~92% 정밀도)
  judge  결정적이나 애매 → themes_judged_<문집>.json 있으면 반영, 없으면 검수
  skip   빈 <Themes> 유지 (검수)

기존 유효 <Theme> 이 있는 시는 손대지 않음.
"""
from __future__ import annotations
import os, sys, json, re, html

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from hansi import poemdoc

LABELS = {
    "mountain": "산악", "water": "강해", "astro": "천문", "season": "계절",
    "animal": "동물", "plant": "식물", "travel": "유람", "donate": "기증",
    "farewell": "송별", "meet": "회방", "sympathy": "애상", "reminiscence": "회고",
    "frontier": "변새", "desire": "염정", "dream": "기몽", "prosper": "현달",
    "tranquility": "한적", "banquet": "연회", "person": "인물", "taoism": "도교",
    "buddhism": "불교", "structure": "건물", "object": "기용", "literature": "문방",
    "picture": "도화", "others": "기타",
}


def theme_tag(cat, title_hit, term_hit):
    b, e = [], []
    if title_hit:
        b.append("title"); e.append("title:" + " ".join(title_hit))
    if term_hit:
        b.append("term"); e.append("term:" + " ".join(term_hit))
    if not b:
        b, e = ["term"], ["term:"]
    return (f'<Theme category="{cat}" basis="{", ".join(b)}" '
            f'evidence="{html.escape(", ".join(e), quote=True)}">{LABELS[cat]}</Theme>')


def set_themes(raw, tags):
    inner = ("\n        " + "\n        ".join(tags) + "\n      ") if tags else ""
    return re.sub(r"(<Themes>).*?(</Themes>)", lambda m: m.group(1) + inner + m.group(2),
                  raw, count=1, flags=re.S)


def main():
    mj = sys.argv[1]
    batch = json.load(open(f"02_pilot/themes_batch_{mj}.json", encoding="utf-8"))
    cand = {it["id"]: it for b in batch["batches"] for it in b}
    judged = {}
    jp = f"02_pilot/themes_judged_{mj}.json"
    if "--judged" in sys.argv and os.path.exists(jp):
        judged = {k: v for k, v in json.load(open(jp, encoding="utf-8")).items() if not k.startswith("_")}

    poems = poemdoc.parse_poems(open(f"01_enriched/{mj}.xml", encoding="utf-8").read())
    n_auto = n_judge = n_skip = n_has = 0
    rep = [f"# 3_themes_{mj}", ""]
    out = []
    for p in poems:
        it = cand.get(p.id)
        if it is None:               # 이미 Theme 있거나 배치 밖
            n_has += 1
            out.append(p.raw)
            continue
        hitmap = {c["cat"]: (c["title_hit"], c["term_hit"]) for c in it["candidates"]}
        tier = it["tier"]
        top = it["thesaurus_top"]
        if tier == "auto":
            th_h, tm_h = hitmap.get(top, ([], []))
            out.append(set_themes(p.raw, [theme_tag(top, th_h, tm_h)]))
            n_auto += 1
            rep.append(f"- [auto] {p.id} {it['title']} → {top}")
        elif tier == "judge" and p.id in judged and judged[p.id] and judged[p.id][0] == top:
            th_h, tm_h = hitmap.get(top, ([], []))
            out.append(set_themes(p.raw, [theme_tag(top, th_h, tm_h)]))
            n_judge += 1
            extra = f"  (+검수: {judged[p.id][1:]})" if len(judged[p.id]) > 1 else ""
            rep.append(f"- [judge] {p.id} {it['title']} → {top}{extra}")
        else:
            n_skip += 1
            sug = f"  판정후보:{judged.get(p.id)}" if p.id in judged else ""
            rep.append(f"- [검수] {p.id} {it['title']}  (시소러스:{top}){sug}")
            out.append(p.raw)

    os.makedirs("02_pilot", exist_ok=True)
    with open(f"02_pilot/{mj}.xml", "w", encoding="utf-8", newline="\n") as f:
        f.write(poemdoc.wrap_corpus(out))
    line = (f"**{mj} {len(poems)}수: auto {n_auto} · judge {n_judge} · 검수 {n_skip} · "
            f"기보유/제외 {n_has}**")
    rep.insert(2, line)
    with open(f"reports/3_themes_{mj}.md", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rep))
    print(line)


if __name__ == "__main__":
    main()

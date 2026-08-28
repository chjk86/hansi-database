"""term/d 재태깅 — 과다 자동태깅된 대상데이터 4문집 전용.

  python 40_termd.py            # d_lexicon 생성 + eval + 4문집 적용
  python 40_termd.py --eval     # 임백호집 골드 대비 검증만

대상: 기재집·동명집·동악집·현주집 (대상데이터 = 사전 bigram 무차별 태깅).
수작업 태깅 문집(임백호집·Drive 15문집)은 건드리지 않는다.
"""
from __future__ import annotations
import os, sys, re, glob, collections

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from hansi import poemdoc, termdtag, xmlpoem as X
from hansi.io import read_text

GOLD = "임백호집_3차완본_20260730.txt"
# 대상데이터(문집 전체 자동태깅) — 무조건 재태깅
ALL_AUTO = ["기재집", "동명집", "동악집", "현주집"]
# 수작업 문집은 시(詩) 단위로 판정: <d> 있거나 Themes 채워졌으면 수작업 → 건너뜀
MANUAL_COLLECTIONS = ["성소부부고", "옥봉집", "고죽유고", "손곡시집", "소재집", "현곡집",
                      "호음잡고", "눌재집", "어우집", "오산집", "용재집", "읍취헌유고",
                      "지봉집", "지천집"]
_NEG_TAG = re.compile(r"<(?:term|d)>(?:不|無|未|莫|勿|非|休|何|豈|寧)[^<]")


def poem_is_auto(raw: str) -> bool:
    """이 시가 '자동태깅(수작업 term/d 안 됨)' 상태인가.

    수작업 근거 = <d> 태그 존재 (작업자가 사전 미등재 시어를 <d>로 구분).
    <d> 없으면 → 사전 bigram 무차별 태깅으로 간주.
    (Themes 신호는 쓰지 않음 — 3단계에서 자동 채워지므로.)
    """
    return not re.search(r"<d>", raw)


def build_d_lexicon():
    """d-어휘 = 수작업으로 확인된 시(<d> 있는 시)의 term/d 중 사전 미등재 2글자."""
    heads = set(open("assets/hdc_headwords.txt", encoding="utf-8").read().split())
    c = collections.Counter()
    for f in glob.glob("01_enriched/*.xml"):
        for p in poemdoc.parse_poems(open(f, encoding="utf-8").read()):
            if not re.search(r"<d>", p.raw):
                continue                     # 수작업 확인된 시만
            for m in re.finditer(r"<(term|d)>(.*?)</\1>", p.raw, re.S):
                w = X.hanja_only(X.strip_tags(m.group(2)))
                if len(w) == 2 and w not in heads:
                    c[w] += 1
    lex = sorted(w for w, n in c.items() if n >= 2)
    with open("assets/d_lexicon.txt", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lex))
    return lex


def gold_span_chars(inner):
    out = set(); pos = 0
    for m in re.finditer(r"<(term|d)>(.*?)</\1>|([^<]+)", inner, re.S):
        if m.group(1):
            w = X.hanja_only(X.strip_tags(m.group(2)))
            for k in range(len(w)):
                out.add(pos + k)
            pos += len(w)
        elif m.group(3):
            pos += len(X.hanja_only(m.group(3)))
    return out


def evaluate():
    termdtag._load.__wrapped__ if False else None
    termdtag._HEADS = termdtag._DLEX = None
    g = poemdoc.parse_poems(read_text(GOLD))
    tp = fp = fn = 0
    for p in g:
        for o, inner, _ in X.lines(p.raw):
            gs = gold_span_chars(inner)
            new, _n = termdtag.retag_line(re.sub(r"<(term|d)>|</(term|d)>", "", inner))
            ps = gold_span_chars(new)
            tp += len(gs & ps); fp += len(ps - gs); fn += len(gs - ps)
    P = tp / (tp + fp); R = tp / (tp + fn)
    print(f"임백호집 골드 대비: P {P:.2f}  R {R:.2f}  F1 {2*P*R/(P+R):.2f}")


def _retag_poem(raw: str) -> str:
    return re.sub(r"(<Line\b[^>]*>)(.*?)(</Line\s*>)",
                  lambda m: m.group(1) + termdtag.retag_line(
                      re.sub(r"</?(?:term|d)>", "", m.group(2)))[0] + m.group(3),
                  raw, flags=re.S | re.I)


def apply_targets():
    os.makedirs("02_suggested", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    grand = collections.Counter()
    for mj in ALL_AUTO + MANUAL_COLLECTIONS:
        src = f"02_suggested/{mj}.xml"
        if not os.path.exists(src):
            src = f"01_enriched/{mj}.xml"
        poems = poemdoc.parse_poems(open(src, encoding="utf-8").read())
        out, rep = [], [f"# 3_termd_{mj}", ""]
        n_retag = n_skip = 0
        for p in poems:
            if mj in ALL_AUTO or poem_is_auto(p.raw):
                out.append(_retag_poem(p.raw))
                n_retag += 1
            else:
                out.append(p.raw)
                n_skip += 1
                continue
            rep.append(f"- {p.id} 재태깅")
        with open(f"02_suggested/{mj}.xml", "w", encoding="utf-8", newline="\n") as f:
            f.write(poemdoc.wrap_corpus(out))
        rep.insert(2, f"**{mj}: {len(poems)}수 — 재태깅 {n_retag} · 수작업유지 {n_skip}**")
        with open(f"reports/3_termd_{mj}.md", "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(rep))
        grand["retag"] += n_retag; grand["skip"] += n_skip
        print(f"{mj:9} 재태깅 {n_retag:>5} · 수작업유지 {n_skip:>5}")
    print(f"\n합계: 재태깅 {grand['retag']} · 수작업유지 {grand['skip']}")


def main():
    lex = build_d_lexicon()
    print(f"d_lexicon: {len(lex)} 어휘")
    evaluate()
    if "--eval" not in sys.argv:
        apply_targets()


if __name__ == "__main__":
    main()

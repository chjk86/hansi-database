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

TARGETS = ["기재집", "동명집", "동악집", "현주집"]
GOLD = "임백호집_3차완본_20260730.txt"


def build_d_lexicon():
    heads = set(open("assets/hdc_headwords.txt", encoding="utf-8").read().split())
    c = collections.Counter()
    for f in glob.glob("01_enriched/*.xml"):
        mj = os.path.splitext(os.path.basename(f))[0]
        if mj in TARGETS:            # 대상데이터는 신뢰 안 함
            continue
        t = open(f, encoding="utf-8").read()
        for m in re.finditer(r"<(term|d)>(.*?)</\1>", t, re.S):
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


def apply_targets():
    os.makedirs("02_suggested", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    for mj in TARGETS:
        src = f"02_suggested/{mj}.xml"
        if not os.path.exists(src):
            src = f"01_enriched/{mj}.xml"
        poems = poemdoc.parse_poems(open(src, encoding="utf-8").read())
        out = []
        rep = [f"# 3_termd_{mj}", ""]
        n_line = n_chg = 0
        for p in poems:
            raw = p.raw
            def repl(m):
                nonlocal n_line, n_chg
                head, body, tail = m.group(1), m.group(2), m.group(3)
                new, ntags = termdtag.retag_line(re.sub(r"</?(?:term|d)>", "", body))
                n_line += 1
                old_tags = len(re.findall(r"<(?:term|d)>", body))
                if abs(old_tags - ntags) >= 2:
                    n_chg += 1
                return head + new + tail
            raw = re.sub(r"(<Line\b[^>]*>)(.*?)(</Line\s*>)", repl, raw, flags=re.S | re.I)
            out.append(raw)
        with open(f"02_suggested/{mj}.xml", "w", encoding="utf-8", newline="\n") as f:
            f.write(poemdoc.wrap_corpus(out))
        rep.insert(2, f"**{mj}: {len(poems)}수, {n_line}행 재태깅, 태그수 크게 바뀐 행 {n_chg}**")
        with open(f"reports/3_termd_{mj}.md", "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(rep))
        print(f"{mj}: {len(poems)}수 재태깅 (태그수 급변 행 {n_chg})")


def main():
    lex = build_d_lexicon()
    print(f"d_lexicon: {len(lex)} 어휘")
    evaluate()
    if "--eval" not in sys.argv:
        apply_targets()


if __name__ == "__main__":
    main()

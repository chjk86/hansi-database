"""term/d 재태깅 — 사전 bigram(→term) + d-어휘(→d) + 부정어 정리 + 절주.

과다 자동태깅된 대상데이터(기재집·동명집·동악집·현주집)용.
수작업 태깅 문집에는 쓰지 않는다.
임백호집 골드 대비 토큰 F1 ~0.80.
"""
from __future__ import annotations
import os
import re
from . import xmlpoem as X

_HEADS = None
_DLEX = None
_NEG = re.compile(r"^(不|無|未|莫|勿|非|休|何|豈|寧)")
_NEG_KEEP = {"無限", "無人", "無情", "無事", "無心", "無端", "不同", "不見", "未歸", "無數"}
# 첩어(AABB형 의태·의성) — 골드도 일부만 태깅. 보수적으로 유지하되 플래그.
_CHOP = re.compile(r"^(.)\1$")


def _load():
    global _HEADS, _DLEX
    if _HEADS is None:
        p = "assets/hdc_headwords.txt"
        _HEADS = set(open(p, encoding="utf-8").read().split()) if os.path.exists(p) else set()
        dp = "assets/d_lexicon.txt"
        _DLEX = set(open(dp, encoding="utf-8").read().split()) if os.path.exists(dp) else set()
    return _HEADS, _DLEX


def retag_line(inner: str) -> tuple[str, int]:
    """inner의 <term>/<d> 를 재계산. <rhyme> 위치는 보존.
    return (새 inner, 변경 span 수)."""
    heads, dlex = _load()
    # rhyme 위치(한자 인덱스) 기록 후 태그 제거
    rhyme_idx = set()
    plain_chars = []
    for m in re.finditer(r"<rhyme>([^<]*)</rhyme>|<[^>]+>|([^<]+)", inner):
        if m.group(1) is not None:
            for ch in X.hanja_only(m.group(1)):
                rhyme_idx.add(len(plain_chars)); plain_chars.append(ch)
        elif m.group(2):
            for ch in m.group(2):
                if X._HANJA.match(ch):
                    plain_chars.append(ch)
    plain = "".join(plain_chars)
    n = len(plain)
    # bigram 스캔
    tags = []  # (start, end, kind)
    i = 0
    changed = 0
    while i < n - 1:
        bg = plain[i:i+2]
        kind = None
        if bg in heads:
            kind = "term"
        elif bg in dlex:
            kind = "d"
        if kind and _NEG.match(bg) and bg not in _NEG_KEEP:
            kind = None
        if kind:
            tags.append((i, i+2, kind))
            i += 2
        else:
            i += 1
    # 재조립
    out = []
    ti = 0
    j = 0
    while j < n:
        if ti < len(tags) and tags[ti][0] == j:
            s, e, k = tags[ti]
            seg = ""
            for x in range(s, e):
                seg += (f"<rhyme>{plain[x]}</rhyme>" if x in rhyme_idx else plain[x])
            out.append(f"<{k}>{seg}</{k}>")
            j = e
            ti += 1
        else:
            out.append(f"<rhyme>{plain[j]}</rhyme>" if j in rhyme_idx else plain[j])
            j += 1
    return "".join(out), len(tags)

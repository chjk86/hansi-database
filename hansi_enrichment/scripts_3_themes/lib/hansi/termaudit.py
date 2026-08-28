"""term/d span 감사 — 절주·사전·부정어 규칙으로 의심 span 표시."""
from __future__ import annotations
import re
import os
from . import xmlpoem as X

_HEADS = None


def heads():
    global _HEADS
    if _HEADS is None:
        p = "assets/hdc_headwords.txt"
        _HEADS = set(open(p, encoding="utf-8").read().split()) if os.path.exists(p) else set()
    return _HEADS


# 절주 경계 (0-index 시작 위치들). 5언 2·3 → 경계 {2}. 7언 2·2·3 → {2,4}.
JEOLJU = {5: {2}, 7: {2, 4}, 6: {2, 4}}

# 태깅 제외 부정/기능어 (매뉴얼)
FUNC_NEG = {"不敢", "不能", "不可", "莫道", "休言", "何必", "不知", "豈能", "未必", "無乃"}
KEEP_NEG = {"無消息", "無人", "無情", "不同", "不平", "未歸", "不歸", "未成", "無限", "不見"}


def line_spans(inner: str):
    """[(kind, text, start, end)] — <term>/<d> span 위치 (한자 인덱스 기준)."""
    # 태그 제거하며 각 span의 한자 구간 계산
    pos = 0
    out = []
    i = 0
    plain = []
    stack = []
    for m in re.finditer(r"<(/?)(term|d|rhyme)>|([^<]+)", inner):
        if m.group(3) is not None:
            text = m.group(3)
            for ch in text:
                if X._HANJA.match(ch):
                    plain.append(ch)
            if stack:
                stack[-1][1].extend(c for c in text if X._HANJA.match(c))
        else:
            closing, tag = m.group(1), m.group(2)
            if tag == "rhyme":
                continue
            if not closing:
                stack.append([tag, [], len(plain)])
            elif stack:
                t, chars, st = stack.pop()
                out.append((t, "".join(chars), st, len(plain)))
    return out, "".join(plain)


def audit_poem(raw: str):
    """의심 span 리스트."""
    cc = X.get_field(raw, "Charactercount") or ""
    n = {"오언": 5, "칠언": 7, "육언": 6}.get(cc)
    flags = []
    for order, inner, _ in X.lines(raw):
        spans, plain = line_spans(inner)
        L = len(plain)
        bnd = JEOLJU.get(n, set()) if n and L == n else set()
        for kind, txt, st, en in spans:
            reasons = []
            if len(txt) == 1:
                reasons.append("1글자")
            if len(txt) >= 2 and txt not in heads():
                reasons.append("사전미등재")
            # 절주 경계 횡단
            if bnd and any(st < b < en for b in bnd):
                reasons.append(f"절주횡단({st}-{en})")
            if txt in FUNC_NEG:
                reasons.append("기능어(제외권장)")
            if reasons:
                flags.append({"order": order, "kind": kind, "text": txt, "reasons": reasons})
    return flags

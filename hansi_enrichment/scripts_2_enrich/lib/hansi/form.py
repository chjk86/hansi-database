"""형식(Form) 판정 — 결정론적.

골드 관찰: Basetype/Detailtype는 사실상 **행수·행길이 규칙성**으로 결정된다
(평/측 압운은 보지 않음 — 측성압운 4행도 골드는 근체 절구).
  n=4  균일        → 근체시 / 절구
  n=8  균일        → 근체시 / 율시
  n>8 균일·짝수    → 근체시 / 배율
  그 외            → 고체시 / (제목으로 부·사·악부·잡체시 판별, 아니면 고시)
"""
from __future__ import annotations
import re
from . import xmlpoem as X
from . import rhyme as R

_GESI_TITLE = [
    (r"賦\s*$", "부"),
    (r"辭\s*$", "사(辭)"),
    (r"詞\s*$", "사(詞)"),
    (r"操\s*$", "금조"),
    (r"(行|歌|引|吟|謠|曲|篇|辭)\s*$", "악부"),
    (r"體\s*$", "잡체시"),
]


def _uniform(lens: list[int]) -> tuple[bool, int]:
    xs = [n for n in lens if n > 0]
    if not xs:
        return False, 0
    from collections import Counter
    c = Counter(xs)
    top, topn = c.most_common(1)[0]
    return (topn >= 0.85 * len(xs) and len(c) <= 2), top


def classify(raw: str, title: str = "") -> dict:
    ls = X.lines(raw)
    n = len(ls)
    lens = [len(h) for _, _, h in ls]
    uni, toplen = _uniform(lens)
    cc = X.charcount_label(raw)
    flags = []

    if n == 0:
        return {"basetype": "", "detailtype": "", "charcount": cc, "flags": ["행 없음"]}

    kunche = uni and cc != "불규칙" and (
        (n in (4, 8)) or (n > 8 and n % 2 == 0)
    )

    if kunche:
        bt = "근체시"
        dt = {4: "절구", 8: "율시"}.get(n, "배율")
        if len({x for x in lens if x}) > 1:
            flags.append("form_uncertain: 행길이 혼재")
        # 짝수행 말자 성조 — 측성압운이면 고절/고시 가능
        finals = [X.last_hanja(inner) for o, inner, _ in ls if o % 2 == 0]
        finals = [c for c in finals if c]
        if finals and all(R.is_ze_only(c) for c in finals):
            flags.append("form_uncertain: 측성압운 (고절/고시 가능)")
        if n > 8:
            flags.append("form_uncertain: 장형 — 배율/고시 평측 미검")
    else:
        bt = "고체시"
        dt = "고시"
        for rx, label in _GESI_TITLE:
            if re.search(rx, title):
                dt = label
                break
        reasons = []
        if not uni:
            reasons.append("행길이 불균일")
        if cc == "불규칙":
            reasons.append("자수 불규칙")
        if n % 2 == 1:
            reasons.append(f"홀수행({n})")
        if n not in (4, 8) and n <= 8:
            reasons.append(f"행수 {n}")
        flags.append("gesi:" + ",".join(reasons) if reasons else "gesi")

    return {"basetype": bt, "detailtype": dt, "charcount": cc, "flags": flags}

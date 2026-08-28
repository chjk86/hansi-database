"""Themes 제안 + 확신도(0~100).

거의 모든 시에 주분류 제안. 확신도는 임백호집 골드로 캘리브레이션한 구간 정밀도.
"""
from __future__ import annotations
import math
import re

# 함정: 시소러스가 제목 키워드에 속는 패턴 → 보정
_TRAP_FIX = [
    (re.compile(r"贈別|別[^。]{0,6}贈"), "farewell"),
    (re.compile(r"送(酒|米|炭|茶|柴|物|扇|筆|墨|花)"), None),   # 送+사물 → 시소러스 신뢰 낮춤, 그대로
]
_CHAUN = re.compile(r"[次和用酬賡]\s*[^。]{0,10}韻|奉和|敬次")
_AKBU = re.compile(r"(曲|行|歌|引|吟|謠|操|辭)\s*$")
_JEYONG = re.compile(r"題詠|帖字|應製")


def suggest(th, raw: str, title: str):
    """return (cat, conf0_100, basis, title_hit, term_hit, note)."""
    sc = th.score(raw)
    mc = sc.most_common(6)
    if not mc:
        return None, 0, "", [], [], "신호 없음"
    top, s1 = mc[0]
    s2 = mc[1][1] if len(mc) > 1 else 0.0
    ratio = s1 / s2 if s2 else 99.0
    th_hit, tm_hit = th.evidence_for(raw, top)
    note = ""

    # 함정 보정
    if _CHAUN.search(title) and top in ("donate",):
        # 차운시: 제목 donate 무효 → 2위로
        note = "차운(제목 donate 무시)"
        if len(mc) > 1:
            top, s1 = mc[1]
            s2 = mc[2][1] if len(mc) > 2 else 0.0
            ratio = s1 / s2 if s2 else 3.0
            th_hit, tm_hit = th.evidence_for(raw, top)
        ratio *= 0.5
    for rx, fix in _TRAP_FIX:
        if rx.search(title):
            if fix and fix != top:
                top = fix
                th_hit, tm_hit = th.evidence_for(raw, top)
                note = "제목보정"
            ratio *= 0.6
    if _AKBU.search(title) or _JEYONG.search(title):
        ratio *= 0.55
        note = (note + " 악부/제영") if note else "악부/제영(확신↓)"

    # 확신도: ratio + 절대점수 + title_hit 로그 스케일 → 0~100
    conf = 30
    conf += min(35, 12 * math.log(max(ratio, 1.01)))
    conf += min(20, 4 * math.log(max(s1, 1)))
    if th_hit:
        conf += 12
    if not th_hit and not tm_hit:
        conf -= 15
    conf = max(3, min(97, round(conf)))

    basis = []
    if th_hit:
        basis.append("title")
    if tm_hit:
        basis.append("term")
    return top, conf, ", ".join(basis) or "term", th_hit, tm_hit, note

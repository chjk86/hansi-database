"""운목·성조·통운 조회. assets/ 필요 (10_assets.py 산출)."""
from __future__ import annotations
import os
import functools

_A = "assets"


@functools.lru_cache(maxsize=1)
def _load():
    ym = {}     # char -> set(운목)
    tone = {}   # char -> set(평/측)
    path = os.path.join(_A, "rhyme_map.tsv")
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            c, y, pz, _detail = line.rstrip("\n").split("\t")
            ym.setdefault(c, set()).add(y)
            tone.setdefault(c, set()).add(pz)
    tg = {}     # 운목 -> 부번호
    with open(os.path.join(_A, "tongun.tsv"), encoding="utf-8") as f:
        next(f)
        for line in f:
            y, g = line.rstrip("\n").split("\t")
            tg[y] = g
    return ym, tone, tg


def rhyme_groups(ch: str) -> set[str]:
    """글자가 속한 운목들(다음자면 복수)."""
    return set(_load()[0].get(ch, ()))


def tones(ch: str) -> set[str]:
    return set(_load()[1].get(ch, ()))


def is_ping(ch: str) -> bool:
    """평성일 수 있으면 True (다음자 관대)."""
    t = tones(ch)
    return ("평" in t) if t else False


def is_ze_only(ch: str) -> bool:
    """측성으로만 쓰이면 True."""
    t = tones(ch)
    return bool(t) and t == {"측"}


def tongun_of(ym: str) -> str | None:
    return _load()[2].get(ym)


def tongun_set(ch: str) -> set[str]:
    """글자가 속한 통운 부번호들."""
    tg = _load()[2]
    return {tg[y] for y in rhyme_groups(ch) if y in tg}


def same_rhyme(a: str, b: str, tongun: bool = True) -> bool:
    ga, gb = rhyme_groups(a), rhyme_groups(b)
    if ga & gb:
        return True
    if tongun:
        return bool(tongun_set(a) & tongun_set(b))
    return False


def dominant_group(chars: list[str]) -> tuple[str | None, int]:
    """운자 리스트의 최빈 운목과 그 표수."""
    from collections import Counter
    c = Counter()
    for ch in chars:
        for y in rhyme_groups(ch):
            c[y] += 1
    if not c:
        return None, 0
    y, n = c.most_common(1)[0]
    return y, n

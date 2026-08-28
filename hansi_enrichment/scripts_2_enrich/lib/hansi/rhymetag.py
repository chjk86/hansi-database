"""Form 확정 후 <rhyme> 재태깅."""
from __future__ import annotations
import re
from . import xmlpoem as X
from . import rhyme as R

_LINE_RE = re.compile(r'(<Line\b[^>]*>)(.*?)(</Line\s*>)', re.S | re.I)


def _last_hanja_pos(inner_notag: str):
    for i in range(len(inner_notag) - 1, -1, -1):
        if X._HANJA.match(inner_notag[i]):
            return i
    return None


def _strip_rhyme(inner: str) -> str:
    return re.sub(r"</?rhyme>", "", inner)


def _add_rhyme_to_last_hanja(inner: str) -> tuple[str, bool]:
    """inner(태그 포함)의 마지막 한자에 <rhyme> 씌움.
    그 한자가 <term>/<d>의 마지막 글자면 그 안에, 아니면 bare.
    return (새 inner, 마지막글자가 term/d 안이었나)."""
    inner = _strip_rhyme(inner)
    # 마지막 한자의 문자열 위치 찾기 (태그 무시)
    # 뒤에서부터 훑으며 태그 스킵
    i = len(inner)
    while i > 0:
        if inner[i-1] == ">":
            j = inner.rfind("<", 0, i)
            if j != -1:
                i = j
                continue
        ch = inner[i-1]
        if X._HANJA.match(ch):
            # ch가 </term> 또는 </d> 바로 앞인가?
            after = inner[i:]
            nested = bool(re.match(r"\s*</(term|d)\s*>", after))
            new = inner[:i-1] + "<rhyme>" + ch + "</rhyme>" + inner[i:]
            return new, nested
        i -= 1
    return inner, False


def retag(raw: str, basetype: str, detailtype: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    lines = X.lines(raw)
    n = len(lines)
    if n == 0:
        return raw, flags
    by_order = {o: (inner, notag) for o, inner, notag in lines}

    # 압운행 결정
    rhyme_orders: set[int] = set()
    if basetype == "근체시":
        rhyme_orders = {o for o in by_order if o % 2 == 0}
        # 수구압운 — 짝수행 압운이 평성일 때만
        l1 = by_order.get(1)
        even_finals = [notag[-1] for o, (inner, notag) in by_order.items()
                       if o % 2 == 0 and notag]
        ping_even = sum(1 for c in even_finals if R.is_ping(c))
        ze_even = sum(1 for c in even_finals if R.is_ze_only(c))
        grp = set()
        for c in even_finals:
            grp |= R.rhyme_groups(c)
        if ze_even > ping_even:
            flags.append("측성압운 (근체판정 재검토)")
        elif l1 and l1[1]:
            c1 = l1[1][-1]
            if R.is_ping(c1) and (R.rhyme_groups(c1) & grp or
                                  R.tongun_set(c1) & {g for c in even_finals for g in R.tongun_set(c)}):
                rhyme_orders.add(1)
                flags.append("수구압운")
    else:
        # 고체: 짝수행을 기본 압운행으로 보고, 말자 운목 연속성으로 환운 표시.
        even = [o for o in sorted(by_order) if o % 2 == 0]
        rhyme_orders = set(even)
        run = None  # 현재 운 그룹(운목 집합)
        for o in even:
            notag = by_order[o][1]
            if not notag:
                continue
            g = R.rhyme_groups(notag[-1])
            if not g:
                continue
            if run is None:
                run = set(g)
            elif g & run or (R.tongun_set(notag[-1]) & _tongun_of_groups(run)):
                run |= (g & run) or g
            else:
                flags.append(f"rhyme_change@{o}")
                run = set(g)

    # 미상 운자 체크
    for o in rhyme_orders:
        notag = by_order[o][1]
        if notag and not R.rhyme_groups(notag[-1]):
            flags.append(f"rhyme_char_unknown@{o}:{notag[-1]}")

    # 재구성
    removed = added = 0
    idx = 0

    def repl(m):
        nonlocal idx, removed, added
        idx += 1
        head, inner, tail = m.group(1), m.group(2), m.group(3)
        om = re.search(r'order\s*=\s*"(\d+)"', head)
        order = int(om.group(1)) if om else idx
        had = "<rhyme>" in inner
        if order in rhyme_orders:
            new_inner, nested = _add_rhyme_to_last_hanja(inner)
            if not had:
                added += 1
            return head + new_inner + tail
        else:
            if had:
                removed += 1
            return head + _strip_rhyme(inner) + tail

    new_raw = _LINE_RE.sub(repl, raw)
    if removed:
        flags.append(f"rhyme_removed:{removed}")
    if added:
        flags.append(f"rhyme_added:{added}")
    return new_raw, flags


def _tongun_of_groups(groups: set[str]) -> set[str]:
    out = set()
    for y in groups:
        g = R.tongun_of(y)
        if g:
            out.add(g)
    return out

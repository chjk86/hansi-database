"""<Poem> raw 블록 내부 조작 (정규식 기반, 비 well-formed 허용)."""
from __future__ import annotations
import re

_HANJA = re.compile(r"[㐀-䶿一-鿿豈-﫿\U00020000-\U0002ffff]")


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def hanja_only(s: str) -> str:
    return "".join(_HANJA.findall(s))


def lines(raw: str):
    """[(order:int, inner_raw:str, hanja:str)] — <text> 안의 <Line>만."""
    tm = re.search(r"<text\b[^>]*>(.*?)</text\s*>", raw, re.S | re.I)
    scope = tm.group(1) if tm else raw
    out = []
    for m in re.finditer(r'<Line\b([^>]*)>(.*?)</Line\s*>', scope, re.S | re.I):
        attrs, inner = m.group(1), m.group(2)
        om = re.search(r'\border\s*=\s*"(\d+)"', attrs)
        order = int(om.group(1)) if om else len(out) + 1
        out.append((order, inner, hanja_only(strip_tags(inner))))
    return out


def get_field(raw: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}\s*>(.*?)</{tag}\s*>", raw, re.S | re.I)
    return m.group(1).strip() if m else None


def set_field(raw: str, tag: str, value: str) -> str:
    """<tag>...</tag> 내용 교체. 없으면 그대로."""
    def rep(m):
        return f"<{tag}>{value}</{tag}>"
    new, n = re.subn(rf"<{tag}\s*>.*?</{tag}\s*>", rep, raw, count=1, flags=re.S | re.I)
    return new


def line_lengths(raw: str) -> list[int]:
    return [len(h) for _, _, h in lines(raw)]


def charcount_label(raw: str) -> str:
    lens = [n for n in line_lengths(raw) if n > 0]
    if not lens:
        return "불규칙"
    from collections import Counter
    c = Counter(lens)
    top, topn = c.most_common(1)[0]
    if len(c) >= 3 or topn < 0.8 * len(lens):
        return "불규칙"
    return {5: "오언", 6: "육언", 7: "칠언"}.get(top, "불규칙")


def rhyme_chars(raw: str) -> list[tuple[int, str]]:
    """[(order, 운자)] — <rhyme> 태그된 글자."""
    out = []
    for order, inner, _ in lines(raw):
        for m in re.finditer(r"<rhyme>([^<]+)</rhyme>", inner):
            out.append((order, m.group(1)))
    return out


def last_hanja(raw_line_inner: str) -> str | None:
    h = hanja_only(strip_tags(raw_line_inner))
    return h[-1] if h else None

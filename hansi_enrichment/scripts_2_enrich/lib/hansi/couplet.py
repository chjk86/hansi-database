"""율시·배율 <Couplet> 래핑."""
from __future__ import annotations
import re
from . import xmlpoem as X

_LINE_RE = re.compile(r'([ \t]*<Line\b[^>]*>.*?</Line\s*>[ \t]*\n?)', re.S | re.I)


def _line_order(block: str) -> int:
    m = re.search(r'order\s*=\s*"(\d+)"', block)
    return int(m.group(1)) if m else 0


def wrap(raw: str, basetype: str, detailtype: str) -> tuple[str, list[str]]:
    if basetype != "근체시" or detailtype not in ("율시", "배율"):
        return raw, []
    if "<Couplet" in raw:
        return raw, ["couplet_이미존재"]
    ls = X.lines(raw)
    n = len(ls)
    if n < 8 or n % 2:
        return raw, []
    # 대장 행쌍: 1·2행 제외, 마지막 2행 제외, 나머지 인접쌍
    pair_starts = set(range(3, n - 1, 2))  # 3,5,7,... n-3  (n-1행이 마지막 직전)
    if detailtype == "율시":
        pair_starts = {3, 5}

    tm = re.search(r"(<text\b[^>]*>)(.*?)(</text\s*>)", raw, re.S | re.I)
    if not tm:
        return raw, ["couplet_실패: text 없음"]
    body = tm.group(2)
    blocks = _LINE_RE.findall(body)
    if len(blocks) != n:
        return raw, [f"couplet_실패: Line {len(blocks)}≠{n}"]
    first_at = body.find(blocks[0])
    prefix = body[:first_at]  # <text> 뒤 개행/들여쓰기 보존

    out = []
    i = 0
    while i < len(blocks):
        o = _line_order(blocks[i])
        if o in pair_starts and i + 1 < len(blocks):
            b1 = blocks[i].rstrip("\n")
            b2 = blocks[i + 1].rstrip("\n")
            out.append(f"      <Couplet>{b1.strip()}\n        {b2.strip()}</Couplet>\n")
            i += 2
        else:
            out.append(blocks[i])
            i += 1
    new_body = prefix + "".join(out)
    new_raw = raw[:tm.start(2)] + new_body + raw[tm.end(2):]
    return new_raw, [f"couplet_추가:{len(pair_starts)}쌍"]

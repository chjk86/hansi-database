"""Themes 스키마 정리 — 템플릿 스텁·구스키마 제거."""
from __future__ import annotations
import re

_STUB_CATS = ("영문주제명", "영문 주제명")
_STUB_TEXT = ("국문주제명", "국문 주제명")


def _theme_is_stub(m: str) -> bool:
    if any(s in m for s in _STUB_CATS):
        return True
    if any(s in m for s in _STUB_TEXT):
        return True
    if 'category=""' in m or "category=''" in m:
        return True
    return False


def clean(raw: str) -> tuple[str, list[str]]:
    m = re.search(r"<Themes\b[^>]*>(.*?)</Themes\s*>", raw, re.S | re.I)
    if not m:
        return raw, []
    inner = m.group(1)
    flags = []
    # 유효 <Theme ...> 만 보존
    kept = []
    for tm in re.finditer(r"<Theme\b[^>]*>.*?</Theme\s*>", inner, re.S | re.I):
        t = tm.group(0)
        if _theme_is_stub(t):
            flags.append("theme_stub_제거")
        else:
            kept.append(t.strip())
    had_mainsub = bool(re.search(r"</?(Main|Sub)\b", inner, re.I))
    # 대문자 단일 카테고리 태그(<Dream sort="main">…) 도 구스키마 — 제거하되 기록
    old_single = re.findall(r"<([A-Z][a-z]+)\s+sort=", inner)
    if old_single:
        flags.append(f"theme_구태그_제거:{','.join(sorted(set(old_single)))}")
    if had_mainsub:
        flags.append("theme_MainSub_제거")

    if kept:
        new_inner = "\n        " + "\n        ".join(kept) + "\n      "
    else:
        new_inner = ""
    new = raw[:m.start(1)] + new_inner + raw[m.end(1):]
    return new, flags

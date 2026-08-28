"""작업자 제출 파일명 파싱 → 정렬 키 / ID 구간."""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class FileMeta:
    path: str
    name: str                       # NFC
    date_key: tuple                  # 정렬 가능. 클수록 최신
    id_range: tuple[int, int] | None # 파일명이 밝힌 ID 구간
    worker: str | None
    markers: list[str] = field(default_factory=list)
    date_src: str = "filename"       # filename | mtime | none


_YY = r"(?:(\d{2})년도?_?)?"
_ID_RANGE_RES = [
    re.compile(r"[Pp]?0*(\d{4,6})\s*[~\-]\s*[Pp]?0*(\d{4,6})"),
    re.compile(r"\(0*(\d{4,6})\s*[~\-]\s*0*(\d{4,6})\)"),
]
_MARKERS = ["(수정)", "(완성본", "최종", "최신본", "지영원수정", "(진행중)"]


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def parse_id_range(name: str) -> tuple[int, int] | None:
    for rx in _ID_RANGE_RES:
        m = rx.search(name)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            return (min(a, b), max(a, b))
    return None


def parse_date_key(name: str) -> tuple[tuple, str]:
    """(정렬키, 소스). 정렬키가 클수록 최신.
    형식: YYYYMMDD / YY년도 MM월 N주차 / MM월 N주차 / 작업 N주차 / NN주차 / MM월 최종 / YY년_M월
    """
    n = name
    # 1) YYYYMMDD (손곡시집 '20260821')
    m = re.search(r"20(\d{2})(\d{2})(\d{2})", n)
    if m:
        yy, mm, dd = map(int, m.groups())
        return ((yy, mm, dd, 0), "filename")
    # 2) 연도
    ym = re.search(r"(\d{2})년도?", n)
    yy = int(ym.group(1)) if ym else None
    # 3) 월
    mm_m = re.search(r"(\d{1,2})월", n)
    mm = int(mm_m.group(1)) if mm_m else None
    # 4) 주차: 'N주차' / '작업 N주차' / '작업N주차'
    wk_m = re.search(r"(\d{1,3})\s*주차", n)
    wk = int(wk_m.group(1)) if wk_m else None
    # '최종' → 해당 월 말로
    final = "최종" in n
    if yy is None and mm is None and wk is None and not final:
        return ((0, 0, 0, 0), "none")
    # 연도 미상인데 월만 있으면: 25년 기준(작업 시작연도) 가정
    y = yy if yy is not None else 25
    mo = mm if mm is not None else (99 if final else 0)
    wkv = 99 if final else (wk if wk is not None else 0)
    return ((y, mo, wkv, 0), "filename")


def parse(path: str, name: str, mtime: float | None = None) -> FileMeta:
    name = _norm(name)
    dk, src = parse_date_key(name)
    if src == "none" and mtime:
        dk, src = ((0, 0, 0, int(mtime)), "mtime")
    markers = [mk for mk in _MARKERS if mk in name]
    wm = re.search(r"(김남지|김재윤|김영인|김용미|김민구|왕예|이길환|이연지|이승환|남윤지|송채은|육숙정|심영주|이연지|이예리|지영원)", name)
    return FileMeta(
        path=path, name=name, date_key=dk,
        id_range=parse_id_range(name),
        worker=wm.group(1) if wm else None,
        markers=markers, date_src=src,
    )

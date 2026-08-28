"""파일 읽기 (인코딩·RTF 자동)."""
from __future__ import annotations
import os

try:
    from striprtf.striprtf import rtf_to_text
except ImportError:
    rtf_to_text = None


def read_text(path: str) -> str:
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        for enc in ("utf-8", "cp949", "euc-kr"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                text = None
        if text is None:
            text = raw.decode("utf-8", "ignore")
    if path.lower().endswith(".rtf"):
        if rtf_to_text is None:
            raise RuntimeError("striprtf 필요: pip install striprtf")
        text = rtf_to_text(text)
    return text


def list_data_files(folder: str) -> list[str]:
    """태깅 데이터 파일만. hwp/csv/docx/원문·번역 제외."""
    out = []
    for f in sorted(os.listdir(folder)):
        p = os.path.join(folder, f)
        if not os.path.isfile(p):
            continue
        low = f.lower()
        if low.endswith((".hwp", ".csv", ".docx")):
            continue
        if "원문" in f or "번역" in f:
            continue
        if f.startswith("태깅정리_") or f.startswith("output_"):
            continue
        out.append(p)
    return out

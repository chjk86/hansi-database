"""1단계: 문집별 코퍼스 재통합.

사용: python 30_merge.py
출력: 00_corpus/<문집>.xml (19개) + reports/00_merge.md
"""
from __future__ import annotations
import os, sys, re, unicodedata, glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from hansi import poemdoc, fname
from hansi.io import read_text, list_data_files

ROOT = "00_raw/4-1. 생성 데이터 [전원]"
TGT = "대상데이터_데이터클리닝"
OUT = "00_corpus"
REP = "reports"

# 문집 설정: NFC 폴더명 → (mode, note)
#  cumulative = 최신 날짜 파일 1개
#  incremental = ID 구간별 병합 + 대상데이터 공백보충
#  gold_fixed = 지정 파일 고정
#  target_only = 대상데이터만
CONF = {
    "성소부부고_허균": ("cumulative", "왕예 주차"),
    "옥봉집_백광훈": ("cumulative", "왕예 주차"),
    "고죽유고_최경창": ("cumulative", "이길환"),
    "손곡시집_이달": ("cumulative", "김민구 날짜"),
    "소재집_노수신": ("cumulative", "27~46주차 전체누적"),
    "현곡집_조위한": ("cumulative", "이승환 주차"),
    "호음잡고_정사룡": ("cumulative", "김민구 단일본"),
    "임백호집_임제": ("gold_fixed", "임백호집_3차완본_20260730.txt"),
    "눌재집_박상": ("incremental", "8월1~4 + 작업5~12주차"),
    "어우집_유몽인": ("incremental", "주차별 ID구간"),
    "오산집_차천로": ("incremental", "주차별 ID구간, 빈파일 제외"),
    "용재집_이행": ("incremental", "주차별 ID구간 연속"),
    "읍취헌유고_박은": ("incremental", "rtf + txt/xml"),
    "지봉집_이수광": ("incremental", "주차별 ID구간"),
    "지천집_황정욱": ("incremental", "ID구간 3 + 요약본"),
    # 석주집_권필: 팀 통합 진행중 → 1단계 제외
}
TARGET_ONLY = {  # 문집명(태깅_ 접미) : 대상데이터 파일 stem
    "기재집": "태깅_기재집", "동명집": "태깅_동명집",
    "동악집": "태깅_동악집", "현주집": "태깅_현주집",
}
GOLD_FILE = "임백호집_3차완본_20260730.txt"


def nfc(s): return unicodedata.normalize("NFC", s)


def load_target_poems(stem: str):
    p = os.path.join(TGT, stem + ".txt")
    if not os.path.exists(p):
        return {}
    return {pm.num: pm for pm in poemdoc.parse_poems(read_text(p)) if pm.num is not None}


def merge_incremental(files, mj_short, log):
    """files: list[(FileMeta, [Poem])]  →  {num: Poem}, 병합 로그."""
    # (첫 poem num, date_key) 순 정렬
    def keyf(item):
        fm, poems = item
        first = min((p.num for p in poems if p.num is not None), default=10**9)
        return (first, fm.date_key)
    files = sorted(files, key=keyf)
    merged: dict[int, poemdoc.Poem] = {}
    for fm, poems in files:
        for p in poems:
            if p.num is None:
                log.append(f"  - id없음 무시: {p.id} ({fm.name})")
                continue
            if p.num in merged:
                log.append(f"  - 중복 P{p.num}: {fm.name} 우선(나중)")
            merged[p.num] = p
    # 공백 보충
    if merged:
        lo, hi = min(merged), max(merged)
        tgt = load_target_poems("태깅_" + mj_short)
        filled, real_gap = [], []
        for n in range(lo, hi + 1):
            if n in merged:
                continue
            if n in tgt:
                merged[n] = tgt[n]
                filled.append(n)
            else:
                real_gap.append(n)
        if filled:
            log.append(f"  - 대상데이터 보충 {len(filled)}수: " + rng_str(filled))
        if real_gap:
            log.append(f"  - **실공백** {len(real_gap)}수: " + rng_str(real_gap))
    return merged


def rng_str(nums):
    if not nums:
        return "-"
    nums = sorted(nums)
    parts, s = [], nums[0]
    for a, b in zip(nums, nums[1:] + [None]):
        if b != (a + 1 if a is not None else None):
            parts.append(f"P{s}" if s == a else f"P{s}~P{a}")
            s = b
    return " ".join(parts)


def write_corpus(mj_short, poems, log, sort_by_num=True):
    """poems: list[Poem] 또는 {num: Poem}."""
    if isinstance(poems, dict):
        ordered = [poems[n] for n in sorted(poems)] if sort_by_num else list(poems.values())
    else:
        ordered = sorted(poems, key=lambda p: (p.num is None, p.num or 0)) if sort_by_num else list(poems)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, mj_short + ".xml")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(poemdoc.wrap_corpus([p.raw for p in ordered]))
    nums = [p.num for p in ordered if p.num is not None]
    nrep = sum(1 for p in ordered if p.repaired)
    nbad = sum(1 for p in ordered if not p.well_formed)
    tail = ""
    if nrep:
        tail += f"  복구 {nrep}"
    if nbad:
        tail += f"  **미복구 {nbad}**"
    log.append(f"  → {path}  {len(ordered)}수  P{nums[0]}~P{nums[-1]}{tail}")
    return len(ordered)


def main():
    os.makedirs(REP, exist_ok=True)
    report = ["# 00_merge 리포트", ""]
    folders = {nfc(d): os.path.join(ROOT, d) for d in os.listdir(ROOT)
               if os.path.isdir(os.path.join(ROOT, d))}

    for mj_full, (mode, note) in CONF.items():
        mj_short = mj_full.split("_")[0]
        report.append(f"\n## {mj_full}  [{mode}]  {note}")
        log = report

        if mode == "gold_fixed":
            poems = poemdoc.parse_poems(read_text(GOLD_FILE))
            write_corpus(mj_short, poems, log, sort_by_num=False)  # 골드 원본 순서 유지
            continue

        folder = folders.get(mj_full)
        if not folder:
            log.append(f"  ! 폴더 없음")
            continue
        entries = []
        for p in list_data_files(folder):
            fm = fname.parse(p, os.path.basename(p), os.path.getmtime(p))
            poems = poemdoc.parse_poems(read_text(p))
            entries.append((fm, poems))
            log.append(f"  · {fm.name[:55]:55} 수={len(poems):<5} date={fm.date_key} "
                       f"idr={fm.id_range or '-'}")

        if mode == "cumulative":
            entries = [e for e in entries if e[1]]  # 빈 파일 제외
            fm, poems = max(entries, key=lambda e: e[0].date_key)
            log.append(f"  채택: {fm.name}")
            by = {p.num: p for p in poems if p.num is not None}
            write_corpus(mj_short, by, log)

        elif mode == "incremental":
            entries = [e for e in entries if e[1]]
            by = merge_incremental(entries, mj_short, log)
            write_corpus(mj_short, by, log)

    # target-only 4문집
    for mj_short, stem in TARGET_ONLY.items():
        report.append(f"\n## {mj_short}  [target_only]  대상데이터")
        by = load_target_poems(stem)
        write_corpus(mj_short, by, report)

    with open(os.path.join(REP, "00_merge.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(report))
    print("\n".join(l for l in report if l.startswith(("##", "  →", "  채택", "  - **"))))
    print(f"\n리포트: {REP}/00_merge.md")


if __name__ == "__main__":
    main()

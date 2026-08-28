"""1단계: Drive 원본 확보.

자동 다운로드(gdown --folder)는 Google Drive 레이트리밋('have had many accesses')에
막힘. 실제로는 사용자가 Drive에서 "전체 다운로드"한 zip을 사용.

  4-1. 생성 데이터 [전원]-<타임스탬프>-1-001.zip  (214 파일, 16 문집)

이 스크립트는 그 zip을 00_raw/ 로 전개한다. gdown 재시도 로직도 폴백으로 둔다.

사용: python 10_fetch.py [zip경로]
"""
from __future__ import annotations
import os, sys, glob, zipfile

RAW = "00_raw"
DEFAULT_ZIP_GLOBS = [
    r"N:\개인\mybox\클로드\4-1. 생성 데이터*zip",
    "../*생성 데이터*zip",
    "*생성 데이터*zip",
]


def main():
    os.makedirs(RAW, exist_ok=True)
    zp = sys.argv[1] if len(sys.argv) > 1 else None
    if not zp:
        for g in DEFAULT_ZIP_GLOBS:
            hits = glob.glob(g)
            if hits:
                zp = hits[0]
                break
    if not zp or not os.path.exists(zp):
        sys.exit("zip을 찾지 못함. 경로를 인자로 주세요.")
    with zipfile.ZipFile(zp) as z:
        z.extractall(RAW)
        print(f"{zp}\n → {RAW}/  ({len(z.namelist())} entries)")
    # 폴더 정리: 00_raw/4-1. 생성 데이터 [전원]/<문집>/...
    inner = glob.glob(os.path.join(RAW, "*생성 데이터*"))
    n_mj = sum(1 for d in glob.glob(os.path.join(inner[0], "*")) if os.path.isdir(d)) if inner else 0
    print(f"문집 폴더: {n_mj}")


if __name__ == "__main__":
    main()

"""1단계 전체 실행: fetch → merge → lint → align.

사용:
  python scripts/run.py            # merge+lint+align (00_raw 이미 있음)
  python scripts/run.py --fetch    # zip 전개부터
"""
from __future__ import annotations
import os, sys, runpy

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "lib"))
os.chdir(os.path.join(HERE, ".."))  # 프로젝트 루트

STEPS = ["30_merge", "40_lint", "50_align"]
if "--fetch" in sys.argv:
    STEPS = ["10_fetch"] + STEPS

for s in STEPS:
    print(f"\n{'='*20} {s} {'='*20}")
    runpy.run_path(os.path.join(HERE, s + ".py"), run_name="__main__")

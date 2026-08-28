"""1단계 수용 기준 검증."""
from __future__ import annotations
import os, sys, glob, xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from hansi import poemdoc
from hansi.io import read_text

OUT = "00_corpus"

EXPECT = {  # 문집: 예상 수 (실측 기준)
    "성소부부고": 570, "옥봉집": 506, "고죽유고": 245, "손곡시집": 368,
    "소재집": 1529, "현곡집": 744, "호음잡고": 2493, "임백호집": 723,
    "눌재집": 206, "어우집": 507, "오산집": 520, "용재집": 784,
    "읍취헌유고": 259, "지봉집": 462, "지천집": 119,
    "기재집": 1710, "동명집": 1215, "동악집": 4644, "현주집": 631,
}

fails = 0
total = 0
for path in sorted(glob.glob(os.path.join(OUT, "*.xml"))):
    mj = os.path.splitext(os.path.basename(path))[0]
    text = open(path, encoding="utf-8").read()
    poems = poemdoc.parse_poems(text)
    total += len(poems)
    ids = [p.id for p in poems]
    nums = [p.num for p in poems if p.num is not None]
    dups = len(ids) - len(set(ids))
    exp = EXPECT.get(mj)
    cont = "연속" if nums == list(range(nums[0], nums[-1] + 1)) else f"공백 {(nums[-1]-nums[0]+1)-len(nums)}"
    ok = dups == 0 and (exp is None or len(poems) == exp)
    fails += not ok
    print(f"{'OK ' if ok else 'FAIL'} {mj:12} {len(poems):>5}수 (exp {exp}) P{nums[0]}~P{nums[-1]} {cont} dup={dups}")

# 임백호집 == 골드
g = {p.id for p in poemdoc.parse_poems(read_text('임백호집_3차완본_20260730.txt'))}
c = {p.id for p in poemdoc.parse_poems(open(os.path.join(OUT, '임백호집.xml'), encoding='utf-8').read())}
gold_ok = g == c
fails += not gold_ok
print(f"\n{'OK ' if gold_ok else 'FAIL'} 임백호집 == 골드 (골드 {len(g)}, 통합 {len(c)})")

# XML 로드 (Corpus 래핑)
xml_ok = 0
for path in glob.glob(os.path.join(OUT, "*.xml")):
    try:
        ET.fromstring(open(path, encoding="utf-8").read())
        xml_ok += 1
    except ET.ParseError:
        pass
print(f"XML 파서 로드: {xml_ok}/19  (인라인 태그 불균형으로 실패 예상 — 2단계 정리 대상)")

print(f"\n총 {total}수 · 실패 {fails}")
sys.exit(1 if fails else 0)

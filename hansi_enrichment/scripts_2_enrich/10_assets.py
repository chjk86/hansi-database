"""2단계 자원 생성:
  assets/rhyme_map.tsv   글자<TAB>운목<TAB>성조(평/측)<TAB>세부성조
  assets/tongun.tsv      운목<TAB>통운그룹번호(사림정운 19부)
  assets/hdc_headwords.txt  한어대사전 표제어

검증: 골드 임백호집 운자 커버리지.
"""
from __future__ import annotations
import os, re, sys, unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from hansi import poemdoc
from hansi.io import read_text

PS = "assets/평수운_수정.txt"
HDC = "한어대사전.txt"
OUT = "assets"

PING = {"上平", "下平"}  # 평성

# 사림정운(詞林正韻) 19부 — 운목(평성 기준 이름) → 부번호. 상·거·입성 대응 포함.
TONGUN = {
    1: "東 冬",
    2: "江 陽",
    3: "支 微 齊 灰",
    4: "魚 虞",
    5: "佳",
    6: "眞 文 元",
    7: "寒 刪 先",
    8: "蕭 肴 豪",
    9: "歌 麻",
    11: "庚 靑 蒸",
    12: "尤",
    13: "侵 覃 鹽 咸",
    # 입성
    15: "屋 沃",
    16: "覺 藥",
    17: "質 物 月 曷 黠 屑",
    18: "陌 錫 職 緝",
    19: "合 洽",
}
# 상·거성 운목을 같은 부에 추가 (詞林正韻: 부1~14는 평·상·거 공유)
_ZE = {
    1: "董 腫 送 宋", 2: "講 養 絳 漾", 3: "紙 尾 薺 賄 寘 未 霽 隊 泰",
    4: "語 麌 御 遇", 5: "蟹 卦", 6: "軫 吻 阮 震 問 願",
    7: "旱 潸 銑 翰 諫 霰", 8: "篠 巧 皓 嘯 效 號", 9: "哿 箇 馬 禡",
    11: "梗 迥 敬 徑", 12: "有 宥", 13: "寢 沁 感 儉 豏 勘 豔 陷",
}
for _g, _s in _ZE.items():
    TONGUN[_g] = TONGUN[_g] + " " + _s


def build_rhyme_map():
    rows = []  # (char, 운목, 평측, 세부)
    lines = read_text(PS).splitlines()
    cur = None
    for l in lines:
        if l.startswith("其它僻字"):
            chars = l.split("：", 1)[1] if "：" in l else l[len("其它僻字"):]
            if cur:
                for c in chars:
                    if c.strip():
                        rows.append((c, cur[0], cur[1], cur[2]))
            continue
        m = re.match(r"^(.+?)(上平|下平|上|去|入)(\d+)　(.+)$", l)
        if not m:
            continue
        ym, tone, no, chars = m.groups()
        pz = "평" if tone in PING else "측"
        cur = (ym, pz, tone)
        for c in chars:
            if c.strip():
                rows.append((c, ym, pz, tone))
    # 중복 글자: 첫 등장 유지(+다중운은 별도 처리 여지) — 여기선 set로 dedup(char,ym)
    seen = set()
    uniq = []
    for r in rows:
        k = (r[0], r[1])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    with open(os.path.join(OUT, "rhyme_map.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("char\t운목\t평측\t세부성조\n")
        for c, ym, pz, tn in uniq:
            f.write(f"{c}\t{ym}\t{pz}\t{tn}\n")
    return uniq


def build_tongun():
    with open(os.path.join(OUT, "tongun.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("운목\t부번호\n")
        for grp, yms in TONGUN.items():
            for ym in yms.split():
                f.write(f"{ym}\t{grp}\n")


def build_headwords():
    heads = set()
    with open(HDC, encoding="utf-8", errors="ignore") as fin:
        for line in fin:
            m = re.match(r"^【([^】]+)】", line)
            if m:
                heads.add(m.group(1))
    with open(os.path.join(OUT, "hdc_headwords.txt"), "w", encoding="utf-8", newline="\n") as f:
        for h in sorted(heads):
            f.write(h + "\n")
    return heads


def verify(rmap):
    charset = {c for c, *_ in rmap}
    gold = poemdoc.parse_poems(read_text("임백호집_3차완본_20260730.txt"))
    rc = []
    for p in gold:
        for m in re.finditer(r"<rhyme>([^<]+)</rhyme>", p.raw):
            rc.append(m.group(1))
    miss = sorted({c for c in rc if c not in charset})
    print(f"골드 임백호집 운자 {len(rc)}개(고유 {len(set(rc))}), 평수운 미상 {len(miss)}: {miss}")
    return miss


def main():
    os.makedirs(OUT, exist_ok=True)
    rmap = build_rhyme_map()
    print(f"rhyme_map.tsv: {len(rmap)} (char,운목) 쌍, 고유 글자 {len({c for c,*_ in rmap})}")
    build_tongun()
    print("tongun.tsv 작성")
    heads = build_headwords()
    print(f"hdc_headwords.txt: {len(heads)} 표제어")
    verify(rmap)


if __name__ == "__main__":
    main()

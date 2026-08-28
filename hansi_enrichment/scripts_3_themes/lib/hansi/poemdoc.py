"""한시 태깅 XML 조각 파서.

입력 파일은 well-formed XML이 아님 (미이스케이프 &, 짝 안 맞는 태그, <D>..<D> 등).
따라서 정규식으로 <Poem ...>...</Poem> 블록 단위로만 다룬다.
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass

# 래퍼/선언 제거 대상
_WRAP_RE = re.compile(
    r"<\?xml[^>]*\?>"
    r"|</?hansi_Collection[^>]*>"
    r"|</?hansi>"
    r"|</?poems[^>]*>"
    r"|</?Corpus[^>]*>",
    re.I,
)
_POEM_SPLIT_RE = re.compile(r"(?=<Poem\b)", re.I)
_POEM_START_RE = re.compile(r"<Poem\b", re.I)
_POEM_CLOSE_RE = re.compile(r"</Poem\s*>", re.I)
_ID_RE = re.compile(r'<Poem\b[^>]*\bid\s*=\s*"([^"]*)"', re.I)

# 인라인 태그 소문자 통일 (구조 태그는 건드리지 않음)
_TAG_LOWER = {
    "Term": "term", "D": "d", "Rhyme": "rhyme",
    "term": "term", "d": "d", "rhyme": "rhyme",
}
_TAG_LOWER_RE = re.compile(r"</?(" + "|".join(sorted(set(_TAG_LOWER), key=len, reverse=True)) + r")(\s[^>]*)?>")


def _lower_inline(m: re.Match) -> str:
    slash = "/" if m.group(0)[1] == "/" else ""
    name = _TAG_LOWER.get(m.group(1), m.group(1))
    attrs = m.group(2) or ""
    return f"<{slash}{name}{attrs}>"


_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")


def normalize_text(text: str) -> str:
    """NFC 정규화 + 개행 LF + 인라인 태그 소문자 + 불량 유니코드 제거."""
    text = _SURROGATE_RE.sub("�", text)
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TAG_LOWER_RE.sub(_lower_inline, text)
    return text


def id_num(pid: str) -> int | None:
    """'P09883' -> 9883, 'P0195851' 같은 Line id는 대상 아님. 실패 시 None."""
    m = re.fullmatch(r"[Pp]?0*(\d+)", pid.strip())
    return int(m.group(1)) if m else None


@dataclass
class Poem:
    id: str
    num: int | None
    raw: str          # <Poem ...>...</Poem> 원문 (정규화 후)
    order: int        # 파일 내 등장 순서
    well_formed: bool = True   # 구조적으로 사용 가능 (복구 포함)
    repaired: bool = False     # </Poem> 누락을 복구함


def parse_poems(text: str) -> list[Poem]:
    text = normalize_text(text)
    text = _WRAP_RE.sub("", text)
    # <Poem 시작 위치마다 분할, 다음 <Poem 전까지가 한 덩어리
    chunks = _POEM_SPLIT_RE.split(text)
    out: list[Poem] = []
    i = 0
    for chunk in chunks:
        if not _POEM_START_RE.match(chunk.lstrip()[:6]) and not chunk.lstrip().lower().startswith("<poem"):
            continue
        cm = _POEM_CLOSE_RE.search(chunk)
        repaired = False
        if cm:
            block = chunk[: cm.end()]
            wf = True
        else:
            # </Poem> 누락 — 복구 시도
            tm = None
            for m2 in re.finditer(r"</text\s*>", chunk, re.I):
                tm = m2
            if tm:
                block = chunk[: tm.end()].rstrip() + "\n  </Poem>"
                wf = True
                repaired = True
            elif re.search(r"</Line\s*>|/>\s*</Line\s*>", chunk, re.I) and re.search(r"<text\b", chunk, re.I):
                # <Line> 다 있고 <text> 열림도 있는데 닫힘만 없음
                lm = None
                for m2 in re.finditer(r"</Line\s*>", chunk, re.I):
                    lm = m2
                block = chunk[: lm.end()].rstrip() + "\n    </text>\n  </Poem>"
                wf = True
                repaired = True
            else:
                block = chunk.rstrip()
                wf = False
        idm = _ID_RE.search(block)
        pid = idm.group(1).strip() if idm else f"__noid_{i}"
        out.append(Poem(id=pid, num=id_num(pid), raw=block.strip(), order=i,
                        well_formed=wf, repaired=repaired))
        i += 1
    return out


def wrap_corpus(poem_blocks: list[str]) -> str:
    body = "\n".join(poem_blocks)
    return f"<Corpus>\n{body}\n</Corpus>\n"

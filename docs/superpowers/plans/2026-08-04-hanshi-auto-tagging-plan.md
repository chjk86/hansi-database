# 한시 자동태깅 파이프라인 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 지천집(224수)을 대상으로, 임백호집_3차완본을 학습 예시로 삼아 형식(Form)·주제(Theme)·대장(Couplet)·시어(term/D)를 채우는 자동태깅 파이프라인을 만들고 파일럿 실행까지 완료한다.

**Architecture:** 사전(한어대사전) 기반 규칙 처리와 LLM 판단을 분리한 하이브리드 파이프라인. 시어 분절/term-D 재분류는 사전 최장일치로 우선 확정하고 애매한 구간만 시 1편당 1회 LLM 호출로 묶어서 처리한다. 형식·대장·주제는 해석적 판단이 필요해 규칙 힌트(구수, 제목 접미어, 제목 키워드)를 생성한 뒤 시 1편당 1회의 LLM 호출로 한꺼번에 확정한다(term/D 애매 구간 호출과 합쳐 시 1편당 최대 2회).

**Tech Stack:** Python 3.14, `anthropic` SDK (Claude API, 프롬프트 캐싱 사용), `pytest`, 표준 라이브러리 `xml.etree.ElementTree`.

## Global Constraints

- 원본 데이터(`extracted/`, `한어대사전.txt`, `임백호집_3차완본_20260730.txt`)는 절대 수정하지 않는다. 모든 산출물은 `output/`, `qa/`, `logs/`에 새로 쓴다.
- 전고(Allusion)는 이번 범위에서 완전히 제외한다 — few-shot 예시로 임백호집 시를 사용할 때도 `<Allusion>` 태그는 코드로 제거한 뒤 사용한다.
- 수운(sou-yun.cn) 아카이브는 사용하지 않는다 — term/D 판정은 `한어대사전.txt`만 근거로 한다.
- LLM 호출은 시 1편당 최대 2회(형식+대장+주제 통합 호출 1회, term/D 애매 구간 통합 호출 1회, 없으면 생략)로 제한한다. 여러 시를 한 호출에 묶지 않는다(응답 파싱 신뢰성 우선).
- 기본 모델은 `claude-haiku-4-5-20251001`. 환경변수 `HANSHI_LLM_MODEL`로 재정의 가능하게 한다.
- 모든 LLM 클라이언트는 인터페이스로 주입하여, 테스트에서는 네트워크 호출 없이 스텁으로 대체한다.

---

## 참고: 실측 데이터 포맷

구현 중 반드시 지켜야 할, 실제 파일에서 확인된 포맷 규칙:

- `한어대사전.txt`: 단일한자 항목은 `*<한자><숫자>［...` 형식(예: `*衣1［yīㄧ］...`), 복합어 항목은 `【<복합어>】...` 형식(예: `【草衣】①编草为衣...`). 항목 텍스트는 한 줄에 전체 정의가 들어있다.
- `태깅_XXX집.txt` (19개 문집 원본): `<Poem id="...">...</Poem>`가 연속으로 나열된 조각(fragment)이며 최상위 `<poems>` 루트나 XML 선언이 없다. `ns0:href` 속성을 쓰므로 파싱 시 `xmlns:ns0="http://www.w3.org/1999/xlink" xmlns:xlink="http://www.w3.org/1999/xlink"`를 선언하는 임시 루트로 감싸야 한다.
- 시어 태그는 `<term>`/`<d>` (소문자, 임백호집 3차완본 기준). 19개 원본 파일은 `<term>`만 있고 `<d>`가 없다.
- 숫자 문자 참조(`&#40603;` 등)가 본문에 존재 — `xml.etree.ElementTree`가 파싱 시 자동으로 유니코드 문자로 변환하므로 별도 처리 불필요.
- `임백호집_3차완본_20260730.txt`도 동일하게 루트 없는 fragment이며 `<Allusion .../>`, `<Couplet>...</Couplet>`, `<Theme category=... basis=... evidence=...>한글라벨</Theme>`, `<Title latent="...">` 를 포함한다.

---

## Task 1: 프로젝트 스캐폴딩

**Files:**
- Create: `hanshi-tagging/requirements.txt`
- Create: `hanshi-tagging/src/__init__.py`
- Create: `hanshi-tagging/src/config.py`
- Create: `hanshi-tagging/tests/__init__.py`
- Create: `hanshi-tagging/tests/test_config.py`
- Create: `hanshi-tagging/pytest.ini`

**Interfaces:**
- Produces: `config.py`의 `ROOT_DIR`, `DICT_PATH`, `GOLD_PATH`, `EXTRACTED_DIR`, `OUTPUT_DIR`, `QA_DIR`, `LOGS_DIR` (모두 `pathlib.Path`), `LLM_MODEL` (str, 환경변수 `HANSHI_LLM_MODEL` 우선, 기본값 `"claude-haiku-4-5-20251001"`).

- [ ] **Step 1: requirements.txt 작성**

```
anthropic>=0.40.0
pytest>=8.0.0
```

- [ ] **Step 2: 가상환경 생성 및 설치**

Run: `cd "C:\Users\user\Desktop\hanshi-tagging" && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt`

- [ ] **Step 3: 실패하는 테스트 작성**

`tests/test_config.py`:
```python
from pathlib import Path
from src import config


def test_paths_are_under_root():
    assert config.ROOT_DIR.is_dir()
    assert config.DICT_PATH == config.ROOT_DIR / "한어대사전.txt"
    assert config.GOLD_PATH == config.ROOT_DIR / "임백호집_3차완본_20260730.txt"
    assert config.OUTPUT_DIR == config.ROOT_DIR / "output"
    assert config.QA_DIR == config.ROOT_DIR / "qa"


def test_default_model_name():
    assert config.LLM_MODEL == "claude-haiku-4-5-20251001"
```

- [ ] **Step 4: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.config'` 또는 `src` 자체가 없음)

- [ ] **Step 5: config.py 구현**

```python
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DICT_PATH = ROOT_DIR / "한어대사전.txt"
GOLD_PATH = ROOT_DIR / "임백호집_3차완본_20260730.txt"
EXTRACTED_DIR = ROOT_DIR / "extracted" / "대상데이터_제목내용시어운자대장태그"
OUTPUT_DIR = ROOT_DIR / "output"
QA_DIR = ROOT_DIR / "qa"
LOGS_DIR = ROOT_DIR / "logs"
CACHE_DIR = ROOT_DIR / ".cache"

LLM_MODEL = os.environ.get("HANSHI_LLM_MODEL", "claude-haiku-4-5-20251001")
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: 커밋**

```bash
git add requirements.txt src/ tests/ pytest.ini
git commit -m "chore: scaffold project structure and config"
```

---

## Task 2: 한어대사전 인덱스

**Files:**
- Create: `src/dict_index.py`
- Create: `tests/fixtures/sample_dict.txt`
- Create: `tests/test_dict_index.py`

**Interfaces:**
- Produces: `DictIndex` 클래스 — `DictIndex.build(path: Path) -> "DictIndex"` (classmethod), `index.contains(word: str) -> bool`, `index.max_word_length -> int`, `index.save(cache_path: Path)`, `DictIndex.load(cache_path: Path) -> "DictIndex"`.

- [ ] **Step 1: 실제 데이터에서 뽑은 fixture 작성**

`tests/fixtures/sample_dict.txt` (한어대사전.txt에서 실제로 확인된 줄들을 그대로 복사):
```
*衣1［yīㄧ］［《廣韻》於希切，平微，影］①上衣。《诗·邶风·绿衣》：“綠衣黃裳。”
*衣2［yìㄧˋ］①穿(衣)。《书·畢命》：“惟公懋德，克勤小物，弼亮四世，正色率下，罔不祗師言，嘉績多于先王，予小子垂拱仰成。”
【草衣】①编草为衣。南朝齐萧子良《陈时政密启》之二：“民特尤貧，連年失稔，草衣藿食，稍有流亡。”
【長安】①古都城名。汉高祖七年(公元前200年)定都于此。
【一一】①逐一；一个一个地。《韩非子·內储说上》：“齊宣王使人吹竽，必三百人。”
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_dict_index.py`:
```python
from pathlib import Path
from src.dict_index import DictIndex

FIXTURE = Path(__file__).parent / "fixtures" / "sample_dict.txt"


def test_single_char_headword_registered():
    idx = DictIndex.build(FIXTURE)
    assert idx.contains("衣")


def test_multi_char_headword_registered():
    idx = DictIndex.build(FIXTURE)
    assert idx.contains("草衣")
    assert idx.contains("長安")
    assert idx.contains("一一")


def test_unregistered_word_not_found():
    idx = DictIndex.build(FIXTURE)
    assert not idx.contains("草木衣裳")
    assert not idx.contains("不存在")


def test_max_word_length_tracks_longest_entry():
    idx = DictIndex.build(FIXTURE)
    assert idx.max_word_length == 2  # "草衣", "長安", "一一" 모두 2글자


def test_save_and_load_roundtrip(tmp_path):
    idx = DictIndex.build(FIXTURE)
    cache_path = tmp_path / "dict_index.pkl"
    idx.save(cache_path)
    loaded = DictIndex.load(cache_path)
    assert loaded.contains("草衣")
    assert loaded.max_word_length == idx.max_word_length
```

- [ ] **Step 3: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_dict_index.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.dict_index'`)

- [ ] **Step 4: dict_index.py 구현**

```python
import pickle
import re
from pathlib import Path

_SINGLE_PATTERN = re.compile(r"^\*(.+?)\d*［")
_MULTI_PATTERN = re.compile(r"^【([^】]+)】")


class DictIndex:
    def __init__(self, headwords: set[str]):
        self._headwords = headwords
        self.max_word_length = max((len(w) for w in headwords), default=0)

    @classmethod
    def build(cls, path: Path) -> "DictIndex":
        headwords: set[str] = set()
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("*"):
                    m = _SINGLE_PATTERN.match(line)
                    if m:
                        headwords.add(m.group(1))
                elif line.startswith("【"):
                    m = _MULTI_PATTERN.match(line)
                    if m:
                        headwords.add(m.group(1))
        return cls(headwords)

    def contains(self, word: str) -> bool:
        return word in self._headwords

    def save(self, cache_path: Path) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(self._headwords, f)

    @classmethod
    def load(cls, cache_path: Path) -> "DictIndex":
        with open(cache_path, "rb") as f:
            headwords = pickle.load(f)
        return cls(headwords)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_dict_index.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: 실제 한어대사전.txt로 인덱스를 빌드하는 스크립트 작성**

`scripts/build_dict_index.py`:
```python
from src import config
from src.dict_index import DictIndex

if __name__ == "__main__":
    idx = DictIndex.build(config.DICT_PATH)
    cache_path = config.CACHE_DIR / "dict_index.pkl"
    idx.save(cache_path)
    print(f"headwords built, max_word_length={idx.max_word_length}, cached at {cache_path}")
```

- [ ] **Step 7: 실행해서 실제 규모 확인**

Run: `.venv\Scripts\python scripts\build_dict_index.py`
Expected: `headwords built, max_word_length=<17 근방>, cached at ...` 형태 출력. 표제어 총합이 대략 371,238개(27,991 단일자 + 343,247 복합어) 근방인지 눈으로 확인.

- [ ] **Step 8: 커밋**

```bash
git add src/dict_index.py scripts/build_dict_index.py tests/test_dict_index.py tests/fixtures/sample_dict.txt
git commit -m "feat: add Hanyu Da Cidian dictionary index"
```

---

## Task 3: Poem 데이터 모델 및 XML 파싱/쓰기

**Files:**
- Create: `src/poem_model.py`
- Create: `src/xml_io.py`
- Create: `tests/fixtures/sample_poems.txt`
- Create: `tests/test_xml_io.py`

**Interfaces:**
- Consumes: 없음 (최하위 계층)
- Produces: `poem_model.py`의 `Poem` dataclass (`id`, `title_xml: str`, `preface`, `annotation`, `collection_href`, `author_href`, `basetype`, `detailtype`, `charactercount`, `themes: list[ThemeTag]`, `context`, `lines: list[Line]`), `Line` dataclass (`id`, `order: int`, `content_xml: str`, `in_couplet: bool`), `ThemeTag` dataclass (`category`, `basis`, `evidence`, `label_ko`). `xml_io.py`의 `parse_collection(path: Path) -> list[Poem]`, `write_collection(path: Path, poems: list[Poem]) -> None`.

- [ ] **Step 1: fixture 작성 (지천집 실제 시 2편을 그대로 복사)**

`tests/fixtures/sample_poems.txt`:
```
  <Poem id="P19425">
    <Metadata>
      <Title>敬次<term>先祖</term><term>翼成</term>公寧越懸板韻</Title>
      <Preface></Preface>
      <Annotation></Annotation>
      <Collection ns0:href="glossary.xml#지천집"/>
      <Author ns0:href="glossary.xml#황정욱"/>
      <Form>
        <Basetype></Basetype>
        <Detailtype></Detailtype>
        <Charactercount>오언</Charactercount>
    </Form>
      <Themes>
        <Main></Main>
        <Sub></Sub>
      </Themes>
      <Context></Context>
    </Metadata>
    <text>
      <Line id="P1942501" order="1"><term>先祖</term><term>遺蹤</term>在</Line>
      <Line id="P1942502" order="2"><term>孤雲</term>獨倚<rhyme>天</rhyme></Line>
    </text>
  </Poem>
  <Poem id="P19426">
    <Metadata>
      <Title>山行</Title>
      <Preface></Preface>
      <Annotation></Annotation>
      <Collection ns0:href="glossary.xml#지천집"/>
      <Author ns0:href="glossary.xml#황정욱"/>
      <Form>
        <Basetype></Basetype>
        <Detailtype></Detailtype>
        <Charactercount>오언</Charactercount>
    </Form>
      <Themes>
        <Main></Main>
        <Sub></Sub>
      </Themes>
      <Context></Context>
    </Metadata>
    <text>
      <Line id="P1942601" order="1"><term>秋風</term>吹<term>古寺</term></Line>
      <Line id="P1942602" order="2"><term>木落</term>啼山<rhyme>雨</rhyme></Line>
    </text>
  </Poem>
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_xml_io.py`:
```python
from pathlib import Path
from src.xml_io import parse_collection, write_collection

FIXTURE = Path(__file__).parent / "fixtures" / "sample_poems.txt"


def test_parse_collection_reads_two_poems():
    poems = parse_collection(FIXTURE)
    assert len(poems) == 2
    assert poems[0].id == "P19425"
    assert poems[1].id == "P19426"


def test_parse_collection_reads_metadata():
    poems = parse_collection(FIXTURE)
    p = poems[0]
    assert p.collection_href == "glossary.xml#지천집"
    assert p.author_href == "glossary.xml#황정욱"
    assert p.charactercount == "오언"
    assert p.basetype == ""
    assert p.title_xml == "敬次<term>先祖</term><term>翼成</term>公寧越懸板韻"


def test_parse_collection_reads_lines():
    poems = parse_collection(FIXTURE)
    lines = poems[0].lines
    assert len(lines) == 2
    assert lines[0].order == 1
    assert lines[0].content_xml == "<term>先祖</term><term>遺蹤</term>在"
    assert lines[1].content_xml == "<term>孤雲</term>獨倚<rhyme>天</rhyme>"


def test_write_collection_roundtrips_and_fills_form(tmp_path):
    poems = parse_collection(FIXTURE)
    poems[0].basetype = "근체시"
    poems[0].detailtype = "절구"
    out_path = tmp_path / "out.xml"
    write_collection(out_path, poems)

    reparsed = parse_collection(out_path)
    assert reparsed[0].basetype == "근체시"
    assert reparsed[0].detailtype == "절구"
    assert reparsed[1].id == "P19426"


def test_write_collection_is_well_formed_xml(tmp_path):
    import xml.etree.ElementTree as ET

    poems = parse_collection(FIXTURE)
    out_path = tmp_path / "out.xml"
    write_collection(out_path, poems)
    ET.parse(out_path)  # raises ParseError if malformed
```

- [ ] **Step 3: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_xml_io.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 4: poem_model.py 구현**

```python
from dataclasses import dataclass, field


@dataclass
class ThemeTag:
    category: str
    basis: str
    evidence: str
    label_ko: str


@dataclass
class Line:
    id: str
    order: int
    content_xml: str
    in_couplet: bool = False


@dataclass
class Poem:
    id: str
    title_xml: str = ""
    preface: str = ""
    annotation: str = ""
    collection_href: str = ""
    author_href: str = ""
    basetype: str = ""
    detailtype: str = ""
    charactercount: str = ""
    context: str = ""
    themes: list[ThemeTag] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
```

주석: `content_xml`/`title_xml`은 `<term>`/`<d>`/`<rhyme>` 하위 태그를 문자열 그대로 보존한다. 이후 단계(term_classify, couplet)에서 이 문자열을 다시 파싱·재작성한다.

- [ ] **Step 5: xml_io.py 구현**

```python
import xml.etree.ElementTree as ET
from pathlib import Path

from .poem_model import Line, Poem, ThemeTag

_NS_WRAPPER_OPEN = (
    '<root xmlns:ns0="http://www.w3.org/1999/xlink" '
    'xmlns:xlink="http://www.w3.org/1999/xlink">'
)
_NS_WRAPPER_CLOSE = "</root>"
_HREF_ATTR = "{http://www.w3.org/1999/xlink}href"


def _inner_xml(elem: ET.Element) -> str:
    """자식 요소 전체를 문자열로 직렬화 (elem 자신의 태그는 제외)."""
    text = elem.text or ""
    for child in elem:
        text += ET.tostring(child, encoding="unicode")
    return text


def _wrap_and_parse(path: Path) -> ET.Element:
    raw = path.read_text(encoding="utf-8")
    wrapped = _NS_WRAPPER_OPEN + raw + _NS_WRAPPER_CLOSE
    return ET.fromstring(wrapped)


def parse_collection(path: Path) -> list[Poem]:
    root = _wrap_and_parse(path)
    poems = []
    for poem_el in root.findall("Poem"):
        meta = poem_el.find("Metadata")
        form = meta.find("Form")
        collection_el = meta.find("Collection")
        author_el = meta.find("Author")

        lines = []
        for line_el in poem_el.find("text").findall("Line"):
            lines.append(
                Line(
                    id=line_el.get("id"),
                    order=int(line_el.get("order")),
                    content_xml=_inner_xml(line_el),
                )
            )

        themes = []
        for theme_el in meta.find("Themes").findall("Theme"):
            themes.append(
                ThemeTag(
                    category=theme_el.get("category", ""),
                    basis=theme_el.get("basis", ""),
                    evidence=theme_el.get("evidence", ""),
                    label_ko=theme_el.text or "",
                )
            )

        poems.append(
            Poem(
                id=poem_el.get("id"),
                title_xml=_inner_xml(meta.find("Title")),
                preface=meta.find("Preface").text or "",
                annotation=meta.find("Annotation").text or "",
                collection_href=collection_el.get(_HREF_ATTR, "") if collection_el is not None else "",
                author_href=author_el.get(_HREF_ATTR, "") if author_el is not None else "",
                basetype=(form.find("Basetype").text or "") if form is not None else "",
                detailtype=(form.find("Detailtype").text or "") if form is not None else "",
                charactercount=(form.find("Charactercount").text or "") if form is not None else "",
                context=meta.find("Context").text or "",
                themes=themes,
                lines=lines,
            )
        )
    return poems


def _poem_to_xml(poem: Poem) -> str:
    theme_xml = "".join(
        f'<Theme category="{t.category}" basis="{t.basis}" evidence="{t.evidence}">{t.label_ko}</Theme>'
        for t in poem.themes
    )
    lines_xml = "".join(
        f'<Line id="{ln.id}" order="{ln.order}">{ln.content_xml}</Line>' for ln in poem.lines
    )
    return (
        f'<Poem id="{poem.id}">'
        f"<Metadata>"
        f"<Title>{poem.title_xml}</Title>"
        f"<Preface>{poem.preface}</Preface>"
        f"<Annotation>{poem.annotation}</Annotation>"
        f'<Collection ns0:href="{poem.collection_href}"/>'
        f'<Author ns0:href="{poem.author_href}"/>'
        f"<Form>"
        f"<Basetype>{poem.basetype}</Basetype>"
        f"<Detailtype>{poem.detailtype}</Detailtype>"
        f"<Charactercount>{poem.charactercount}</Charactercount>"
        f"</Form>"
        f"<Themes>{theme_xml}</Themes>"
        f"<Context>{poem.context}</Context>"
        f"</Metadata>"
        f"<text>{lines_xml}</text>"
        f"</Poem>"
    )


def write_collection(path: Path, poems: list[Poem]) -> None:
    body = "".join(_poem_to_xml(p) for p in poems)
    document = (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<poems xmlns:ns0="http://www.w3.org/1999/xlink" '
        'xmlns:xlink="http://www.w3.org/1999/xlink">'
        f"{body}"
        "</poems>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
```

주의: `Couplet`으로 감싸인 `Line`은 이 시점(Task 3)에서는 다루지 않는다 — Couplet 배치는 Task 8에서 별도로 `content_xml`이 아닌 poem 직렬화 단계에 개입하므로, Task 8에서 `_poem_to_xml`의 `lines_xml` 생성 부분을 수정한다(아래 Task 8 Step 참고).

- [ ] **Step 6: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_xml_io.py -v`
Expected: PASS (5 passed)

- [ ] **Step 7: 커밋**

```bash
git add src/poem_model.py src/xml_io.py tests/test_xml_io.py tests/fixtures/sample_poems.txt
git commit -m "feat: add Poem model and XML parse/write"
```

---

## Task 4: 시구 분절 (사전 최장일치)

**Files:**
- Create: `src/segment.py`
- Create: `tests/test_segment.py`

**Interfaces:**
- Consumes: `DictIndex.contains(word: str) -> bool`, `DictIndex.max_word_length: int` (Task 2)
- Produces: `SpanCandidate` dataclass (`start: int`, `end: int`, `text: str`, `in_dict: bool`), `generate_candidates(plain_text: str, hint_start: int, hint_end: int, dict_index: DictIndex) -> list[SpanCandidate]` — `hint_start`/`hint_end`는 기존 `<term>` 태깅 위치(문자 인덱스, 원본 시구의 순수 텍스트 기준)를 참고 힌트로 받아 그 주변(±2자)에서 사전에 등재된 가장 긴 조합을 우선순위로 후보를 생성한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_segment.py`:
```python
from src.dict_index import DictIndex
from src.segment import generate_candidates

WORDS = {"草衣", "長安", "先祖", "遺蹤", "衣", "先", "祖"}


def _idx():
    return DictIndex(set(WORDS))


def test_exact_hint_match_returns_single_high_confidence_candidate():
    # 시구 "先祖遺蹤在" 중 힌트가 가리키는 0-2("先祖")가 사전에 등재
    cands = generate_candidates("先祖遺蹤在", hint_start=0, hint_end=2, dict_index=_idx())
    assert len(cands) == 1
    assert cands[0].text == "先祖"
    assert cands[0].in_dict is True


def test_hint_boundary_off_by_one_is_corrected_by_dictionary():
    # 힌트가 "先祖遺"(0-3)로 잘못 잡혀 있어도 사전에 없는 3자 조합이므로
    # 사전에 있는 2자 조합("先祖")을 후보로 우선 제안해야 한다
    cands = generate_candidates("先祖遺蹤在", hint_start=0, hint_end=3, dict_index=_idx())
    texts = [c.text for c in cands if c.in_dict]
    assert "先祖" in texts


def test_no_dictionary_match_yields_out_of_dict_candidate():
    idx = DictIndex(set())  # 빈 사전
    cands = generate_candidates("先祖遺蹤在", hint_start=0, hint_end=2, dict_index=idx)
    assert len(cands) == 1
    assert cands[0].text == "先祖"
    assert cands[0].in_dict is False
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_segment.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: segment.py 구현**

```python
from dataclasses import dataclass

from .dict_index import DictIndex


@dataclass
class SpanCandidate:
    start: int
    end: int
    text: str
    in_dict: bool


def generate_candidates(
    plain_text: str, hint_start: int, hint_end: int, dict_index: DictIndex
) -> list[SpanCandidate]:
    """hint 주변(±2자)에서 사전 등재 여부를 기준으로 경계 후보를 생성한다.

    사전에 등재된 조합 중 가장 긴 것을 우선하고, 등재된 조합이 전혀 없으면
    원래 힌트 그대로를 사전 미등재(in_dict=False) 후보로 반환한다.
    """
    search_start = max(0, hint_start - 2)
    search_end = min(len(plain_text), hint_end + 2)

    dict_hits: list[SpanCandidate] = []
    for start in range(search_start, search_end):
        max_len = min(dict_index.max_word_length, search_end - start)
        for length in range(max_len, 1, -1):  # 1글자 표제어는 시어 태깅 대상이 아니므로 제외
            end = start + length
            candidate_text = plain_text[start:end]
            if dict_index.contains(candidate_text):
                dict_hits.append(SpanCandidate(start, end, candidate_text, True))

    # 원래 힌트 구간과 겹치는 사전 히트만 채택 (완전히 무관한 위치의 우연한 매칭 배제)
    overlapping = [
        c for c in dict_hits if not (c.end <= hint_start or c.start >= hint_end)
    ]
    if overlapping:
        overlapping.sort(key=lambda c: (-(c.end - c.start), c.start))
        return overlapping

    return [
        SpanCandidate(hint_start, hint_end, plain_text[hint_start:hint_end], False)
    ]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_segment.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/segment.py tests/test_segment.py
git commit -m "feat: add dictionary-based span candidate generation"
```

---

## Task 5: LLM 클라이언트 래퍼

**Files:**
- Create: `src/llm_client.py`
- Create: `tests/test_llm_client.py`

**Interfaces:**
- Produces: `LLMClient` 프로토콜(추상 인터페이스) — `complete(system: str, user: str, response_schema: dict) -> dict`. `AnthropicLLMClient(model: str, api_key: str | None = None)` 구현체 — 내부적으로 재시도(지수 백오프, 최대 3회)와 JSON 파싱을 수행. `FakeLLMClient(responses: list[dict])` — 테스트용, 호출 순서대로 미리 지정된 dict를 반환하고 호출 인자를 기록.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_llm_client.py`:
```python
import pytest

from src.llm_client import FakeLLMClient, RetryExhaustedError


def test_fake_client_returns_queued_responses_in_order():
    client = FakeLLMClient(responses=[{"a": 1}, {"a": 2}])
    assert client.complete("sys", "user1", {}) == {"a": 1}
    assert client.complete("sys", "user2", {}) == {"a": 2}


def test_fake_client_records_calls():
    client = FakeLLMClient(responses=[{"a": 1}])
    client.complete("sys-prompt", "user-prompt", {"type": "object"})
    assert client.calls[0]["system"] == "sys-prompt"
    assert client.calls[0]["user"] == "user-prompt"


def test_fake_client_raises_when_responses_exhausted():
    client = FakeLLMClient(responses=[])
    with pytest.raises(RetryExhaustedError):
        client.complete("sys", "user", {})
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_llm_client.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: llm_client.py 구현**

```python
import json
import os
import time
from typing import Protocol


class RetryExhaustedError(Exception):
    pass


class LLMClient(Protocol):
    def complete(self, system: str, user: str, response_schema: dict) -> dict: ...


class FakeLLMClient:
    """테스트용 스텁. 실제 네트워크 호출 없이 미리 지정된 응답을 순서대로 반환한다."""

    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def complete(self, system: str, user: str, response_schema: dict) -> dict:
        self.calls.append({"system": system, "user": user, "schema": response_schema})
        if not self._responses:
            raise RetryExhaustedError("no more queued fake responses")
        return self._responses.pop(0)


class AnthropicLLMClient:
    """실제 Claude API 호출. 프롬프트 캐싱과 지수 백오프 재시도를 포함한다."""

    def __init__(self, model: str, api_key: str | None = None, max_retries: int = 3):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self._model = model
        self._max_retries = max_retries

    def complete(self, system: str, user: str, response_schema: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=2048,
                    system=[
                        {
                            "type": "text",
                            "text": system,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[{"role": "user", "content": user}],
                    tools=[
                        {
                            "name": "submit_result",
                            "description": "구조화된 태깅 결과를 제출한다.",
                            "input_schema": response_schema,
                        }
                    ],
                    tool_choice={"type": "tool", "name": "submit_result"},
                )
                for block in response.content:
                    if block.type == "tool_use":
                        return block.input
                raise ValueError("no tool_use block in response")
            except Exception as exc:  # noqa: BLE001 - 재시도 대상 예외를 폭넓게 포착
                last_error = exc
                if attempt < self._max_retries - 1:
                    time.sleep(2**attempt)
        raise RetryExhaustedError(f"LLM call failed after {self._max_retries} attempts: {last_error}")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_llm_client.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/llm_client.py tests/test_llm_client.py
git commit -m "feat: add LLM client wrapper with fake stub for tests"
```

---

## Task 6: term/D 분류 (사전 확정 + 애매 구간 LLM)

**Files:**
- Create: `src/term_classify.py`
- Create: `tests/test_term_classify.py`

**Interfaces:**
- Consumes: `Poem`/`Line` (Task 3), `generate_candidates` (Task 4), `LLMClient.complete` (Task 5)
- Produces: `classify_poem_terms(poem: Poem, dict_index: DictIndex, llm_client: LLMClient) -> tuple[Poem, list[dict]]` — 반환된 `Poem`은 각 `Line.content_xml`이 `<term>`/`<d>`로 재태깅된 상태. 두 번째 반환값은 QA 로그용 플래그 리스트(`{"poem_id", "line_id", "reason"}`).
- 매뉴얼 규칙(부정어 처리 등)을 요약한 시스템 프롬프트 상수 `TERM_CLASSIFY_SYSTEM_PROMPT`를 이 파일에 정의한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_term_classify.py`:
```python
from src.dict_index import DictIndex
from src.llm_client import FakeLLMClient
from src.poem_model import Line, Poem
from src.term_classify import classify_poem_terms

WORDS = {"先祖", "遺蹤", "草衣", "重雲"}


def _idx():
    return DictIndex(set(WORDS))


def test_dict_confirmed_span_becomes_term_without_llm_call():
    poem = Poem(
        id="P1",
        lines=[Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在")],
    )
    llm = FakeLLMClient(responses=[])  # 호출되면 즉시 예외 -> 호출 안 됨을 검증

    result, flags = classify_poem_terms(poem, _idx(), llm)

    assert result.lines[0].content_xml == "<term>先祖</term>遺蹤在"
    assert llm.calls == []


def test_dict_unregistered_span_becomes_d_without_llm_call():
    poem = Poem(
        id="P1",
        lines=[Line(id="L1", order=1, content_xml="<term>重雲</term>濕草衣")],
    )
    idx = DictIndex({"重雲"} - {"重雲"})  # 빈 사전 -> 미등재
    llm = FakeLLMClient(responses=[])

    result, flags = classify_poem_terms(poem, idx, llm)

    assert result.lines[0].content_xml == "<d>重雲</d>濕草衣"
    assert llm.calls == []


def test_ambiguous_span_is_resolved_via_single_llm_call_per_poem():
    poem = Poem(
        id="P1",
        lines=[
            Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在"),
            Line(id="L2", order=2, content_xml="<term>重雲</term>濕草衣"),
        ],
    )
    # "先祖"는 힌트와 정확히 일치하는 사전 후보가 없어 애매 -> LLM이 "先"만 term으로 판단
    idx = DictIndex({"先", "草衣"})
    llm = FakeLLMClient(
        responses=[
            {
                "resolved_spans": [
                    {"line_id": "L1", "start": 0, "end": 1, "text": "先", "label": "term"},
                ]
            }
        ]
    )

    result, flags = classify_poem_terms(poem, idx, llm)

    assert len(llm.calls) == 1  # 시 1편당 1회로 묶임
    assert "<term>先</term>" in result.lines[0].content_xml
    assert any(f["poem_id"] == "P1" for f in flags)
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_term_classify.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: term_classify.py 구현**

```python
import re

from .dict_index import DictIndex
from .llm_client import LLMClient
from .poem_model import Line, Poem
from .segment import generate_candidates

_TAG_PATTERN = re.compile(r"<(term|d)>(.*?)</\1>", re.DOTALL)

TERM_CLASSIFY_SYSTEM_PROMPT = """\
당신은 한국 한시 시어(詩語) 태깅 전문가입니다. 아래 규칙을 따라 애매한 시어 구간의
정확한 경계와 term/D 여부를 판정하세요.

- term: 『한어대사전』에 등재된 시어. D: 등재되지 않았지만 분석상 의미 있는 어휘.
- 부정어 처리: 無消息, 無情처럼 상태·정서를 구체화하거나 不同처럼 반대 뜻으로 굳어진
  경우는 태깅하되, 不敢·不能처럼 단순 조동사·기능어인 경우는 태깅하지 않습니다.
- 3자 시어(안긴 어휘)는 수식어 없이 의미가 급변하거나 고유한 어휘로 쓰일 때만 묶습니다.
- 반드시 원문 글자를 그대로 사용하고, 새로운 글자를 만들어내지 않습니다.
"""


def _strip_tags(content_xml: str) -> str:
    return _TAG_PATTERN.sub(lambda m: m.group(2), content_xml)


def _existing_hint(content_xml: str) -> tuple[int, int] | None:
    """content_xml 안의 첫 <term> 태그 위치를 순수 텍스트 기준 (start, end)로 반환."""
    plain = _strip_tags(content_xml)
    m = _TAG_PATTERN.search(content_xml)
    if not m:
        return None
    prefix_plain = _strip_tags(content_xml[: m.start()])
    start = len(prefix_plain)
    end = start + len(m.group(2))
    return start, end, plain


def _rebuild_line(plain: str, spans: list[tuple[int, int, str]]) -> str:
    """spans: (start, end, label) 정렬된 리스트. 겹치지 않는다고 가정."""
    spans = sorted(spans, key=lambda s: s[0])
    out = []
    cursor = 0
    for start, end, label in spans:
        out.append(plain[cursor:start])
        out.append(f"<{label}>{plain[start:end]}</{label}>")
        cursor = end
    out.append(plain[cursor:])
    return "".join(out)


def classify_poem_terms(
    poem: Poem, dict_index: DictIndex, llm_client: LLMClient
) -> tuple[Poem, list[dict]]:
    flags: list[dict] = []
    confirmed_spans: dict[str, list[tuple[int, int, str]]] = {}
    ambiguous_requests = []

    for line in poem.lines:
        hint = _existing_hint(line.content_xml)
        if hint is None:
            confirmed_spans[line.id] = []
            continue
        hint_start, hint_end, plain = hint
        candidates = generate_candidates(plain, hint_start, hint_end, dict_index)

        if len(candidates) == 1:
            c = candidates[0]
            label = "term" if c.in_dict else "d"
            confirmed_spans[line.id] = [(c.start, c.end, label)]
        else:
            ambiguous_requests.append(
                {
                    "line_id": line.id,
                    "plain_text": plain,
                    "candidates": [
                        {"start": c.start, "end": c.end, "text": c.text, "in_dict": c.in_dict}
                        for c in candidates
                    ],
                }
            )
            confirmed_spans[line.id] = []  # LLM 응답으로 채워질 예정

    if ambiguous_requests:
        user_prompt = (
            "다음 시구들의 애매한 시어 구간을 판정해 resolved_spans로 반환하세요.\n"
            f"{ambiguous_requests}"
        )
        schema = {
            "type": "object",
            "properties": {
                "resolved_spans": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line_id": {"type": "string"},
                            "start": {"type": "integer"},
                            "end": {"type": "integer"},
                            "text": {"type": "string"},
                            "label": {"type": "string", "enum": ["term", "d"]},
                        },
                        "required": ["line_id", "start", "end", "text", "label"],
                    },
                }
            },
            "required": ["resolved_spans"],
        }
        response = llm_client.complete(TERM_CLASSIFY_SYSTEM_PROMPT, user_prompt, schema)
        for span in response["resolved_spans"]:
            confirmed_spans[span["line_id"]].append((span["start"], span["end"], span["label"]))
            flags.append(
                {
                    "poem_id": poem.id,
                    "item": "term/D",
                    "reason": f"{span['line_id']}: term/D 분절 LLM 판정",
                }
            )

    new_lines = []
    for line in poem.lines:
        hint = _existing_hint(line.content_xml)
        if hint is None:
            new_lines.append(line)
            continue
        _, _, plain = hint
        new_content = _rebuild_line(plain, confirmed_spans[line.id])
        new_lines.append(Line(id=line.id, order=line.order, content_xml=new_content))

    poem.lines = new_lines
    return poem, flags
```

주석: 현재 fixture/manual 예시는 시구당 `<term>`이 1개인 단순 케이스만 다룬다. 실제 지천집 데이터에는 한 시구에 `<term>`이 여러 개 있는 경우가 흔하므로(Task 13 파일럿에서 실측 확인), `_existing_hint`가 첫 태그만 처리하는 이 구현은 **다중 태그 케이스를 처리하도록 Task 13에서 실데이터로 확장**한다. Task 6에서는 단일 태그 케이스의 정확성을 먼저 확보한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_term_classify.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/term_classify.py tests/test_term_classify.py
git commit -m "feat: classify term/D spans via dictionary with LLM fallback for ambiguous cases"
```

---

## Task 7: Form/Couplet/Theme 통합 LLM 분류

**Files:**
- Create: `src/interpretive_classify.py`
- Create: `tests/test_interpretive_classify.py`

**Interfaces:**
- Consumes: `Poem` (Task 3), `LLMClient.complete` (Task 5)
- Produces: `classify_form_couplet_theme(poem: Poem, llm_client: LLMClient) -> tuple[Poem, list[dict]]` — `Poem.basetype`/`detailtype`/`themes`를 채우고, `Poem.lines`의 `in_couplet` 플래그를 설정한다. 두 번째 반환값은 QA 로그 플래그.
- `THEME_CATEGORIES` 상수: 매뉴얼의 24개 카테고리 표를 `{"mountain": ("산악", ["山", "石", "登", "望"]), ...}` 형태로 정의.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_interpretive_classify.py`:
```python
from src.llm_client import FakeLLMClient
from src.poem_model import Line, Poem
from src.interpretive_classify import classify_form_couplet_theme


def _quatrain():
    return Poem(
        id="P1",
        title_xml="贈<d>眞鑑</d>",
        lines=[
            Line(id="L1", order=1, content_xml="夜伴<term>林僧</term>宿"),
            Line(id="L2", order=2, content_xml="<d>重雲</d>濕<term>草衣</term>"),
            Line(id="L3", order=3, content_xml="<term>巖扉</term>開<term>晩日</term>"),
            Line(id="L4", order=4, content_xml="<d>棲鳥</d>始<term>驚飛</term>"),
        ],
        charactercount="오언",
    )


def test_quatrain_gets_basetype_and_detailtype_from_llm():
    llm = FakeLLMClient(
        responses=[
            {
                "basetype": "근체시",
                "detailtype": "절구",
                "couplets": [],
                "themes": [
                    {"category": "donate", "basis": "title", "evidence": "贈", "label_ko": "기증"},
                    {
                        "category": "buddhism",
                        "basis": "term",
                        "evidence": "林僧 草衣",
                        "label_ko": "불교",
                    },
                ],
            }
        ]
    )

    result, flags = classify_form_couplet_theme(_quatrain(), llm)

    assert result.basetype == "근체시"
    assert result.detailtype == "절구"
    assert len(result.themes) == 2
    assert result.themes[0].category == "donate"


def test_couplet_flags_are_applied_to_matching_lines():
    poem = Poem(
        id="P2",
        title_xml="題",
        lines=[Line(id=f"L{i}", order=i, content_xml="字字字") for i in range(1, 9)],
        charactercount="오언",
    )
    llm = FakeLLMClient(
        responses=[
            {
                "basetype": "근체시",
                "detailtype": "율시",
                "couplets": [[5, 6]],
                "themes": [],
            }
        ]
    )

    result, flags = classify_form_couplet_theme(poem, llm)

    in_couplet_orders = [ln.order for ln in result.lines if ln.in_couplet]
    assert in_couplet_orders == [5, 6]


def test_evidence_not_found_in_poem_text_is_flagged_and_dropped():
    llm = FakeLLMClient(
        responses=[
            {
                "basetype": "근체시",
                "detailtype": "절구",
                "couplets": [],
                "themes": [
                    {
                        "category": "farewell",
                        "basis": "term",
                        "evidence": "존재하지않는단어",
                        "label_ko": "송별",
                    }
                ],
            }
        ]
    )

    result, flags = classify_form_couplet_theme(_quatrain(), llm)

    assert result.themes == []  # 근거 없는 Theme는 채택하지 않음
    assert any(f["item"] == "Theme" and "환각 의심" in f["reason"] for f in flags)
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_interpretive_classify.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: interpretive_classify.py 구현**

```python
import re

from .llm_client import LLMClient
from .poem_model import Poem, ThemeTag

_TAG_STRIP = re.compile(r"</?(term|d|rhyme)>")

THEME_CATEGORIES = {
    "mountain": ("산악", ["山", "石", "登", "望", "觀"]),
    "water": ("강해", ["水", "海", "湖", "川", "浦"]),
    "astro": ("천문", ["日", "月", "星", "雷", "雨", "雪", "風"]),
    "season": ("계절", ["節", "春", "夏", "秋", "冬"]),
    "animal": ("동물", ["禽", "獸", "鱗", "蟲"]),
    "plant": ("식물", ["花", "樹", "菓", "草"]),
    "travel": ("유람", ["遊", "過", "行", "宿"]),
    "donate": ("기증", ["贈", "答", "和"]),
    "farewell": ("송별", ["送", "別", "留別"]),
    "meet": ("회방", ["訪", "會", "見"]),
    "sympathy": ("애상", ["挽", "恨", "哀悼", "弔古"]),
    "reminiscence": ("회고", ["懷", "憶", "追"]),
    "frontier": ("변새", ["邊", "塞"]),
    "desire": ("염정", ["閨怨", "宮詞"]),
    "dream": ("기몽", ["夢"]),
    "prosper": ("현달", ["慶", "賀", "喜"]),
    "tranquility": ("한적", ["閑", "居", "退"]),
    "banquet": ("연회", ["宴", "樂", "曲", "茶酒"]),
    "person": ("인물", ["人物", "漁釣", "豪俠"]),
    "taoism": ("도교", ["仙", "道"]),
    "buddhism": ("불교", ["釋", "佛", "寺刹", "僧"]),
    "structure": ("건물", ["樓", "亭", "臺", "閣", "堂"]),
    "object": ("기용", ["器"]),
    "literature": ("문방", ["文", "讀", "觀"]),
    "picture": ("도화", ["畵", "圖", "題畵"]),
    "others": ("기타", []),
}

SYSTEM_PROMPT = """\
당신은 한국 한시 태깅 전문가입니다. 시 한 편을 보고 아래 세 가지를 판정해
submit_result 도구로 제출하세요.

1. 형식(basetype/detailtype)
   - 근체시: 절구(4구)·율시(8구)·배율(8구 초과)
   - 고체시: 고시·악부·사(詞)·사(辭)·부(賦)·잡체시(雜體詩)·과체시(科體詩)
   - 제목이 '~歌', '~行', '~引', '~謠'로 끝나면 고체시(악부/고시)일 가능성이 높습니다.

2. 대장(couplets): 근체시의 중간 구-쌍(절구 제외) 중 실제로 문법·의미가
   대응하는 경우만 [상구번호, 하구번호]로 나열하세요. 위치상 대장이 가능해
   보여도 실제 대응이 약하면 포함하지 마세요. 절구는 항상 빈 리스트입니다.

3. 주제(themes): 아래 24개 카테고리 중 해당하는 것을 다중 선택하세요.
   각 항목은 category(영문 코드), basis(title/term/title, term), evidence(제목
   또는 시어에서 실제로 등장하는 글자 그대로), label_ko(한글 라벨)를 포함합니다.
   evidence는 반드시 시의 제목 또는 본문에 실제로 나오는 글자만 사용하세요.
   카테고리 표: {categories}
""".format(
    categories=", ".join(f"{k}({v[0]})" for k, v in THEME_CATEGORIES.items())
)

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "basetype": {"type": "string", "enum": ["근체시", "고체시"]},
        "detailtype": {"type": "string"},
        "couplets": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
        },
        "themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "basis": {"type": "string"},
                    "evidence": {"type": "string"},
                    "label_ko": {"type": "string"},
                },
                "required": ["category", "basis", "evidence", "label_ko"],
            },
        },
    },
    "required": ["basetype", "detailtype", "couplets", "themes"],
}


def _plain(xml_fragment: str) -> str:
    return _TAG_STRIP.sub("", xml_fragment)


def _evidence_exists_in_poem(evidence: str, poem_plain_text: str) -> bool:
    tokens = evidence.replace(",", " ").split()
    return all(token in poem_plain_text for token in tokens)


def classify_form_couplet_theme(poem: Poem, llm_client: LLMClient) -> tuple[Poem, list[dict]]:
    flags: list[dict] = []
    title_plain = _plain(poem.title_xml)
    body_plain = "".join(_plain(ln.content_xml) for ln in poem.lines)
    full_text = title_plain + body_plain

    user_prompt = (
        f"제목: {title_plain}\n"
        f"자수: {poem.charactercount}\n"
        f"구수: {len(poem.lines)}\n"
        "본문:\n" + "\n".join(f"{ln.order}구: {_plain(ln.content_xml)}" for ln in poem.lines)
    )

    result = llm_client.complete(SYSTEM_PROMPT, user_prompt, _RESPONSE_SCHEMA)

    poem.basetype = result["basetype"]
    poem.detailtype = result["detailtype"]

    couplet_orders = {order for pair in result["couplets"] for order in pair}
    for line in poem.lines:
        line.in_couplet = line.order in couplet_orders

    accepted_themes = []
    for theme in result["themes"]:
        if _evidence_exists_in_poem(theme["evidence"], full_text):
            accepted_themes.append(
                ThemeTag(
                    category=theme["category"],
                    basis=theme["basis"],
                    evidence=theme["evidence"],
                    label_ko=theme["label_ko"],
                )
            )
        else:
            flags.append(
                {
                    "poem_id": poem.id,
                    "item": "Theme",
                    "reason": f"evidence 미검증(환각 의심): {theme['evidence']}",
                }
            )
    poem.themes = accepted_themes

    return poem, flags
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_interpretive_classify.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/interpretive_classify.py tests/test_interpretive_classify.py
git commit -m "feat: classify Form/Couplet/Theme via single combined LLM call"
```

---

## Task 8: Couplet 직렬화 반영

**Files:**
- Modify: `src/xml_io.py:_poem_to_xml` (Task 3에서 작성한 함수)
- Modify: `tests/test_xml_io.py`

**Interfaces:**
- Consumes: `Line.in_couplet` (Task 7이 설정)
- Produces: `write_collection`이 `in_couplet=True`인 인접 `Line` 쌍을 `<Couplet>...</Couplet>`으로 감싸 출력.

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_xml_io.py`에 추가:
```python
def test_write_collection_wraps_couplet_lines(tmp_path):
    from src.poem_model import Line, Poem

    poem = Poem(
        id="P1",
        lines=[
            Line(id="L1", order=1, content_xml="字"),
            Line(id="L2", order=2, content_xml="字", ),
            Line(id="L3", order=3, content_xml="字", in_couplet=True),
            Line(id="L4", order=4, content_xml="字", in_couplet=True),
        ],
    )
    out_path = tmp_path / "out.xml"
    write_collection(out_path, [poem])
    raw = out_path.read_text(encoding="utf-8")

    assert "<Couplet>" in raw
    assert raw.index("<Couplet>") < raw.index('id="L3"')
    assert raw.index("</Couplet>") > raw.index('id="L4"')
    assert raw.count("<Couplet>") == 1
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_xml_io.py -v`
Expected: FAIL (아직 `<Couplet>` 출력 안 함)

- [ ] **Step 3: `_poem_to_xml`의 lines_xml 생성부 수정**

`src/xml_io.py`에서 `_poem_to_xml` 내부의 `lines_xml = "".join(...)` 줄을 아래 헬퍼 호출로 교체:

```python
def _lines_to_xml(lines: list) -> str:
    out = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.in_couplet and i + 1 < len(lines) and lines[i + 1].in_couplet:
            partner = lines[i + 1]
            out.append(
                f'<Couplet><Line id="{ln.id}" order="{ln.order}">{ln.content_xml}</Line>'
                f'<Line id="{partner.id}" order="{partner.order}">{partner.content_xml}</Line></Couplet>'
            )
            i += 2
        else:
            out.append(f'<Line id="{ln.id}" order="{ln.order}">{ln.content_xml}</Line>')
            i += 1
    return "".join(out)
```

그리고 `_poem_to_xml` 안의 `lines_xml = "".join(...)`을 `lines_xml = _lines_to_xml(poem.lines)`로 교체한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_xml_io.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/xml_io.py tests/test_xml_io.py
git commit -m "feat: serialize Couplet-wrapped line pairs on write"
```

---

## Task 9: 검증 (validate.py)

**Files:**
- Create: `src/validate.py`
- Create: `tests/test_validate.py`

**Interfaces:**
- Consumes: `Poem` (Task 3)
- Produces: `validate_poem(poem: Poem, original_plain_lookup: dict[str, str]) -> list[str]` — 위반 사항 문자열 리스트(빈 리스트면 통과). `original_plain_lookup`은 `{line_id: 원본_순수_텍스트}` — term/D 재태깅이 원문 글자를 훼손하지 않았는지 대조하는 데 쓰인다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_validate.py`:
```python
from src.poem_model import Line, Poem, ThemeTag
from src.validate import validate_poem


def test_valid_poem_has_no_issues():
    poem = Poem(
        id="P1",
        title_xml="題",
        lines=[Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在")],
        themes=[ThemeTag(category="donate", basis="title", evidence="題", label_ko="기증")],
    )
    issues = validate_poem(poem, original_plain_lookup={"L1": "先祖遺蹤在"})
    assert issues == []


def test_span_text_drift_is_detected():
    poem = Poem(
        id="P1",
        lines=[Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在")],
    )
    # 원문은 "先祖山蹤在"인데 태깅 결과 텍스트가 "先祖遺蹤在"로 달라짐 -> 훼손 감지
    issues = validate_poem(poem, original_plain_lookup={"L1": "先祖山蹤在"})
    assert any("원문 훼손" in issue for issue in issues)


def test_couplet_on_quatrain_is_detected():
    poem = Poem(
        id="P1",
        detailtype="절구",
        lines=[
            Line(id="L1", order=1, content_xml="字"),
            Line(id="L2", order=2, content_xml="字", in_couplet=True),
            Line(id="L3", order=3, content_xml="字", in_couplet=True),
            Line(id="L4", order=4, content_xml="字"),
        ],
    )
    issues = validate_poem(poem, original_plain_lookup={"L1": "字", "L2": "字", "L3": "字", "L4": "字"})
    assert any("절구에 Couplet" in issue for issue in issues)
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_validate.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: validate.py 구현**

```python
import re

from .poem_model import Poem

_TAG_STRIP = re.compile(r"</?(term|d|rhyme)>")


def _plain(xml_fragment: str) -> str:
    return _TAG_STRIP.sub("", xml_fragment)


def validate_poem(poem: Poem, original_plain_lookup: dict[str, str]) -> list[str]:
    issues: list[str] = []

    for line in poem.lines:
        current_plain = _plain(line.content_xml)
        original_plain = original_plain_lookup.get(line.id)
        if original_plain is not None and current_plain != original_plain:
            issues.append(
                f"{poem.id}/{line.id}: 원문 훼손 의심 (원문='{original_plain}', 현재='{current_plain}')"
            )

    if poem.detailtype == "절구" and any(ln.in_couplet for ln in poem.lines):
        issues.append(f"{poem.id}: 절구에 Couplet이 배치됨 (절구는 대장 대상 아님)")

    return issues
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_validate.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/validate.py tests/test_validate.py
git commit -m "feat: add rule-based post-run validation"
```

---

## Task 10: QA 로그

**Files:**
- Create: `src/qa_log.py`
- Create: `tests/test_qa_log.py`

**Interfaces:**
- Produces: `QALog` 클래스 — `add(poem_id: str, collection: str, item: str, reason: str) -> None`, `write_csv(path: Path) -> None`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_qa_log.py`:
```python
import csv

from src.qa_log import QALog


def test_write_csv_produces_expected_rows(tmp_path):
    log = QALog()
    log.add(poem_id="P1", collection="지천집", item="Theme", reason="근거 빈약")
    log.add(poem_id="P2", collection="지천집", item="Couplet", reason="판단 유보")

    out_path = tmp_path / "log.csv"
    log.write_csv(out_path)

    with open(out_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    assert rows[0]["poem_id"] == "P1"
    assert rows[0]["item"] == "Theme"
    assert rows[1]["reason"] == "판단 유보"


def test_empty_log_still_writes_header(tmp_path):
    log = QALog()
    out_path = tmp_path / "log.csv"
    log.write_csv(out_path)

    with open(out_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows == []
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_qa_log.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: qa_log.py 구현**

```python
import csv
from pathlib import Path


class QALog:
    _FIELDS = ["poem_id", "collection", "item", "reason"]

    def __init__(self):
        self._rows: list[dict] = []

    def add(self, poem_id: str, collection: str, item: str, reason: str) -> None:
        self._rows.append(
            {"poem_id": poem_id, "collection": collection, "item": item, "reason": reason}
        )

    def write_csv(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self._FIELDS)
            writer.writeheader()
            writer.writerows(self._rows)
```

(`utf-8-sig`로 저장하는 이유: 엑셀에서 한글 CSV를 열 때 BOM이 없으면 깨지는 문제를 방지)

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_qa_log.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/qa_log.py tests/test_qa_log.py
git commit -m "feat: add QA log CSV writer"
```

---

## Task 11: 파이프라인 오케스트레이션 (체크포인트 포함)

**Files:**
- Create: `src/pipeline.py`
- Create: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: 전체 이전 Task 모듈
- Produces: `run_pipeline(input_path: Path, output_path: Path, qa_path: Path, checkpoint_path: Path, dict_index: DictIndex, llm_client: LLMClient) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_pipeline.py`:
```python
import json

from src.dict_index import DictIndex
from src.llm_client import FakeLLMClient
from src.pipeline import run_pipeline
from src.xml_io import parse_collection, write_collection
from src.poem_model import Line, Poem


def _write_fixture(path):
    poems = [
        Poem(
            id="P1",
            title_xml="題",
            lines=[
                Line(id="L1", order=1, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L2", order=2, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L3", order=3, content_xml="<term>先祖</term>遺蹤在"),
                Line(id="L4", order=4, content_xml="<term>先祖</term>遺蹤在"),
            ],
            charactercount="오언",
        )
    ]
    write_collection(path, poems)


def test_pipeline_produces_output_and_qa_files(tmp_path):
    input_path = tmp_path / "in.xml"
    _write_fixture(input_path)
    output_path = tmp_path / "out.xml"
    qa_path = tmp_path / "qa.csv"
    checkpoint_path = tmp_path / "checkpoint.json"

    dict_index = DictIndex({"先祖"})
    llm = FakeLLMClient(
        responses=[
            {
                "basetype": "근체시",
                "detailtype": "절구",
                "couplets": [],
                "themes": [],
            }
        ]
    )

    run_pipeline(input_path, output_path, qa_path, checkpoint_path, dict_index, llm, collection_name="테스트문집")

    assert output_path.exists()
    assert qa_path.exists()
    result_poems = parse_collection(output_path)
    assert result_poems[0].basetype == "근체시"


def test_pipeline_skips_already_checkpointed_poems(tmp_path):
    input_path = tmp_path / "in.xml"
    _write_fixture(input_path)
    output_path = tmp_path / "out.xml"
    qa_path = tmp_path / "qa.csv"
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text(json.dumps({"done_poem_ids": ["P1"]}), encoding="utf-8")

    dict_index = DictIndex({"先祖"})
    llm = FakeLLMClient(responses=[])  # 호출되면 즉시 실패 -> 스킵됐는지 검증

    run_pipeline(input_path, output_path, qa_path, checkpoint_path, dict_index, llm, collection_name="테스트문집")

    # P1이 체크포인트에 있어 LLM이 호출되지 않아야 함
    assert llm.calls == []
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_pipeline.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: pipeline.py 구현**

```python
import json
import re
from pathlib import Path

from .dict_index import DictIndex
from .interpretive_classify import classify_form_couplet_theme
from .llm_client import LLMClient
from .qa_log import QALog
from .term_classify import classify_poem_terms
from .validate import validate_poem
from .xml_io import parse_collection, write_collection

_TAG_STRIP = re.compile(r"</?(term|d|rhyme)>")


def _plain(xml_fragment: str) -> str:
    return _TAG_STRIP.sub("", xml_fragment)


def _load_checkpoint(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("done_poem_ids", []))


def _save_checkpoint(path: Path, done_ids: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"done_poem_ids": sorted(done_ids)}), encoding="utf-8")


def run_pipeline(
    input_path: Path,
    output_path: Path,
    qa_path: Path,
    checkpoint_path: Path,
    dict_index: DictIndex,
    llm_client: LLMClient,
    collection_name: str,
) -> None:
    poems = parse_collection(input_path)
    done_ids = _load_checkpoint(checkpoint_path)
    qa_log = QALog()

    processed = []
    for poem in poems:
        original_plain_lookup = {ln.id: _plain(ln.content_xml) for ln in poem.lines}

        if poem.id in done_ids:
            processed.append(poem)
            continue

        try:
            poem, term_flags = classify_poem_terms(poem, dict_index, llm_client)
            poem, theme_flags = classify_form_couplet_theme(poem, llm_client)
        except Exception as exc:  # noqa: BLE001 - 개별 시 실패가 전체를 막지 않도록 함
            qa_log.add(poem.id, collection_name, "처리 실패", str(exc))
            processed.append(poem)
            continue

        for flag in term_flags + theme_flags:
            qa_log.add(flag["poem_id"], collection_name, flag["item"], flag["reason"])

        issues = validate_poem(poem, original_plain_lookup)
        for issue in issues:
            qa_log.add(poem.id, collection_name, "검증 실패", issue)

        processed.append(poem)
        done_ids.add(poem.id)
        _save_checkpoint(checkpoint_path, done_ids)

    write_collection(output_path, processed)
    qa_log.write_csv(qa_path)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_pipeline.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: orchestrate full pipeline with checkpointing"
```

---

## Task 12: 골드 검증 스크립트

**Files:**
- Create: `scripts/run_gold_eval.py`

**Interfaces:**
- Consumes: `parse_collection` (Task 3), `run_pipeline`의 구성요소(Task 11), `config.GOLD_PATH`
- Produces: 실행 시 정확도 리포트를 표준출력에 출력하는 CLI 스크립트. 자동 테스트 대상은 아니며(실 API 호출 포함) 수동 실행으로 검증한다.

- [ ] **Step 1: 스크립트 작성**

```python
"""임백호집 723수 중 뒤쪽 100수를 hold-out으로 감추고, 파이프라인이 예측한
Theme/Basetype/Couplet을 실제 정답과 대조해 정확도를 출력한다."""

import copy

from src import config
from src.dict_index import DictIndex
from src.interpretive_classify import classify_form_couplet_theme
from src.llm_client import AnthropicLLMClient
from src.poem_model import Poem
from src.xml_io import parse_collection

HOLDOUT_SIZE = 100


def _strip_answers(poem: Poem) -> Poem:
    blanked = copy.deepcopy(poem)
    blanked.basetype = ""
    blanked.detailtype = ""
    blanked.themes = []
    for line in blanked.lines:
        line.in_couplet = False
    return blanked


def main() -> None:
    all_poems = parse_collection(config.GOLD_PATH)
    holdout = all_poems[-HOLDOUT_SIZE:]

    dict_index = DictIndex.load(config.CACHE_DIR / "dict_index.pkl")
    llm_client = AnthropicLLMClient(model=config.LLM_MODEL)

    basetype_correct = 0
    detailtype_correct = 0
    theme_category_hits = 0
    theme_category_total = 0
    couplet_line_matches = 0
    couplet_line_total = 0

    for gold_poem in holdout:
        blanked = _strip_answers(gold_poem)
        predicted, _ = classify_form_couplet_theme(blanked, llm_client)

        if predicted.basetype == gold_poem.basetype:
            basetype_correct += 1
        if predicted.detailtype == gold_poem.detailtype:
            detailtype_correct += 1

        gold_categories = {t.category for t in gold_poem.themes}
        pred_categories = {t.category for t in predicted.themes}
        theme_category_hits += len(gold_categories & pred_categories)
        theme_category_total += len(gold_categories)

        gold_couplet_orders = {ln.order for ln in gold_poem.lines if ln.in_couplet}
        pred_couplet_orders = {ln.order for ln in predicted.lines if ln.in_couplet}
        couplet_line_matches += len(gold_couplet_orders & pred_couplet_orders)
        couplet_line_total += len(gold_couplet_orders)

    n = len(holdout)
    print(f"hold-out 표본: {n}수")
    print(f"Basetype 정확도: {basetype_correct}/{n} ({basetype_correct/n:.1%})")
    print(f"Detailtype 정확도: {detailtype_correct}/{n} ({detailtype_correct/n:.1%})")
    if theme_category_total:
        print(f"Theme 카테고리 재현율: {theme_category_hits}/{theme_category_total} ({theme_category_hits/theme_category_total:.1%})")
    if couplet_line_total:
        print(f"Couplet 구-라인 재현율: {couplet_line_matches}/{couplet_line_total} ({couplet_line_matches/couplet_line_total:.1%})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: `.cache`에 사전 인덱스가 없다면 먼저 빌드**

Run: `.venv\Scripts\python scripts\build_dict_index.py`

- [ ] **Step 3: 환경변수 설정 후 실행**

Run (PowerShell): `$env:ANTHROPIC_API_KEY="<실제 키>"; .venv\Scripts\python scripts\run_gold_eval.py`
Expected: 4개 정확도 지표가 출력됨. 이 수치를 사용자에게 보고하고, Theme 재현율이
낮으면(예: 60% 미만) `interpretive_classify.py`의 `SYSTEM_PROMPT`/`THEME_CATEGORIES`
키워드를 보강한 뒤 재실행한다.

- [ ] **Step 4: 커밋**

```bash
git add scripts/run_gold_eval.py
git commit -m "feat: add gold-standard evaluation script against 임백호집 hold-out"
```

---

## Task 13: 파일럿 실행 — 지천집

**Files:**
- Create: `scripts/run_pilot.py`
- Modify: `src/term_classify.py` (다중 `<term>` 태그 시구 처리로 확장)
- Modify: `tests/test_term_classify.py` (다중 태그 케이스 테스트 추가)

**Interfaces:**
- Consumes: `run_pipeline` (Task 11), `config`
- Produces: `output/완성본_지천집_황정욱_자동태깅_<날짜>.xml`, `qa/지천집_검토필요_<날짜>.csv`

- [ ] **Step 1: 다중 `<term>` 처리를 위한 실패하는 테스트 추가**

`tests/test_term_classify.py`에 추가 (지천집 실제 시구 형태 반영):
```python
def test_line_with_multiple_term_tags_all_get_reclassified():
    poem = Poem(
        id="P19425",
        lines=[Line(id="L1", order=1, content_xml="<term>先祖</term><term>翼成</term>公寧越懸板韻")],
    )
    idx = DictIndex({"先祖"})  # "翼成"은 사전 미등재
    llm = FakeLLMClient(responses=[])

    result, flags = classify_poem_terms(poem, idx, llm)

    assert "<term>先祖</term>" in result.lines[0].content_xml
    assert "<d>翼成</d>" in result.lines[0].content_xml
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_term_classify.py -v`
Expected: FAIL (`_existing_hint`가 첫 번째 태그만 처리)

- [ ] **Step 3: term_classify.py를 다중 태그 지원으로 확장**

`src/term_classify.py`에서 `_existing_hint` 함수를 삭제하고 아래 `_existing_hints`
(복수형)로 교체한다:

```python
def _existing_hints(content_xml: str) -> tuple[str, list[tuple[int, int]]]:
    """content_xml 안의 모든 <term> 태그 위치를 순수 텍스트 기준 (start, end) 리스트로 반환."""
    plain = _strip_tags(content_xml)
    hints: list[tuple[int, int]] = []
    cursor_plain = 0
    cursor_xml = 0
    for m in _TAG_PATTERN.finditer(content_xml):
        prefix_plain = _strip_tags(content_xml[cursor_xml : m.start()])
        start = cursor_plain + len(prefix_plain)
        end = start + len(m.group(2))
        hints.append((start, end))
        cursor_plain = end
        cursor_xml = m.end()
    return plain, hints
```

그리고 `classify_poem_terms` 전체를 아래로 교체한다 (기존 단일-hint 루프를
다중-hint 루프로 바꾼 버전):

```python
def classify_poem_terms(
    poem: Poem, dict_index: DictIndex, llm_client: LLMClient
) -> tuple[Poem, list[dict]]:
    flags: list[dict] = []
    confirmed_spans: dict[str, list[tuple[int, int, str]]] = {}
    ambiguous_requests = []

    for line in poem.lines:
        plain, hints = _existing_hints(line.content_xml)
        confirmed_spans[line.id] = []
        for hint_start, hint_end in hints:
            candidates = generate_candidates(plain, hint_start, hint_end, dict_index)
            if len(candidates) == 1:
                c = candidates[0]
                label = "term" if c.in_dict else "d"
                confirmed_spans[line.id].append((c.start, c.end, label))
            else:
                ambiguous_requests.append(
                    {
                        "line_id": line.id,
                        "plain_text": plain,
                        "candidates": [
                            {"start": c.start, "end": c.end, "text": c.text, "in_dict": c.in_dict}
                            for c in candidates
                        ],
                    }
                )

    if ambiguous_requests:
        user_prompt = (
            "다음 시구들의 애매한 시어 구간을 판정해 resolved_spans로 반환하세요.\n"
            f"{ambiguous_requests}"
        )
        schema = {
            "type": "object",
            "properties": {
                "resolved_spans": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line_id": {"type": "string"},
                            "start": {"type": "integer"},
                            "end": {"type": "integer"},
                            "text": {"type": "string"},
                            "label": {"type": "string", "enum": ["term", "d"]},
                        },
                        "required": ["line_id", "start", "end", "text", "label"],
                    },
                }
            },
            "required": ["resolved_spans"],
        }
        response = llm_client.complete(TERM_CLASSIFY_SYSTEM_PROMPT, user_prompt, schema)
        for span in response["resolved_spans"]:
            confirmed_spans[span["line_id"]].append((span["start"], span["end"], span["label"]))
            flags.append(
                {
                    "poem_id": poem.id,
                    "item": "term/D",
                    "reason": f"{span['line_id']}: term/D 분절 LLM 판정",
                }
            )

    new_lines = []
    for line in poem.lines:
        plain, hints = _existing_hints(line.content_xml)
        if not hints:
            new_lines.append(line)
            continue
        new_content = _rebuild_line(plain, confirmed_spans[line.id])
        new_lines.append(Line(id=line.id, order=line.order, content_xml=new_content))

    poem.lines = new_lines
    return poem, flags
```

이 버전은 겹치지 않는 여러 `<term>` 태그를 모두 개별 힌트로 처리한다. 원본
19개 문집 데이터의 `<term>` 태그는 서로 겹치지 않으므로(각 문집 파일에서
확인됨) `_rebuild_line`에 그대로 넘겨도 안전하다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_term_classify.py -v`
Expected: PASS (전체 통과)

- [ ] **Step 5: 파일럿 실행 스크립트 작성**

```python
"""지천집(224수)을 대상으로 전체 파이프라인을 실행한다."""

from src import config
from src.dict_index import DictIndex
from src.llm_client import AnthropicLLMClient
from src.pipeline import run_pipeline

RUN_DATE = "20260804"  # 실행 시 실제 날짜로 교체

if __name__ == "__main__":
    dict_index = DictIndex.load(config.CACHE_DIR / "dict_index.pkl")
    llm_client = AnthropicLLMClient(model=config.LLM_MODEL)

    run_pipeline(
        input_path=config.EXTRACTED_DIR / "태깅_지천집.txt",
        output_path=config.OUTPUT_DIR / f"완성본_지천집_황정욱_자동태깅_{RUN_DATE}.xml",
        qa_path=config.QA_DIR / f"지천집_검토필요_{RUN_DATE}.csv",
        checkpoint_path=config.CACHE_DIR / "checkpoint_지천집.json",
        dict_index=dict_index,
        llm_client=llm_client,
        collection_name="지천집",
    )
    print("지천집 파일럿 완료")
```

- [ ] **Step 6: 실행**

Run (PowerShell): `$env:ANTHROPIC_API_KEY="<실제 키>"; .venv\Scripts\python scripts\run_pilot.py`
Expected: `지천집 파일럿 완료` 출력, `output/완성본_지천집_황정욱_자동태깅_20260804.xml`과
`qa/지천집_검토필요_20260804.csv` 생성. 224수가 모두 처리될 때까지 시간이 걸릴 수
있으므로 중단되면 재실행 시 체크포인트로 이어서 진행되는지 확인한다.

- [ ] **Step 7: 결과 표본 확인 (사람 눈 검증)**

`output/완성본_지천집_황정욱_자동태깅_<날짜>.xml`에서 5~10편을 골라 원본
`extracted/.../태깅_지천집.txt`와 나란히 비교한다: term/D 분류가 타당한지,
Theme의 evidence가 실제로 근거 있는지, Couplet 위치가 자연스러운지 확인하고
사용자에게 before/after로 보여준다.

- [ ] **Step 8: 커밋**

```bash
git add scripts/run_pilot.py src/term_classify.py tests/test_term_classify.py
git commit -m "feat: run auto-tagging pilot on 지천집 with multi-term-tag support"
```

---

## Self-Review 결과 (계획 작성자 자체 점검)

- **스펙 커버리지**: 사전 인덱스(Task 2), 시구 분절+term/D(Task 4,6,13), Form(Task 7),
  Couplet(Task 7,8), Theme+환각 검증(Task 7), 검증(Task 9), QA 로그(Task 10),
  체크포인트/재개(Task 11), 골드 검증(Task 12), 지천집 파일럿(Task 13) — 스펙의
  모든 항목에 대응하는 태스크가 있음을 확인.
- **제외 항목 확인**: 전고(Allusion), 수운 아카이브는 어떤 태스크에서도 다루지 않음 — 스펙과 일치.
- **타입/시그니처 일관성**: `Poem`/`Line`/`ThemeTag`는 Task 3에서 정의된 필드명을
  이후 모든 태스크(6,7,8,9,11,12,13)가 동일하게 사용하는지 재확인 완료
  (`content_xml`, `in_couplet`, `basetype`/`detailtype`, `themes` 등 통일).
- **알려진 한계 (계획 작성 중 발견, 설계 문서에는 없던 세부사항)**:
  - Task 6의 `classify_poem_terms`는 원본 `<term>` 태그가 서로 겹치지 않는다는
    전제로 동작한다. 파일럿(Task 13) 중 겹치는 사례가 발견되면 별도 처리가 필요하다.
  - Form 판정(Task 7)은 애초 설계보다 LLM 의존도가 높다 — 구수만으로는 근체시/고체시
    경계(4구·8구)를 신뢰할 수 없다는 점을 계획 작성 중 실데이터로 확인해 사용자에게
    보고하고 반영했다.

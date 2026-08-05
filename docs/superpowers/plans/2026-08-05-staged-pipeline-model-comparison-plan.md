# 단계별 파이프라인 + 3모델 비교 실험 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 지천집 50수를 대상으로, 형식→대장→시어→주제 순 단계별(각각 단일 목적) LLM
호출 파이프라인을 만들고, Timely 중개 API를 통해 Claude Opus 4.7 / Gemini 3 Flash
Preview / GPT-5.5 세 모델로 각각 실행해 결과를 나란히 비교하는 리포트를 생성한다.

**Architecture:** 기존 프로덕션 파이프라인(`src/`)은 건드리지 않고 `experiments/`
아래 별도 모듈로 실험을 구성한다. `src/llm_client.py`에는 `TimelyLLMClient`만
추가한다(기존 `LLMClient` 프로토콜을 그대로 구현하는 새 클라이언트이므로 다른 코드에
영향이 없다). term/D 판정에서는 한어대사전을 LLM 프롬프트에서 완전히 배제하고,
LLM이 반환한 span을 사후에 사전 조회로만 term/D 라벨링한다.

**Tech Stack:** Python 3.14, `openai` SDK(Timely가 OpenAI 호환 REST를 제공하므로),
`pytest`, 기존 `src/dict_index.py`·`src/poem_model.py`·`src/xml_io.py`·
`src/validate.py`·`src/qa_log.py` 재사용.

## Global Constraints

- 프로덕션 파이프라인 파일(`src/pipeline.py`, `src/term_classify.py`,
  `src/interpretive_classify.py`)은 이번 계획에서 전혀 수정하지 않는다. 새 로직은
  전부 `experiments/`에 둔다. `src/llm_client.py`에는 `TimelyLLMClient` 클래스
  추가만 허용된다(기존 클래스 수정 없음).
- 원본 데이터(`한어대사전.txt`, `태깅_지천집.txt`, `임백호집_3차완본_20260730.txt`)는
  절대 수정하지 않는다.
- 전고(Allusion)는 여전히 범위 밖 — 새 코드 어디에도 Allusion 관련 로직을 넣지 않는다.
- term/D 판정용 LLM 프롬프트를 만드는 코드는 `DictIndex`를 import하지 않는다(사전이
  프롬프트에 새어 들어가지 않음을 코드 구조로 보장).
- 입력은 `extracted/대상데이터_제목내용시어운자대장태그/태깅_지천집.txt`의 파일
  순서상 처음 50수로 고정한다(무작위 아님 — 재현성).
- 대장(Couplet) 호출은 `basetype == "근체시"` 그리고 `detailtype != "절구"`인
  경우에만 수행한다(호출 여부는 오케스트레이션 코드가 결정하며, `classify_couplet`
  함수 자체는 호출 여부를 판단하지 않는다).
- QA 로그는 모델별로 별도 파일에 쓴다(`src/qa_log.py`의 `QALog` 스키마를 그대로
  쓰되 모델마다 별도 인스턴스/파일).

---

## 참고: 재사용하는 기존 인터페이스 (그대로, 수정 없음)

```python
# src/poem_model.py
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

# src/xml_io.py
def parse_collection(path: Path) -> list[Poem]: ...
def write_collection(path: Path, poems: list[Poem]) -> None: ...

# src/dict_index.py
class DictIndex:
    def contains(self, word: str) -> bool: ...
    @classmethod
    def load(cls, cache_path: Path) -> "DictIndex": ...

# src/qa_log.py
class QALog:
    def __init__(self, rows: list[dict] | None = None): ...
    def add(self, poem_id: str, collection: str, item: str, reason: str) -> None: ...
    def write_csv(self, path: Path) -> None: ...

# src/llm_client.py
class LLMClient(Protocol):
    def complete(self, system: str, user: str, response_schema: dict) -> dict: ...

class FakeLLMClient:
    def __init__(self, responses: list[dict]): ...
    # .calls: list[dict] 기록, 응답 소진 시 RetryExhaustedError

class RetryExhaustedError(Exception): ...
```

---

## Task 1: TimelyLLMClient

**Files:**
- Modify: `requirements.txt`
- Modify: `src/llm_client.py` (클래스 추가만, 기존 클래스 무수정)
- Test: `tests/test_llm_client.py` (기존 파일에 테스트 추가)

**Interfaces:**
- Consumes: `LLMClient` 프로토콜, `RetryExhaustedError` (둘 다 이미 `src/llm_client.py`에 있음)
- Produces: `TimelyLLMClient(model: str, api_key: str | None = None, max_retries: int = 3)` —
  `complete(system, user, response_schema) -> dict`를 구현. 이후 모든 태스크가 이 클래스를
  `model="anthropic/claude-opus-4.7"` 등으로 생성해 사용한다.

- [ ] **Step 1: requirements.txt에 openai 추가**

```
google-genai>=0.3.0
openai>=1.50.0
pytest>=8.0.0
```

Run: `.venv\Scripts\pip install -r requirements.txt`

- [ ] **Step 2: TimelyLLMClient 생성자만 검증하는 실패하는 테스트 작성**

`tests/test_llm_client.py`에 추가 (파일 최상단 import에 `TimelyLLMClient` 추가):
```python
def test_timely_client_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("TIMELY_API_KEY", "sdk_live_test123")
    client = TimelyLLMClient(model="anthropic/claude-opus-4.7")
    assert client is not None  # 생성자가 예외 없이 성공하는지만 확인 (실 API 호출 없음)


def test_timely_client_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("TIMELY_API_KEY", raising=False)
    with pytest.raises(KeyError):
        TimelyLLMClient(model="anthropic/claude-opus-4.7")
```

(`import pytest`가 파일 상단에 이미 없다면 추가한다.)

- [ ] **Step 3: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_llm_client.py -v`
Expected: FAIL (`ImportError: cannot import name 'TimelyLLMClient'`)

- [ ] **Step 4: TimelyLLMClient 구현**

`src/llm_client.py` 맨 끝에 추가:
```python
class TimelyLLMClient:
    """Timely 중개 API(OpenAI 호환 REST) 경유로 여러 회사 모델(Claude/Gemini/GPT/Grok)을
    같은 인터페이스로 호출한다. 구조화된 JSON 출력과 재시도를 포함한다."""

    _BASE_URL = "https://hello.timelygpt.co.kr/api/v2/chat/bridge/openai"

    def __init__(self, model: str, api_key: str | None = None, max_retries: int = 3):
        from openai import OpenAI

        self._client = OpenAI(
            base_url=self._BASE_URL,
            api_key=api_key or os.environ["TIMELY_API_KEY"],
        )
        self._model = model
        self._max_retries = max_retries

    def complete(self, system: str, user: str, response_schema: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    tools=[
                        {
                            "type": "function",
                            "function": {
                                "name": "submit_result",
                                "description": "구조화된 태깅 결과를 제출한다.",
                                "parameters": response_schema,
                            },
                        }
                    ],
                    tool_choice={"type": "function", "function": {"name": "submit_result"}},
                )
                tool_call = response.choices[0].message.tool_calls[0]
                return json.loads(tool_call.function.arguments)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                status = getattr(exc, "status_code", None)
                if status == 402:
                    # 크레딧 부족은 재시도해도 소용없으므로 즉시 실패
                    raise RetryExhaustedError(f"Timely 크레딧 부족: {exc}") from exc
                if attempt < self._max_retries - 1:
                    wait = 10 if status == 429 else 2**attempt
                    time.sleep(wait)
        raise RetryExhaustedError(f"Timely 호출 실패 ({self._max_retries}회 시도): {last_error}")
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_llm_client.py -v`
Expected: PASS (기존 테스트 포함 전부 통과)

- [ ] **Step 6: 커밋**

```bash
git add requirements.txt src/llm_client.py tests/test_llm_client.py
git commit -m "feat: add TimelyLLMClient for Claude/Gemini/GPT via Timely broker"
```

---

## Task 2: 형식(Form) 단계별 분류

**Files:**
- Create: `experiments/staged_classify.py`
- Create: `tests/test_staged_classify.py`

**Interfaces:**
- Consumes: `Poem`, `LLMClient.complete`
- Produces: `classify_form(poem: Poem, llm_client: LLMClient) -> Poem` — `poem.basetype`/
  `poem.detailtype`를 채운 `Poem`을 반환(원본을 그대로 변경 후 반환 — 기존
  `interpretive_classify.py`와 동일한 관례). 이후 태스크(3, 6)가 `poem.basetype`/
  `poem.detailtype`를 읽어 사용한다.
- `_plain_form_body(poem: Poem) -> str`: 이후 태스크들도 재사용할 공용 헬퍼 —
  전고(Allusion)/주석(Annotation) 요소를 제거하고 `<term>/<d>/<rhyme>` 태그만 벗겨낸
  순수 텍스트를 만든다(기존 `interpretive_classify.py`의 `_plain`과 동일한 로직).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_staged_classify.py`:
```python
from src.llm_client import FakeLLMClient
from src.poem_model import Line, Poem
from experiments.staged_classify import classify_form


def _quatrain():
    return Poem(
        id="P1",
        title_xml="贈<d>眞鑑</d>",
        lines=[
            Line(id="L1", order=1, content_xml="夜伴<term>林僧</term>宿"),
            Line(id="L2", order=2, content_xml="<d>重雲</d>濕<term>草<rhyme>衣</rhyme></term>"),
            Line(id="L3", order=3, content_xml="<term>巖扉</term>開<term>晩日</term>"),
            Line(id="L4", order=4, content_xml="<d>棲鳥</d>始<term>驚<rhyme>飛</rhyme></term>"),
        ],
        charactercount="오언",
    )


def test_geunche_detailtype_is_computed_from_line_count_not_llm():
    # LLM이 절구를 "율시"로 잘못 말해도, 근체시로 확정된 이상 4구=절구 규칙이 덮어써야 한다
    llm = FakeLLMClient(responses=[{"basetype": "근체시", "detailtype": "율시"}])

    result = classify_form(_quatrain(), llm)

    assert result.basetype == "근체시"
    assert result.detailtype == "절구"  # LLM 응답이 아니라 규칙으로 확정됨


def test_gochesi_detailtype_comes_from_llm_unchanged():
    llm = FakeLLMClient(responses=[{"basetype": "고체시", "detailtype": "악부"}])

    result = classify_form(_quatrain(), llm)

    assert result.basetype == "고체시"
    assert result.detailtype == "악부"  # 고체시는 구수 규칙이 없으므로 LLM 응답 그대로


def test_eight_lines_geunche_becomes_yulsi():
    poem = Poem(
        id="P2",
        lines=[Line(id=f"L{i}", order=i, content_xml="字字") for i in range(1, 9)],
        charactercount="오언",
    )
    llm = FakeLLMClient(responses=[{"basetype": "근체시", "detailtype": "아무값"}])

    result = classify_form(poem, llm)

    assert result.detailtype == "율시"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_staged_classify.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: experiments/staged_classify.py 시작 (Form 부분만)**

```python
import re

from src.llm_client import LLMClient
from src.poem_model import Poem

_ELEMENT_STRIP = re.compile(r"<Allusion\b[^>]*/>|<Annotation\b[^>]*>.*?</Annotation>", re.DOTALL)
_TAG_STRIP = re.compile(r"</?(term|d|rhyme)>")

_FORM_SYSTEM_PROMPT = """\
당신은 한국 한시 형식 분류 전문가입니다. 시 한 편을 보고 형식을 판정해
submit_result 도구로 제출하세요.

- 근체시: 절구(4구)·율시(8구)·배율(8구 초과) — 근체시로 판단되면 detailtype에는
  당신이 생각하는 값을 넣어도 되지만, 실제로는 구수로 기계적으로 재확정되므로
  절구/율시/배율 여부에 대한 고민보다 근체시/고체시 판정 자체에 집중하세요.
- 고체시: 고시·악부·사(詞)·사(辭)·부(賦)·잡체시(雜體詩)·과체시(科體詩) 중
  detailtype을 정확히 판단하세요. 제목이 '~歌', '~行', '~引', '~謠'로 끝나면
  고체시(악부/고시)일 가능성이 높습니다.
"""

_FORM_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "basetype": {"type": "string", "enum": ["근체시", "고체시"]},
        "detailtype": {"type": "string"},
    },
    "required": ["basetype", "detailtype"],
}


def _plain_form_body(poem: Poem) -> str:
    def plain(xml_fragment: str) -> str:
        without_out_of_scope = _ELEMENT_STRIP.sub("", xml_fragment)
        return _TAG_STRIP.sub("", without_out_of_scope)

    title_plain = plain(poem.title_xml)
    body_plain = "\n".join(plain(ln.content_xml) for ln in poem.lines)
    return title_plain + "\n" + body_plain


def _geunche_detailtype(line_count: int) -> str:
    if line_count == 4:
        return "절구"
    if line_count == 8:
        return "율시"
    return "배율"


def classify_form(poem: Poem, llm_client: LLMClient) -> Poem:
    title_plain = _TAG_STRIP.sub("", _ELEMENT_STRIP.sub("", poem.title_xml))
    user_prompt = (
        f"제목: {title_plain}\n"
        f"자수: {poem.charactercount}\n"
        f"구수: {len(poem.lines)}\n"
    )

    result = llm_client.complete(_FORM_SYSTEM_PROMPT, user_prompt, _FORM_RESPONSE_SCHEMA)

    poem.basetype = result["basetype"]
    if poem.basetype == "근체시":
        poem.detailtype = _geunche_detailtype(len(poem.lines))
    else:
        poem.detailtype = result["detailtype"]

    return poem
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_staged_classify.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add experiments/staged_classify.py tests/test_staged_classify.py
git commit -m "feat: add staged Form classification (LLM basetype + rule-based geunche detailtype)"
```

---

## Task 3: 대장(Couplet) 단계별 분류

**Files:**
- Modify: `experiments/staged_classify.py`
- Modify: `tests/test_staged_classify.py`

**Interfaces:**
- Consumes: `Poem`(이미 `classify_form`을 거쳐 `basetype`/`detailtype`가 채워진 상태), `LLMClient`
- Produces: `classify_couplet(poem: Poem, llm_client: LLMClient) -> Poem` — `poem.lines[i].in_couplet`을
  설정한 `Poem` 반환. **호출 여부 판단(절구/고체시 제외)은 이 함수의 책임이 아니다** —
  오케스트레이션(Task 6)이 호출 전에 판단한다. 이 함수는 호출되면 무조건 대장 판정을 시도한다.

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_staged_classify.py`에 추가 (import에 `classify_couplet` 추가):
```python
def _yulsi_with_lines():
    return Poem(
        id="P3",
        basetype="근체시",
        detailtype="율시",
        lines=[Line(id=f"L{i}", order=i, content_xml="字字") for i in range(1, 9)],
        charactercount="오언",
    )


def test_couplet_flags_only_llm_confirmed_pairs():
    poem = _yulsi_with_lines()
    llm = FakeLLMClient(responses=[{"couplets": [[5, 6]]}])

    result = classify_couplet(poem, llm)

    in_couplet_orders = [ln.order for ln in result.lines if ln.in_couplet]
    assert in_couplet_orders == [5, 6]


def test_couplet_empty_response_flags_nothing():
    poem = _yulsi_with_lines()
    llm = FakeLLMClient(responses=[{"couplets": []}])

    result = classify_couplet(poem, llm)

    assert all(not ln.in_couplet for ln in result.lines)
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_staged_classify.py -v`
Expected: FAIL (`ImportError: cannot import name 'classify_couplet'`)

- [ ] **Step 3: classify_couplet 구현 (staged_classify.py에 추가)**

```python
_COUPLET_SYSTEM_PROMPT = """\
당신은 한국 한시 대장(對仗) 판정 전문가입니다. 근체시의 중간 구-쌍 중 실제로
문법·의미가 대응하는 경우만 [상구번호, 하구번호]로 나열해 submit_result 도구로
제출하세요. 위치상 대장이 가능해 보여도 실제 대응이 약하면 포함하지 마세요.
확신이 없으면 빈 리스트를 반환하세요.
"""

_COUPLET_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "couplets": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
        },
    },
    "required": ["couplets"],
}


def classify_couplet(poem: Poem, llm_client: LLMClient) -> Poem:
    user_prompt = "본문:\n" + "\n".join(
        f"{ln.order}구: {_TAG_STRIP.sub('', _ELEMENT_STRIP.sub('', ln.content_xml))}"
        for ln in poem.lines
    )

    result = llm_client.complete(_COUPLET_SYSTEM_PROMPT, user_prompt, _COUPLET_RESPONSE_SCHEMA)

    couplet_orders = {order for pair in result["couplets"] for order in pair}
    for line in poem.lines:
        line.in_couplet = line.order in couplet_orders

    return poem
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_staged_classify.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add experiments/staged_classify.py tests/test_staged_classify.py
git commit -m "feat: add staged Couplet classification"
```

---

## Task 4: 시어(term/D) 단계별 분류 — 사전 배제 + 사후 라벨링

**Files:**
- Modify: `experiments/staged_classify.py`
- Modify: `tests/test_staged_classify.py`

**Interfaces:**
- Consumes: `Poem`, `LLMClient`, `DictIndex.contains(word: str) -> bool`
- Produces: `classify_term_d(poem: Poem, dict_index: DictIndex, llm_client: LLMClient) -> tuple[Poem, list[dict]]` —
  각 `Line.content_xml`을 완전히 새로 판단된 `<term>`/`<d>`(+ 기존 `<rhyme>` 위치 보존)로
  재태깅한 `Poem`과 QA 플래그 리스트(`{"poem_id", "item", "reason"}`)를 반환.
  **이 함수를 정의하는 모듈 상단에서 `DictIndex`는 타입 힌트로만 참조되고, LLM
  프롬프트를 만드는 코드(`_TERM_SYSTEM_PROMPT`, `user_prompt` 조립부)는 `dict_index`
  변수를 전혀 참조하지 않는다 — 사전 조회는 LLM 호출이 끝난 뒤에만 일어난다.**

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_staged_classify.py`에 추가 (import에 `classify_term_d`, `from src.dict_index import DictIndex` 추가):
```python
def test_term_d_llm_proposes_spans_without_seeing_dictionary():
    poem = Poem(
        id="P4",
        lines=[Line(id="L1", order=1, content_xml="夜伴林僧宿")],  # 태그 없는 순수 원문
    )
    idx = DictIndex({"林僧"})  # "林僧"만 사전에 등재
    llm = FakeLLMClient(responses=[{"spans": [{"line_id": "L1", "text": "林僧"}]}])

    result, flags = classify_term_d(poem, idx, llm)

    # LLM에 사전 정보가 전달되지 않았는지 확인 (프롬프트 텍스트에 "사전"/dict 관련
    # 문자열이 없어야 함 -- FakeLLMClient가 기록한 실제 호출 인자를 검사)
    assert "林僧" not in llm.calls[0]["system"]  # 시스템 프롬프트에 사전 후보가 안 들어감
    assert result.lines[0].content_xml == "夜伴<term>林僧</term>宿"
    assert flags == []


def test_term_d_span_not_in_dictionary_becomes_d():
    poem = Poem(
        id="P5",
        lines=[Line(id="L1", order=1, content_xml="重雲濕草衣")],
    )
    idx = DictIndex(set())  # 빈 사전 -> 무조건 미등재
    llm = FakeLLMClient(responses=[{"spans": [{"line_id": "L1", "text": "重雲"}]}])

    result, flags = classify_term_d(poem, idx, llm)

    assert result.lines[0].content_xml == "<d>重雲</d>濕草衣"


def test_term_d_preserves_rhyme_tag_position():
    poem = Poem(
        id="P6",
        lines=[Line(id="L1", order=1, content_xml="草<rhyme>衣</rhyme>")],
    )
    idx = DictIndex({"草衣"})
    llm = FakeLLMClient(responses=[{"spans": [{"line_id": "L1", "text": "草衣"}]}])

    result, flags = classify_term_d(poem, idx, llm)

    assert result.lines[0].content_xml == "<term>草<rhyme>衣</rhyme></term>"


def test_term_d_hallucinated_span_text_is_flagged_and_skipped():
    poem = Poem(
        id="P7",
        lines=[Line(id="L1", order=1, content_xml="夜伴林僧宿")],
    )
    idx = DictIndex(set())
    llm = FakeLLMClient(responses=[{"spans": [{"line_id": "L1", "text": "存在しない"}]}])

    result, flags = classify_term_d(poem, idx, llm)

    assert result.lines[0].content_xml == "夜伴林僧宿"  # 원문 그대로, 태그 없음
    assert len(flags) == 1
    assert flags[0]["item"] == "term/D"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_staged_classify.py -v`
Expected: FAIL (`ImportError: cannot import name 'classify_term_d'`)

- [ ] **Step 3: classify_term_d 구현 (staged_classify.py에 추가)**

```python
_RHYME_TAG_RE = re.compile(r"<rhyme>(.)</rhyme>")

_TERM_SYSTEM_PROMPT = """\
당신은 한국 한시 시어(詩語) 분석 전문가입니다. 아래 시구들에서 의미적으로
중요한 시어(2자 이상의 명사어·형용사어·안긴 어휘)의 경계를 문맥과 문학적 판단만으로
정하세요. 부정어는 상태·정서를 구체화하는 경우만(예: 無消息) 포함하고, 단순
조동사·기능어(예: 不敢)는 제외합니다. 판단한 시어는 원문 글자를 그대로
text 필드에 담아 submit_result 도구로 제출하세요. 시구마다 시어가 없을 수도, 여러
개일 수도 있습니다.
"""

_TERM_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "spans": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["line_id", "text"],
            },
        },
    },
    "required": ["spans"],
}


def _plain_and_rhyme_index(content_xml: str) -> tuple[str, int | None]:
    """기존 term/d 태그를 모두 제거한 순수 텍스트와, <rhyme>로 감싸인 글자의
    순수 텍스트 기준 인덱스(없으면 None)를 반환한다."""
    without_term_d = re.sub(r"</?(term|d)>", "", content_xml)
    m = _RHYME_TAG_RE.search(without_term_d)
    plain = _RHYME_TAG_RE.sub(r"\1", without_term_d)
    rhyme_index = None
    if m:
        prefix = without_term_d[: m.start()]
        prefix_plain = _RHYME_TAG_RE.sub(r"\1", prefix)
        rhyme_index = len(prefix_plain)
    return plain, rhyme_index


def _rebuild_line_with_spans(
    plain: str, rhyme_index: int | None, spans: list[tuple[int, int, str]]
) -> str:
    """spans: (start, end, label) 정렬된 겹치지 않는 구간 리스트."""
    spans = sorted(spans, key=lambda s: s[0])

    def wrap_char_at(text: str, idx: int) -> str:
        if idx is None or not (0 <= idx < len(text)):
            return text
        return text[:idx] + f"<rhyme>{text[idx]}</rhyme>" + text[idx + 1 :]

    out = []
    cursor = 0
    for start, end, label in spans:
        gap = plain[cursor:start]
        if rhyme_index is not None and cursor <= rhyme_index < start:
            gap = wrap_char_at(gap, rhyme_index - cursor)
        out.append(gap)

        span_text = plain[start:end]
        if rhyme_index is not None and start <= rhyme_index < end:
            span_text = wrap_char_at(span_text, rhyme_index - start)
        out.append(f"<{label}>{span_text}</{label}>")
        cursor = end
    tail = plain[cursor:]
    if rhyme_index is not None and cursor <= rhyme_index < len(plain):
        tail = wrap_char_at(tail, rhyme_index - cursor)
    out.append(tail)
    return "".join(out)


def classify_term_d(
    poem: Poem, dict_index, llm_client: LLMClient
) -> tuple[Poem, list[dict]]:
    flags: list[dict] = []
    plains: dict[str, tuple[str, int | None]] = {
        ln.id: _plain_and_rhyme_index(ln.content_xml) for ln in poem.lines
    }

    user_prompt = "시구:\n" + "\n".join(
        f"{ln.id}: {plains[ln.id][0]}" for ln in poem.lines
    )
    result = llm_client.complete(_TERM_SYSTEM_PROMPT, user_prompt, _TERM_RESPONSE_SCHEMA)

    spans_by_line: dict[str, list[tuple[int, int, str]]] = {ln.id: [] for ln in poem.lines}
    cursor_by_line: dict[str, int] = {ln.id: 0 for ln in poem.lines}
    for span in result["spans"]:
        line_id = span["line_id"]
        text = span["text"]
        if line_id not in plains:
            flags.append(
                {"poem_id": poem.id, "item": "term/D", "reason": f"알 수 없는 line_id: {line_id}"}
            )
            continue
        plain, _ = plains[line_id]
        start = plain.find(text, cursor_by_line[line_id])
        if start == -1:
            flags.append(
                {
                    "poem_id": poem.id,
                    "item": "term/D",
                    "reason": f"{line_id}: LLM이 반환한 시어 '{text}'가 원문에 없음(환각 의심)",
                }
            )
            continue
        end = start + len(text)
        label = "term" if dict_index.contains(text) else "d"
        spans_by_line[line_id].append((start, end, label))
        cursor_by_line[line_id] = end

    new_lines = []
    for line in poem.lines:
        plain, rhyme_index = plains[line.id]
        new_content = _rebuild_line_with_spans(plain, rhyme_index, spans_by_line[line.id])
        new_lines.append(
            type(line)(id=line.id, order=line.order, content_xml=new_content, in_couplet=line.in_couplet)
        )
    poem.lines = new_lines

    return poem, flags
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_staged_classify.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: DictIndex를 프롬프트 조립 코드가 참조하지 않는지 수동 확인**

`_TERM_SYSTEM_PROMPT`, `_TERM_RESPONSE_SCHEMA`, `classify_term_d`의 `user_prompt` 조립부
(`llm_client.complete` 호출 전 코드)를 눈으로 다시 확인해 `dict_index` 변수가 등장하지
않는지 검증한다 (등장은 `llm_client.complete(...)` 호출 이후, `dict_index.contains(text)`
한 곳에서만 있어야 한다).

- [ ] **Step 6: 커밋**

```bash
git add experiments/staged_classify.py tests/test_staged_classify.py
git commit -m "feat: add staged term/D classification with dictionary excluded from LLM prompt"
```

---

## Task 5: 주제(Theme) 단계별 분류

**Files:**
- Modify: `experiments/staged_classify.py`
- Modify: `tests/test_staged_classify.py`

**Interfaces:**
- Consumes: `Poem`(이미 `classify_term_d`를 거쳐 시어 태깅이 완료된 상태), `LLMClient`
- Produces: `classify_theme(poem: Poem, llm_client: LLMClient) -> tuple[Poem, list[dict]]` —
  `poem.themes`를 채운 `Poem`과 QA 플래그. 기존 `src/interpretive_classify.py`의
  `THEME_CATEGORIES`/evidence 환각 검증 로직과 동일한 기준을 그대로 이식한다(코드
  중복이지만, 이번 실험은 프로덕션 모듈을 import하지 않는다는 원칙을 지키기 위해
  의도적으로 복제한다).

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_staged_classify.py`에 추가 (import에 `classify_theme` 추가):
```python
def test_theme_uses_term_tagged_poem_as_context():
    poem = Poem(
        id="P8",
        title_xml="贈<d>眞鑑</d>",
        lines=[
            Line(id="L1", order=1, content_xml="夜伴<term>林僧</term>宿"),
            Line(id="L2", order=2, content_xml="<d>重雲</d>濕<term>草<rhyme>衣</rhyme></term>"),
        ],
    )
    llm = FakeLLMClient(
        responses=[
            {
                "themes": [
                    {"category": "donate", "basis": "title", "evidence": "贈", "label_ko": "기증"},
                    {
                        "category": "buddhism",
                        "basis": "term",
                        "evidence": "林僧 草衣",
                        "label_ko": "불교",
                    },
                ]
            }
        ]
    )

    result, flags = classify_theme(poem, llm)

    assert len(result.themes) == 2
    assert result.themes[0].category == "donate"
    assert flags == []


def test_theme_evidence_hallucination_is_rejected():
    poem = Poem(id="P9", title_xml="題", lines=[Line(id="L1", order=1, content_xml="山")])
    llm = FakeLLMClient(
        responses=[
            {
                "themes": [
                    {
                        "category": "farewell",
                        "basis": "term",
                        "evidence": "존재하지않는단어",
                        "label_ko": "송별",
                    }
                ]
            }
        ]
    )

    result, flags = classify_theme(poem, llm)

    assert result.themes == []
    assert len(flags) == 1
    assert flags[0]["item"] == "Theme"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_staged_classify.py -v`
Expected: FAIL (`ImportError: cannot import name 'classify_theme'`)

- [ ] **Step 3: classify_theme 구현 (staged_classify.py에 추가)**

```python
from src.poem_model import ThemeTag  # 파일 상단 import에 추가

_THEME_CATEGORIES = {
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

_THEME_SYSTEM_PROMPT = """\
당신은 한국 한시 주제 분류 전문가입니다. 시의 제목과 이미 확정된 시어(term) 태깅을
참고해 아래 24개 카테고리 중 해당하는 것을 다중 선택하세요. 각 항목은 category(영문
코드), basis(title/term/title, term), evidence(제목 또는 시어에서 실제로 등장하는
글자 그대로), label_ko(한글 라벨)를 포함합니다. evidence는 반드시 시의 제목 또는
본문에 실제로 나오는 글자만 사용하세요. 카테고리 표: {categories}
""".format(categories=", ".join(f"{k}({v[0]})" for k, v in _THEME_CATEGORIES.items()))

_THEME_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
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
    "required": ["themes"],
}


def _theme_evidence_exists(evidence: str, poem_plain_text: str) -> bool:
    tokens = evidence.replace(",", " ").split()
    return all(token in poem_plain_text for token in tokens)


def classify_theme(poem: Poem, llm_client: LLMClient) -> tuple[Poem, list[dict]]:
    flags: list[dict] = []

    def plain(xml_fragment: str) -> str:
        without_out_of_scope = _ELEMENT_STRIP.sub("", xml_fragment)
        return _TAG_STRIP.sub("", without_out_of_scope)

    title_plain = plain(poem.title_xml)
    body_plain = "\n".join(plain(ln.content_xml) for ln in poem.lines)
    full_text = title_plain + "\n" + body_plain

    user_prompt = (
        f"제목: {title_plain}\n"
        "본문(시어 태깅 포함):\n"
        + "\n".join(f"{ln.order}구: {ln.content_xml}" for ln in poem.lines)
    )

    result = llm_client.complete(_THEME_SYSTEM_PROMPT, user_prompt, _THEME_RESPONSE_SCHEMA)

    accepted_themes = []
    for theme in result["themes"]:
        if _theme_evidence_exists(theme["evidence"], full_text):
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

Run: `.venv\Scripts\pytest tests/test_staged_classify.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: 커밋**

```bash
git add experiments/staged_classify.py tests/test_staged_classify.py
git commit -m "feat: add staged Theme classification consuming term-tagged poem"
```

---

## Task 6: 비교 실행 오케스트레이션

**Files:**
- Create: `experiments/run_comparison.py`
- Test: `tests/test_run_comparison.py`

**Interfaces:**
- Consumes: `classify_form`, `classify_couplet`, `classify_term_d`, `classify_theme` (Task 2-5),
  `parse_collection`/`write_collection` (`src/xml_io.py`), `DictIndex` (`src/dict_index.py`),
  `QALog` (`src/qa_log.py`), `TimelyLLMClient` (Task 1)
- Produces: `run_staged_pipeline(poems: list[Poem], dict_index: DictIndex, llm_client: LLMClient, model_label: str) -> tuple[list[Poem], QALog]` —
  이후 Task 7(리포트 생성)이 이 함수가 반환한 결과(또는 이 함수가 쓴 출력 파일)를 읽는다.
  `main()` 함수는 이 함수를 3개 모델에 대해 순차 실행하고 파일로 저장한다.

- [ ] **Step 1: run_staged_pipeline에 대한 실패하는 테스트 작성 (FakeLLMClient 사용)**

`tests/test_run_comparison.py`:
```python
from src.dict_index import DictIndex
from src.llm_client import FakeLLMClient
from src.poem_model import Line, Poem
from experiments.run_comparison import run_staged_pipeline


def test_run_staged_pipeline_processes_quatrain_without_couplet_call():
    poem = Poem(
        id="P1",
        title_xml="題",
        lines=[Line(id=f"L{i}", order=i, content_xml="字字") for i in range(1, 5)],
        charactercount="오언",
    )
    idx = DictIndex(set())
    # 절구(4구)이므로 Couplet 호출은 없어야 함 -> Form, term/D, Theme 3번만 큐에 준비
    llm = FakeLLMClient(
        responses=[
            {"basetype": "근체시", "detailtype": "율시"},  # Form (detailtype은 규칙으로 덮임)
            {"spans": []},  # term/D
            {"themes": []},  # Theme
        ]
    )

    result_poems, qa_log = run_staged_pipeline([poem], idx, llm, model_label="test-model")

    assert len(result_poems) == 1
    assert result_poems[0].detailtype == "절구"
    assert len(llm.calls) == 3  # Couplet 호출이 생략되었는지 확인


def test_run_staged_pipeline_calls_couplet_for_yulsi():
    poem = Poem(
        id="P2",
        title_xml="題",
        lines=[Line(id=f"L{i}", order=i, content_xml="字字") for i in range(1, 9)],
        charactercount="오언",
    )
    idx = DictIndex(set())
    llm = FakeLLMClient(
        responses=[
            {"basetype": "근체시", "detailtype": "율시"},  # Form
            {"couplets": []},  # Couplet
            {"spans": []},  # term/D
            {"themes": []},  # Theme
        ]
    )

    result_poems, qa_log = run_staged_pipeline([poem], idx, llm, model_label="test-model")

    assert len(llm.calls) == 4  # 8구=율시이므로 Couplet 호출이 있어야 함


def test_run_staged_pipeline_continues_after_poem_failure():
    # P_OK(절구, 4구)가 먼저 처리되어 정확히 3개 응답(Form/term-D/Theme, Couplet은
    # 절구라 생략)을 전부 소비한다. 그다음 P_FAIL 처리 시 큐가 완전히 비어 있으므로
    # classify_form의 첫 호출에서 FakeLLMClient가 RetryExhaustedError를 던진다 --
    # 이 실패가 P_OK의 결과나 이후 처리에 영향을 주지 않는지 검증한다.
    poems = [
        Poem(
            id="P_OK",
            title_xml="B",
            lines=[Line(id=f"L{i}", order=i, content_xml="字字") for i in range(1, 5)],
            charactercount="오언",
        ),
        Poem(id="P_FAIL", title_xml="A", lines=[Line(id="L1", order=1, content_xml="字字字字")], charactercount="오언"),
    ]
    idx = DictIndex(set())
    llm = FakeLLMClient(
        responses=[
            {"basetype": "근체시", "detailtype": "율시"},  # P_OK Form (detailtype은 규칙으로 절구로 덮임)
            {"spans": []},  # P_OK term/D
            {"themes": []},  # P_OK Theme
            # P_FAIL 차례엔 큐가 비어 있어 classify_form이 RetryExhaustedError로 실패한다
        ]
    )

    result_poems, qa_log = run_staged_pipeline(poems, idx, llm, model_label="test-model")

    assert len(result_poems) == 2  # P_FAIL도 원본 그대로 결과 리스트에 포함됨
    ok_result = next(p for p in result_poems if p.id == "P_OK")
    assert ok_result.detailtype == "절구"  # P_OK는 정상적으로 끝까지 처리됨
    fail_result = next(p for p in result_poems if p.id == "P_FAIL")
    assert fail_result.basetype == ""  # P_FAIL은 classify_form에서 실패해 미분류 상태로 남음
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_run_comparison.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: experiments/run_comparison.py 구현**

```python
from pathlib import Path

from src.dict_index import DictIndex
from src.llm_client import LLMClient, TimelyLLMClient
from src.poem_model import Poem
from src.qa_log import QALog
from src.xml_io import parse_collection, write_collection

from experiments.staged_classify import (
    classify_couplet,
    classify_form,
    classify_term_d,
    classify_theme,
)

_EXTRACTED_PATH = (
    Path(__file__).resolve().parent.parent
    / "extracted"
    / "대상데이터_제목내용시어운자대장태그"
    / "태깅_지천집.txt"
)
_OUTPUT_DIR = Path(__file__).resolve().parent / "2026-08-05-model-comparison"
_POEM_COUNT = 50

_MODELS = {
    "claude-opus-4.7": "anthropic/claude-opus-4.7",
    "gemini-3-flash-preview": "google/gemini-3-flash-preview",
    "gpt-5.5": "openai/gpt-5.5",
}


def run_staged_pipeline(
    poems: list[Poem], dict_index: DictIndex, llm_client: LLMClient, model_label: str
) -> tuple[list[Poem], QALog]:
    qa_log = QALog()
    results = []

    for poem in poems:
        try:
            poem = classify_form(poem, llm_client)

            if poem.basetype == "근체시" and poem.detailtype != "절구":
                poem = classify_couplet(poem, llm_client)

            poem, term_flags = classify_term_d(poem, dict_index, llm_client)
            poem, theme_flags = classify_theme(poem, llm_client)

            for flag in term_flags + theme_flags:
                qa_log.add(flag["poem_id"], "지천집", flag["item"], flag["reason"])
        except Exception as exc:  # noqa: BLE001
            qa_log.add(poem.id, "지천집", "처리 실패", f"[{model_label}] {exc}")

        results.append(poem)

    return results, qa_log


def main() -> None:
    all_poems = parse_collection(_EXTRACTED_PATH)
    target_poems = all_poems[:_POEM_COUNT]
    dict_index = DictIndex.load(Path(__file__).resolve().parent.parent / ".cache" / "dict_index.pkl")

    for label, model_name in _MODELS.items():
        print(f"=== {label} 실행 중 ===")
        # 매 모델마다 원본 poem 객체를 새로 파싱해 이전 모델의 결과가 섞이지 않게 한다
        poems_for_model = parse_collection(_EXTRACTED_PATH)[:_POEM_COUNT]
        llm_client = TimelyLLMClient(model=model_name)

        result_poems, qa_log = run_staged_pipeline(poems_for_model, dict_index, llm_client, label)

        write_collection(_OUTPUT_DIR / f"output_{label}.xml", result_poems)
        qa_log.write_csv(_OUTPUT_DIR / f"qa_{label}.csv")
        print(f"{label}: {len(result_poems)}수 완료")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_run_comparison.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 전체 테스트 스위트 실행**

Run: `.venv\Scripts\pytest tests/ -v`
Expected: 모든 테스트 통과 (기존 프로덕션 테스트 포함, 회귀 없음)

- [ ] **Step 6: 커밋**

```bash
git add experiments/run_comparison.py tests/test_run_comparison.py
git commit -m "feat: add staged-pipeline orchestration across 3 models via Timely"
```

---

## Task 7: 비교 리포트 생성

**Files:**
- Create: `experiments/build_report.py`
- Test: `tests/test_build_report.py`

**Interfaces:**
- Consumes: `parse_collection` (`src/xml_io.py`) — Task 6이 쓴 `output_<label>.xml` 파일들을 다시 읽는다.
- Produces: `build_comparison_report(model_outputs: dict[str, list[Poem]]) -> str` — 사람이 읽을
  비교 리포트 텍스트. `main()`은 이를 `comparison_report.txt`로 저장한다. 실 API 호출이
  전혀 없는 순수 파일 처리 로직이므로 라이브 LLM 없이 완전히 테스트 가능하다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_build_report.py`:
```python
from src.poem_model import Line, Poem, ThemeTag
from experiments.build_report import build_comparison_report


def _poem(basetype, themes):
    return Poem(
        id="P1",
        title_xml="題",
        basetype=basetype,
        detailtype="절구",
        lines=[Line(id="L1", order=1, content_xml="<term>山</term>水")],
        themes=themes,
    )


def test_report_lists_each_model_result_for_same_poem():
    model_outputs = {
        "claude-opus-4.7": [_poem("근체시", [ThemeTag("mountain", "term", "山", "산악")])],
        "gemini-3-flash-preview": [_poem("근체시", [])],
        "gpt-5.5": [_poem("고체시", [ThemeTag("water", "term", "水", "강해")])],
    }

    report = build_comparison_report(model_outputs)

    assert "P1" in report
    assert "claude-opus-4.7" in report
    assert "gemini-3-flash-preview" in report
    assert "gpt-5.5" in report
    assert "산악" in report  # Claude 결과의 주제 라벨이 리포트에 나타나야 함
    assert "고체시" in report  # GPT 결과의 형식 판정이 리포트에 나타나야 함


def test_report_handles_mismatched_poem_counts_gracefully():
    # 한 모델이 크레딧 부족으로 중간에 멈춰 poem 수가 다를 수 있음
    model_outputs = {
        "claude-opus-4.7": [_poem("근체시", [])],
        "gemini-3-flash-preview": [],
    }

    report = build_comparison_report(model_outputs)

    assert "gemini-3-flash-preview" in report
    assert "결과 없음" in report or "누락" in report
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `.venv\Scripts\pytest tests/test_build_report.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: experiments/build_report.py 구현**

```python
import re
from pathlib import Path

from src.poem_model import Poem
from src.xml_io import parse_collection

_TAG_STRIP = re.compile(r"</?(term|d|rhyme)>")
_OUTPUT_DIR = Path(__file__).resolve().parent / "2026-08-05-model-comparison"
_MODEL_LABELS = ["claude-opus-4.7", "gemini-3-flash-preview", "gpt-5.5"]


def _poem_summary(poem: Poem) -> str:
    theme_labels = ", ".join(f"{t.label_ko}({t.category})" for t in poem.themes) or "(없음)"
    lines_text = "\n".join(f"    {ln.order}구: {ln.content_xml}" for ln in poem.lines)
    return (
        f"  형식: {poem.basetype}/{poem.detailtype}\n"
        f"  주제: {theme_labels}\n"
        f"  본문:\n{lines_text}"
    )


def build_comparison_report(model_outputs: dict[str, list[Poem]]) -> str:
    all_poem_ids: list[str] = []
    seen = set()
    for poems in model_outputs.values():
        for p in poems:
            if p.id not in seen:
                seen.add(p.id)
                all_poem_ids.append(p.id)

    sections = []
    for poem_id in all_poem_ids:
        sections.append(f"{'=' * 20} {poem_id} {'=' * 20}")
        for label in _MODEL_LABELS:
            poems_by_id = {p.id: p for p in model_outputs.get(label, [])}
            sections.append(f"--- {label} ---")
            if poem_id in poems_by_id:
                sections.append(_poem_summary(poems_by_id[poem_id]))
            else:
                sections.append("  (결과 없음 -- 이 모델에서 누락됨)")
        sections.append("")

    return "\n".join(sections)


def main() -> None:
    model_outputs: dict[str, list[Poem]] = {}
    for label in _MODEL_LABELS:
        output_path = _OUTPUT_DIR / f"output_{label}.xml"
        if output_path.exists():
            model_outputs[label] = parse_collection(output_path)
        else:
            model_outputs[label] = []

    report = build_comparison_report(model_outputs)
    (_OUTPUT_DIR / "comparison_report.txt").write_text(report, encoding="utf-8")
    print(f"리포트 저장: {_OUTPUT_DIR / 'comparison_report.txt'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv\Scripts\pytest tests/test_build_report.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 전체 테스트 스위트 최종 확인**

Run: `.venv\Scripts\pytest tests/ -v`
Expected: 전체 통과, 회귀 없음

- [ ] **Step 6: 커밋**

```bash
git add experiments/build_report.py tests/test_build_report.py
git commit -m "feat: add comparison report generator for 3-model staged pipeline experiment"
```

- [ ] **Step 7: 실행 안내 (사용자가 직접 실행)**

이 단계부터는 실 API 키(`TIMELY_API_KEY`)가 필요하므로 자동 실행하지 않는다. 사용자가
`TIMELY_API_KEY`를 환경변수로 설정한 뒤:
```bash
python -m experiments.run_comparison
python -m experiments.build_report
```
를 실행하면 `experiments/2026-08-05-model-comparison/comparison_report.txt`에서
세 모델의 결과를 비교할 수 있다.

---

## Self-Review 결과 (계획 작성자 자체 점검)

- **스펙 커버리지**: TimelyLLMClient(Task 1), Form 규칙+LLM 분리(Task 2), 조건부
  Couplet 호출(Task 3, 6), 사전 배제 term/D(Task 4), term 태깅 포함 Theme(Task 5),
  50수 고정 슬라이스·모델별 출력 파일·QA 파일 분리(Task 6), 비교 리포트(Task 7) —
  스펙의 모든 항목에 대응하는 태스크가 있음을 확인.
- **프로덕션 미변경 확인**: `src/pipeline.py`, `src/term_classify.py`,
  `src/interpretive_classify.py`를 수정하는 태스크가 없음. `src/llm_client.py`는
  클래스 추가만 하는 Task 1뿐. `src/qa_log.py`도 수정 없음(모델별 별도 인스턴스로
  스키마를 그대로 재사용).
- **타입/시그니처 일관성**: `classify_form`은 `Poem`만 반환(플래그 없음, 실패할
  경우가 드문 단순 판정이므로), `classify_couplet`도 `Poem`만 반환, `classify_term_d`/
  `classify_theme`는 `tuple[Poem, list[dict]]` 반환 — Task 6의 `run_staged_pipeline`이
  이 차이를 정확히 반영해 호출하는지 재확인 완료(Form/Couplet은 언패킹 없이, term-D/
  Theme는 플래그를 언패킹).
- **알려진 한계**: `classify_form`이 예외를 던지면(예: RetryExhaustedError) 해당
  poem은 `run_staged_pipeline`의 `except` 블록에서 원본 그대로(미분류 상태) 결과
  리스트에 남는다 — 이는 프로덕션 파이프라인(Task 11)과 동일한 "개별 시 실패가
  전체를 막지 않는다" 원칙을 따른 것이며, 이번 실험 스크립트에는 재개(resume)
  기능은 없다(50수 규모라 필요성이 낮다고 판단, 필요해지면 후속 작업).

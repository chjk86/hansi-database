import json
import re
import warnings
from pathlib import Path

from .dict_index import DictIndex
from .interpretive_classify import classify_form_couplet_theme
from .llm_client import LLMClient
from .qa_log import QALog
from .term_classify import classify_poem_terms
from .validate import validate_poem
from .xml_io import parse_collection, write_collection

_TAG_STRIP = re.compile(r"</?(term|d|rhyme)>")
# xml_io.parse_collection이 개별 <Poem> 블록을 건너뛸 때 warnings.warn으로 내보내는
# 메시지에서 poem id를 뽑아내는 패턴. 이 문자열이 xml_io.py의 경고 문구와 어긋나면
# id를 못 뽑을 뿐, id="?" fallback으로 여전히 QA에는 기록된다(아래 참고).
_MALFORMED_POEM_ID_RE = re.compile(r"malformed <Poem> block skipped \(id=([^)]*)\)")


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
    # parse_collection이 손상/잘림으로 건너뛴 <Poem> 블록은 stderr 경고만 남기고
    # 어떤 산출물에도 흔적을 남기지 않았다 -- 그 경고를 여기서 가로채 QA 로그에
    # "파싱 실패" 항목으로 기록해, 사람 검토자의 작업 목록에서 이 시들이 완전히
    # 사라지지 않도록 한다.
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        poems = parse_collection(input_path)

    done_ids = _load_checkpoint(checkpoint_path)
    previously_processed = (
        {poem.id: poem for poem in parse_collection(output_path)} if output_path.exists() else {}
    )
    # qa_path가 이미 있으면(이전 실행이 중단된 뒤 재개하는 경우) 그 행들을 이어받는다
    # -- 그렇지 않으면 QALog()가 빈 상태로 시작해 재개 전 실행이 남긴 QA 플래그가
    # 이번 실행의 write_csv 호출로 통째로 덮어써져 사라진다.
    qa_log = QALog.load_csv(qa_path) if qa_path.exists() else QALog()

    for warning in caught_warnings:
        message = str(warning.message)
        m = _MALFORMED_POEM_ID_RE.search(message)
        poem_id = m.group(1) if m else "?"
        # 매 실행마다 같은 시가 같은 이유로 계속 파싱에 실패하므로(원본 파일은
        # 바뀌지 않음), 재개 시 동일 항목이 매번 중복 기록되지 않도록 방지한다.
        if not qa_log.has_entry(poem_id, "파싱 실패"):
            qa_log.add(poem_id, collection_name, "파싱 실패", message)
    if caught_warnings:
        # 처리 루프가 poem 0개(전부 체크포인트됨)로 끝나거나 첫 시에서 곧바로
        # 죽더라도, 방금 기록한 파싱 실패 항목은 즉시 디스크에 남긴다.
        qa_log.write_csv(qa_path)

    processed = []
    for poem in poems:
        original_plain_lookup = {ln.id: _plain(ln.content_xml) for ln in poem.lines}

        if poem.id in done_ids and poem.id in previously_processed:
            processed.append(previously_processed[poem.id])
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
        # 체크포인트/출력과 마찬가지로 QA 로그도 매 시 처리 직후 증분 기록한다.
        # 기존에는 루프가 전부 끝난 뒤 딱 한 번만 썼기 때문에, 긴 실행이
        # 중간에 끊기면 QA csv가 아예 만들어지지 않았고 -- 체크포인트된 시는
        # 재개 시 재처리되지 않으므로 그 QA 플래그는 영구히 복구 불가능했다.
        qa_log.write_csv(qa_path)

    write_collection(output_path, processed)
    qa_log.write_csv(qa_path)

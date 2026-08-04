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

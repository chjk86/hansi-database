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

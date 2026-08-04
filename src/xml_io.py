import re
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

from .poem_model import Line, Poem, ThemeTag

_NS_WRAPPER_OPEN = (
    '<root xmlns:ns0="http://www.w3.org/1999/xlink" '
    'xmlns:xlink="http://www.w3.org/1999/xlink">'
)
_NS_WRAPPER_CLOSE = "</root>"
_HREF_ATTR = "{http://www.w3.org/1999/xlink}href"

# 개별 <Poem> 블록을 추출하는 정규식. 원본 조각 파일(루트 없음)이든
# write_collection이 만든 완전한 문서(<?xml?>/<poems> 래퍼 포함)든 동일하게
# 동작하므로, 문서 전체를 한 번에 파싱할 필요가 없다 -- 즉 한 시가 깨진 XML을
# 담고 있어도 나머지 시 파싱에 영향을 주지 않는다.
_POEM_BLOCK_RE = re.compile(r"<Poem\b.*?</Poem>", re.DOTALL)
_POEM_ID_RE = re.compile(r'<Poem\b[^>]*\bid="([^"]*)"')
_POEM_OPEN_TAG_RE = re.compile(r"<Poem\b")


def _inner_xml(elem: ET.Element) -> str:
    """자식 요소 전체를 문자열로 직렬화 (elem 자신의 태그는 제외)."""
    text = elem.text or ""
    for child in elem:
        text += ET.tostring(child, encoding="unicode")
    return text


def _extract_poem_id(block: str) -> str:
    """정상 파싱이 불가능한 블록에서도 경고 메시지용 id는 뽑아낸다."""
    m = _POEM_ID_RE.search(block)
    return m.group(1) if m else "?"


def _poem_from_element(poem_el: ET.Element) -> Poem:
    meta = poem_el.find("Metadata")
    form = meta.find("Form")
    collection_el = meta.find("Collection")
    author_el = meta.find("Author")

    lines = []
    for child in poem_el.find("text"):
        if child.tag == "Line":
            lines.append(
                Line(
                    id=child.get("id"),
                    order=int(child.get("order")),
                    content_xml=_inner_xml(child),
                    in_couplet=False,
                )
            )
        elif child.tag == "Couplet":
            for line_el in child.findall("Line"):
                lines.append(
                    Line(
                        id=line_el.get("id"),
                        order=int(line_el.get("order")),
                        content_xml=_inner_xml(line_el),
                        in_couplet=True,
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

    return Poem(
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


def parse_collection(path: Path) -> list[Poem]:
    raw = path.read_text(encoding="utf-8")
    blocks = _POEM_BLOCK_RE.findall(raw)

    open_tag_count = len(_POEM_OPEN_TAG_RE.findall(raw))
    if open_tag_count != len(blocks):
        warnings.warn(
            f"found {open_tag_count} <Poem> opening tag(s) but only recovered "
            f"{len(blocks)} complete block(s) -- file may be truncated or corrupted"
        )

    poems = []
    for block in blocks:
        try:
            poem_el = ET.fromstring(_NS_WRAPPER_OPEN + block + _NS_WRAPPER_CLOSE)[0]
            poem = _poem_from_element(poem_el)
        except (ET.ParseError, AttributeError) as e:
            warnings.warn(f"malformed <Poem> block skipped (id={_extract_poem_id(block)}): {e}")
            continue
        poems.append(poem)
    return poems


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


def _poem_to_xml(poem: Poem) -> str:
    theme_xml = "".join(
        f'<Theme category="{t.category}" basis="{t.basis}" evidence="{t.evidence}">{t.label_ko}</Theme>'
        for t in poem.themes
    )
    lines_xml = _lines_to_xml(poem.lines)
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

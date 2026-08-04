import re
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

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
        else:
            # <Couplet>(우리 파이프라인이 쓰는 이름) 외에도, 원본 19개 문집 데이터는
            # 동일한 위치에 <quatrain> 같은 이름으로 구를 묶어둔다(1차 자동태깅의
            # 잔재로 추정). 태그 이름과 무관하게 안의 <Line>은 절대 잃어버리지
            # 않는다. 다만 in_couplet=True는 우리 자신이 쓴 <Couplet>에서만 상속하고,
            # 그 외 원본 래퍼는 검증되지 않은 위치 정보이므로 False로 둔다 -- 최종
            # 대장 판정은 항상 Task 7의 LLM 재판단(classify_form_couplet_theme)이
            # 새로 내린다.
            inherited_in_couplet = child.tag == "Couplet"
            for line_el in child.findall("Line"):
                lines.append(
                    Line(
                        id=line_el.get("id"),
                        order=int(line_el.get("order")),
                        content_xml=_inner_xml(line_el),
                        in_couplet=inherited_in_couplet,
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


# 주의: title_xml/content_xml은 <term>/<d>/<rhyme>(및 원본에 실려온 그 밖의
# 요소) 하위 마크업을 문자열 그대로 보존하는 XML 조각이므로 여기서는 절대
# escape()하지 않는다 -- escape하면 태그 자체가 텍스트로 깨진다. escape/quoteattr
# 대상은 LLM이 생성했거나 그 외 임의 문자열이 들어올 수 있는 순수 텍스트/속성값
# 필드(ThemeTag의 각 필드, preface/annotation/context, basetype/detailtype 등)로
# 한정한다.
def _lines_to_xml(lines: list) -> str:
    out = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.in_couplet and i + 1 < len(lines) and lines[i + 1].in_couplet:
            partner = lines[i + 1]
            out.append(
                f'<Couplet><Line id={quoteattr(ln.id)} order="{ln.order}">{ln.content_xml}</Line>'
                f'<Line id={quoteattr(partner.id)} order="{partner.order}">{partner.content_xml}</Line></Couplet>'
            )
            i += 2
        else:
            out.append(f'<Line id={quoteattr(ln.id)} order="{ln.order}">{ln.content_xml}</Line>')
            i += 1
    return "".join(out)


def _poem_to_xml(poem: Poem) -> str:
    theme_xml = "".join(
        f'<Theme category={quoteattr(t.category)} basis={quoteattr(t.basis)} '
        f'evidence={quoteattr(t.evidence)}>{escape(t.label_ko)}</Theme>'
        for t in poem.themes
    )
    lines_xml = _lines_to_xml(poem.lines)
    return (
        f"<Poem id={quoteattr(poem.id)}>"
        f"<Metadata>"
        f"<Title>{poem.title_xml}</Title>"
        f"<Preface>{escape(poem.preface)}</Preface>"
        f"<Annotation>{escape(poem.annotation)}</Annotation>"
        f"<Collection ns0:href={quoteattr(poem.collection_href)}/>"
        f"<Author ns0:href={quoteattr(poem.author_href)}/>"
        f"<Form>"
        f"<Basetype>{escape(poem.basetype)}</Basetype>"
        f"<Detailtype>{escape(poem.detailtype)}</Detailtype>"
        f"<Charactercount>{escape(poem.charactercount)}</Charactercount>"
        f"</Form>"
        f"<Themes>{theme_xml}</Themes>"
        f"<Context>{escape(poem.context)}</Context>"
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

from dataclasses import dataclass, field


@dataclass
class ThemeTag:
    category: str
    basis: str
    evidence: str
    label_ko: str


@dataclass
class Line:
    """content_xml preserves <term>/<d>/<rhyme> sub-tags as a raw string.
    Later stages (term_classify, couplet) re-parse and rewrite this string.
    """

    id: str
    order: int
    content_xml: str
    in_couplet: bool = False


@dataclass
class Poem:
    """title_xml preserves <term>/<d>/<rhyme> sub-tags as a raw string,
    same as Line.content_xml.
    """

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

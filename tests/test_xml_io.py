from pathlib import Path

import pytest

from src.xml_io import parse_collection, write_collection

FIXTURE = Path(__file__).parent / "fixtures" / "sample_poems.txt"

_MALFORMED_MIDDLE_POEM = """\
  <Poem id="P001">
    <Metadata>
      <Title>春望</Title>
      <Preface></Preface>
      <Annotation></Annotation>
      <Collection ns0:href="glossary.xml#test"/>
      <Author ns0:href="glossary.xml#test"/>
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
      <Line id="P00101" order="1">國破山河在</Line>
    </text>
  </Poem>
  <Poem id="P002">
    <Metadata>
      <Title><d>成佛菴</d>邀<d>靜老</d>話</term></Title>
      <Preface></Preface>
      <Annotation></Annotation>
      <Collection ns0:href="glossary.xml#test"/>
      <Author ns0:href="glossary.xml#test"/>
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
      <Line id="P00201" order="1">城春草木深</Line>
    </text>
  </Poem>
  <Poem id="P003">
    <Metadata>
      <Title>春夜喜雨</Title>
      <Preface></Preface>
      <Annotation></Annotation>
      <Collection ns0:href="glossary.xml#test"/>
      <Author ns0:href="glossary.xml#test"/>
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
      <Line id="P00301" order="1">好雨知時節</Line>
    </text>
  </Poem>
"""


def test_parse_collection_skips_malformed_poem_and_warns(tmp_path):
    """A malformed <Poem> block (stray unmatched closing tag, mirroring the real
    임백호집 corpus's occasional hand-annotation typos) must not crash parsing of
    the whole file. It should be skipped with a visible warning, while the
    well-formed poems before and after it still parse correctly and in order.
    """
    path = tmp_path / "malformed.txt"
    path.write_text(_MALFORMED_MIDDLE_POEM, encoding="utf-8")

    with pytest.warns(UserWarning, match="P002"):
        poems = parse_collection(path)

    assert len(poems) == 2
    assert [p.id for p in poems] == ["P001", "P003"]


_MISSING_METADATA_MIDDLE_POEM = """\
  <Poem id="P001">
    <Metadata>
      <Title>春望</Title>
      <Preface></Preface>
      <Annotation></Annotation>
      <Collection ns0:href="glossary.xml#test"/>
      <Author ns0:href="glossary.xml#test"/>
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
      <Line id="P00101" order="1">國破山河在</Line>
    </text>
  </Poem>
  <Poem id="P002"></Poem>
  <Poem id="P003">
    <Metadata>
      <Title>春夜喜雨</Title>
      <Preface></Preface>
      <Annotation></Annotation>
      <Collection ns0:href="glossary.xml#test"/>
      <Author ns0:href="glossary.xml#test"/>
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
      <Line id="P00301" order="1">好雨知時節</Line>
    </text>
  </Poem>
"""


def test_parse_collection_skips_poem_missing_metadata_and_warns(tmp_path):
    """A <Poem> block that's well-formed XML but missing required child elements
    (here <Metadata> entirely) parses fine via ET.fromstring but then crashes
    _poem_from_element with AttributeError on meta.find(...) since meta is None.
    That must be caught and skipped like a ParseError, not left to crash the
    whole parse_collection call.
    """
    path = tmp_path / "missing_metadata.txt"
    path.write_text(_MISSING_METADATA_MIDDLE_POEM, encoding="utf-8")

    with pytest.warns(UserWarning, match="P002"):
        poems = parse_collection(path)

    assert len(poems) == 2
    assert [p.id for p in poems] == ["P001", "P003"]


def test_parse_collection_warns_on_truncated_trailing_poem(tmp_path):
    """A file truncated mid-poem (missing closing </Poem>, e.g. cut off at EOF)
    means the block regex won't match that fragment at all -- it must not be
    silently dropped. parse_collection should still return the complete, valid
    poems that precede it, and emit a warning flagging the <Poem>-tag-count vs.
    recovered-block-count mismatch so the truncation is visible.
    """
    path = tmp_path / "truncated.txt"
    truncated = (
        "  <Poem id=\"P001\">\n"
        "    <Metadata>\n"
        "      <Title>春望</Title>\n"
        "      <Preface></Preface>\n"
        "      <Annotation></Annotation>\n"
        "      <Collection ns0:href=\"glossary.xml#test\"/>\n"
        "      <Author ns0:href=\"glossary.xml#test\"/>\n"
        "      <Form>\n"
        "        <Basetype></Basetype>\n"
        "        <Detailtype></Detailtype>\n"
        "        <Charactercount>오언</Charactercount>\n"
        "    </Form>\n"
        "      <Themes>\n"
        "        <Main></Main>\n"
        "        <Sub></Sub>\n"
        "      </Themes>\n"
        "      <Context></Context>\n"
        "    </Metadata>\n"
        "    <text>\n"
        "      <Line id=\"P00101\" order=\"1\">國破山河在</Line>\n"
        "    </text>\n"
        "  </Poem>\n"
        '  <Poem id="P002">\n'
        "    <Metadata>\n"
        "      <Title>殘篇"
    )
    path.write_text(truncated, encoding="utf-8")

    with pytest.warns(UserWarning, match=r"2 <Poem> opening tag\(s\).*1 complete block\(s\)"):
        poems = parse_collection(path)

    assert len(poems) == 1
    assert poems[0].id == "P001"


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


def test_write_collection_wraps_couplet_lines(tmp_path):
    from src.poem_model import Line, Poem

    poem = Poem(
        id="P1",
        lines=[
            Line(id="L1", order=1, content_xml="字"),
            Line(id="L2", order=2, content_xml="字"),
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


def test_parse_collection_recovers_couplet_wrapped_lines(tmp_path):
    """<Couplet>-wrapped lines are grandchildren of <text>, not direct children.
    parse_collection must still recover them (correct count, order, ids) on round-trip,
    otherwise resuming a pipeline run from a written output file silently drops lines.
    """
    from src.poem_model import Line, Poem

    poem = Poem(
        id="P1",
        lines=[
            Line(id="L1", order=1, content_xml="字"),
            Line(id="L2", order=2, content_xml="字", in_couplet=True),
            Line(id="L3", order=3, content_xml="字", in_couplet=True),
            Line(id="L4", order=4, content_xml="字"),
        ],
    )
    out_path = tmp_path / "out.xml"
    write_collection(out_path, [poem])

    reparsed = parse_collection(out_path)
    assert len(reparsed[0].lines) == 4
    assert [ln.id for ln in reparsed[0].lines] == ["L1", "L2", "L3", "L4"]
    assert [ln.order for ln in reparsed[0].lines] == [1, 2, 3, 4]


def test_parse_collection_recovers_couplet_flag(tmp_path):
    """Content survival alone isn't enough: lines nested inside <Couplet> must come
    back with in_couplet=True, and lines outside it with in_couplet=False, otherwise
    a poem that gets written and re-parsed (e.g. via pipeline resume) loses its
    Couplet/대장 tagging on the very next write, since write_collection only wraps
    lines whose in_couplet flag is set.
    """
    from src.poem_model import Line, Poem

    poem = Poem(
        id="P1",
        lines=[
            Line(id="L1", order=1, content_xml="字"),
            Line(id="L2", order=2, content_xml="字", in_couplet=True),
            Line(id="L3", order=3, content_xml="字", in_couplet=True),
            Line(id="L4", order=4, content_xml="字"),
        ],
    )
    out_path = tmp_path / "out.xml"
    write_collection(out_path, [poem])

    reparsed = parse_collection(out_path)
    reparsed_lines = {ln.id: ln for ln in reparsed[0].lines}
    assert reparsed_lines["L1"].in_couplet is False
    assert reparsed_lines["L2"].in_couplet is True
    assert reparsed_lines["L3"].in_couplet is True
    assert reparsed_lines["L4"].in_couplet is False

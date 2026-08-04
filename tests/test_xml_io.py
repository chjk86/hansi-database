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

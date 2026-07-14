"""Shared helpers for the frontier-poem (변새시) classification pipeline."""
import re

TAG_RE = re.compile(r"<[^>]+>")


def parse_gold_poems(gold_path):
    """Parse the hand-annotated gold XML file into a list of raw <Poem>...</Poem> blocks."""
    text = open(gold_path, encoding="utf-8").read()
    return re.findall(r'<Poem id="[^"]*">.*?</Poem>', text, re.S)


def poem_id(poem_block):
    return re.search(r'<Poem id="([^"]*)"', poem_block).group(1)


def title_plain(poem_block):
    m = re.search(r"<Title>(.*?)</Title>", poem_block, re.S)
    return TAG_RE.sub("", m.group(1)) if m else ""


def body_plain(poem_block):
    m = re.search(r"<text>(.*?)</text>", poem_block, re.S)
    return TAG_RE.sub("", m.group(1)) if m else ""


def full_plain(poem_block):
    return title_plain(poem_block) + body_plain(poem_block)


def theme_categories(poem_block):
    return [c.lower() for c in re.findall(r'<Theme category="([^"]*)"', poem_block)]


def is_frontier(poem_block):
    return "frontier" in theme_categories(poem_block)


def author_of(poem_block):
    m = re.search(r'Author ns0:href="glossary\.xml#([^"]*)"', poem_block)
    return m.group(1) if m else None


def load_collection(path):
    """Load a `<title>...</title>,<text>...</text>` per-line collection file.

    Returns a list of (title, body) tuples.
    """
    out = []
    for line in open(path, encoding="utf-8").read().splitlines():
        m = re.match(r"<title>(.*?)</title>,<text>(.*?)</text>", line)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


# The 12 collections that overlap with the gold-standard frontier data (author -> filename
# inside hansi-database/2025_munzip_title_text_ver/). Six of the twenty originally-requested
# collection titles existed as duplicates under different accession numbers; these are the
# numbers the author confirmed as correct.
AUTHOR_FILE = {
    "최경창": "0216.고죽유고.txt",
    "박상": "0104.눌재집.txt",
    "정두경": "0349.동명집.txt",
    "권필": "0294.석주집.txt",
    "유몽인": "0265.어우집.txt",
    "차천로": "0258.오산집.txt",
    "백광훈": "0206.옥봉집.txt",
    "이행": "0109.용재집.txt",
    "임제": "0243.임백호집.txt",
    "이수광": "0273.지봉집.txt",
    "황정욱": "0192.지천집.txt",
    "조위한": "0288.현곡집.txt",
}

# Eight additional collections gathered for later corpus-wide expansion (no gold labels yet).
EXTRA_COLLECTION_FILE = {
    "기재집": "0116.기재집.txt",
    "동악집": "0300.동악집.txt",
    "성소부부고": "0292.성소부부고.txt",
    "소재집": "0159.소재집.txt",
    "손곡시집": "0254.손곡시집.txt",
    "읍취헌유고": "0110.읍취헌유고.txt",
    "현주집": "0303.현주집.txt",
    "호음잡고": "0126.호음잡고.txt",
}

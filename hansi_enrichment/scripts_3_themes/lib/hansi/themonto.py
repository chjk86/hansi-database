"""주제(Themes) 시소러스·후보 스코어링.

골드 <Theme category basis evidence> 에서 category별 title어/term어 가중치 추출.
새 시에 대해 title·본문 시어로 category 후보를 점수화.
"""
from __future__ import annotations
import re
import math
import collections
from . import xmlpoem as X

CATS = ["mountain", "water", "astro", "season", "animal", "plant", "travel",
        "donate", "farewell", "meet", "sympathy", "reminiscence", "frontier",
        "desire", "dream", "prosper", "tranquility", "banquet", "person",
        "taoism", "buddhism", "structure", "object", "literature", "picture", "others"]


def parse_gold_themes(raw: str):
    """[(cat, basis, {'title':[..], 'term':[..]})]"""
    m = re.search(r"<Themes>(.*?)</Themes>", raw, re.S)
    out = []
    if not m:
        return out
    for tm in re.finditer(
        r'<Theme category="([a-z_]+)"\s+basis="([^"]*)"\s+evidence="([^"]*)"\s*>([^<]*)</Theme>',
        m.group(1),
    ):
        cat, basis, ev, _label = tm.groups()
        d = {"title": [], "term": []}
        for part in re.findall(r'title:([^,]*)', ev):
            d["title"] += part.split()
        for part in re.findall(r'term:(.*?)(?:,\s*title:|$)', ev):
            d["term"] += part.split()
        out.append((cat, basis, d))
    return out


def poem_title(raw: str) -> str:
    return X.hanja_only(X.strip_tags(X.get_field(raw, "Title") or ""))


def poem_terms(raw: str) -> list[str]:
    terms = []
    for _, inner, _ in X.lines(raw):
        for mm in re.finditer(r"<(term|d)>(.*?)</\1>", inner, re.S):
            w = X.hanja_only(X.strip_tags(mm.group(2)))
            if w:
                terms.append(w)
    return terms


def poem_text(raw: str) -> str:
    return "".join(h for _, _, h in X.lines(raw))


class Thesaurus:
    def __init__(self):
        self.title_w = collections.defaultdict(lambda: collections.Counter())  # cat -> word -> df
        self.term_w = collections.defaultdict(lambda: collections.Counter())
        self.cat_freq = collections.Counter()
        self.n = 0
        self._title_df = collections.Counter()   # word -> #cats
        self._term_df = collections.Counter()

    def fit(self, poems_raw: list[str]):
        for raw in poems_raw:
            self.n += 1
            for cat, basis, d in parse_gold_themes(raw):
                self.cat_freq[cat] += 1
                for w in set(d["title"]):
                    self.title_w[cat][w] += 1
                for w in set(d["term"]):
                    self.term_w[cat][w] += 1
        for cat in self.title_w:
            for w in self.title_w[cat]:
                self._title_df[w] += 1
        for cat in self.term_w:
            for w in self.term_w[cat]:
                self._term_df[w] += 1
        return self

    def _score_words(self, words: set[str], table, df, kind: str):
        sc = collections.Counter()
        for cat in CATS:
            t = table.get(cat)
            if not t:
                continue
            s = 0.0
            for w in words:
                if w in t:
                    # 특이도 가중: 여러 category에 걸친 어휘는 감점
                    idf = math.log(1 + 26 / (1 + df.get(w, 0)))
                    s += t[w] * idf
            if s:
                sc[cat] = s
        return sc

    def score(self, raw: str) -> collections.Counter:
        title_ws = set(_ngrams(poem_title(raw)))
        term_ws = set(poem_terms(raw))
        # 본문 2-gram도 보조 (시소러스에 있는 것만)
        text_ws = set(_ngrams(poem_text(raw), 2))
        sc = collections.Counter()
        for c, v in self._score_words(title_ws, self.title_w, self._title_df, "title").items():
            sc[c] += v * 3.0
        for c, v in self._score_words(term_ws, self.term_w, self._term_df, "term").items():
            sc[c] += v * 1.5
        for c, v in self._score_words(text_ws, self.term_w, self._term_df, "text").items():
            sc[c] += v * 0.3
        return sc

    def evidence_for(self, raw: str, cat: str):
        title_ws = set(_ngrams(poem_title(raw)))
        term_ws = set(poem_terms(raw))
        t_hit = [w for w in title_ws if w in self.title_w.get(cat, {})]
        m_hit = [w for w in term_ws if w in self.term_w.get(cat, {})]
        return t_hit, m_hit


def _ngrams(s: str, nmax: int = 3):
    out = list(s)
    for k in (2, 3):
        if k > nmax:
            break
        out += [s[i:i+k] for i in range(len(s) - k + 1)]
    return out

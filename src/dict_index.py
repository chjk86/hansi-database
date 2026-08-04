import pickle
import re
from pathlib import Path

_SINGLE_PATTERN = re.compile(r"^\*(.+?)\d*［")
_MULTI_PATTERN = re.compile(r"^【([^】]+)】")


class DictIndex:
    def __init__(self, headwords: set[str]):
        self._headwords = headwords
        self.max_word_length = max((len(w) for w in headwords), default=0)

    @classmethod
    def build(cls, path: Path) -> "DictIndex":
        headwords: set[str] = set()
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("*"):
                    m = _SINGLE_PATTERN.match(line)
                    if m:
                        headwords.add(m.group(1))
                elif line.startswith("【"):
                    m = _MULTI_PATTERN.match(line)
                    if m:
                        headwords.add(m.group(1))
        return cls(headwords)

    def contains(self, word: str) -> bool:
        return word in self._headwords

    def save(self, cache_path: Path) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(self._headwords, f)

    @classmethod
    def load(cls, cache_path: Path) -> "DictIndex":
        with open(cache_path, "rb") as f:
            headwords = pickle.load(f)
        return cls(headwords)

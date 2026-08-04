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
        try:
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
        except FileNotFoundError:
            raise FileNotFoundError(f"한어대사전 파일을 찾을 수 없습니다: {path}")
        return cls(headwords)

    def contains(self, word: str) -> bool:
        return word in self._headwords

    def save(self, cache_path: Path) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(self._headwords, f)

    @classmethod
    def load(cls, cache_path: Path) -> "DictIndex":
        try:
            with open(cache_path, "rb") as f:
                headwords = pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError, EOFError) as e:
            raise RuntimeError(
                f"캐시 파일을 읽을 수 없습니다: {cache_path}\n"
                f"캐시 파일을 삭제한 후 다시 빌드해주세요.\n"
                f"원인: {type(e).__name__}: {e}"
            )
        return cls(headwords)

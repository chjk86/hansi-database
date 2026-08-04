from src import config
from src.dict_index import DictIndex

if __name__ == "__main__":
    idx = DictIndex.build(config.DICT_PATH)
    cache_path = config.CACHE_DIR / "dict_index.pkl"
    idx.save(cache_path)
    print(f"headwords built, max_word_length={idx.max_word_length}, cached at {cache_path}")

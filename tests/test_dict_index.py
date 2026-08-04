from pathlib import Path
from src.dict_index import DictIndex

FIXTURE = Path(__file__).parent / "fixtures" / "sample_dict.txt"


def test_single_char_headword_registered():
    idx = DictIndex.build(FIXTURE)
    assert idx.contains("衣")


def test_multi_char_headword_registered():
    idx = DictIndex.build(FIXTURE)
    assert idx.contains("草衣")
    assert idx.contains("長安")
    assert idx.contains("一一")


def test_unregistered_word_not_found():
    idx = DictIndex.build(FIXTURE)
    assert not idx.contains("草木衣裳")
    assert not idx.contains("不存在")


def test_max_word_length_tracks_longest_entry():
    idx = DictIndex.build(FIXTURE)
    assert idx.max_word_length == 7  # "一寸光陰一寸金" 는 7글자


def test_save_and_load_roundtrip(tmp_path):
    idx = DictIndex.build(FIXTURE)
    cache_path = tmp_path / "dict_index.pkl"
    idx.save(cache_path)
    loaded = DictIndex.load(cache_path)
    assert loaded.contains("草衣")
    assert loaded.max_word_length == idx.max_word_length

from pathlib import Path
from src import config


def test_paths_are_under_root():
    assert config.ROOT_DIR.is_dir()
    assert config.DICT_PATH == config.ROOT_DIR / "한어대사전.txt"
    assert config.GOLD_PATH == config.ROOT_DIR / "임백호집_3차완본_20260730.txt"
    assert config.OUTPUT_DIR == config.ROOT_DIR / "output"
    assert config.QA_DIR == config.ROOT_DIR / "qa"


def test_default_model_name():
    assert config.LLM_MODEL == "gemini-2.5-flash"

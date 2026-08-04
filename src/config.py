import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DICT_PATH = ROOT_DIR / "한어대사전.txt"
GOLD_PATH = ROOT_DIR / "임백호집_3차완본_20260730.txt"
EXTRACTED_DIR = ROOT_DIR / "extracted" / "대상데이터_제목내용시어운자대장태그"
OUTPUT_DIR = ROOT_DIR / "output"
QA_DIR = ROOT_DIR / "qa"
LOGS_DIR = ROOT_DIR / "logs"
CACHE_DIR = ROOT_DIR / ".cache"

LLM_MODEL = os.environ.get("HANSHI_LLM_MODEL", "gemini-flash-latest")

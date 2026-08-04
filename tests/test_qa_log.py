import csv

from src.qa_log import QALog


def test_write_csv_produces_expected_rows(tmp_path):
    log = QALog()
    log.add(poem_id="P1", collection="지천집", item="Theme", reason="근거 빈약")
    log.add(poem_id="P2", collection="지천집", item="Couplet", reason="판단 유보")

    out_path = tmp_path / "log.csv"
    log.write_csv(out_path)

    with open(out_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    assert rows[0]["poem_id"] == "P1"
    assert rows[0]["item"] == "Theme"
    assert rows[1]["reason"] == "판단 유보"


def test_empty_log_still_writes_header(tmp_path):
    log = QALog()
    out_path = tmp_path / "log.csv"
    log.write_csv(out_path)

    with open(out_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows == []

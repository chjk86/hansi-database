import csv
from pathlib import Path


class QALog:
    _FIELDS = ["poem_id", "collection", "item", "reason"]

    def __init__(self):
        self._rows: list[dict] = []

    def add(self, poem_id: str, collection: str, item: str, reason: str) -> None:
        self._rows.append(
            {"poem_id": poem_id, "collection": collection, "item": item, "reason": reason}
        )

    def write_csv(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self._FIELDS)
            writer.writeheader()
            writer.writerows(self._rows)

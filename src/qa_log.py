import csv
from pathlib import Path


class QALog:
    _FIELDS = ["poem_id", "collection", "item", "reason"]

    def __init__(self, rows: list[dict] | None = None):
        self._rows: list[dict] = list(rows) if rows is not None else []

    def add(self, poem_id: str, collection: str, item: str, reason: str) -> None:
        self._rows.append(
            {"poem_id": poem_id, "collection": collection, "item": item, "reason": reason}
        )

    def has_entry(self, poem_id: str, item: str) -> bool:
        """poem_id/item 조합의 행이 이미 기록돼 있는지 확인한다. 인터럽트된
        실행을 재개할 때(load_csv로 이전 실행분을 이어받은 경우) 동일한 원인으로
        매번 재발생하는 플래그(예: 항상 파싱에 실패하는 시)를 재실행마다
        중복 기록하지 않기 위한 헬퍼."""
        return any(row["poem_id"] == poem_id and row["item"] == item for row in self._rows)

    def write_csv(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self._FIELDS)
            writer.writeheader()
            writer.writerows(self._rows)

    @classmethod
    def load_csv(cls, path: Path) -> "QALog":
        """이전 실행이 남긴 QA csv를 읽어 그 행들을 이어받은 QALog를 만든다.
        인터럽트된 실행을 재개할 때, 이미 체크포인트된(다시 처리되지 않는) 시들의
        QA 플래그가 새 실행에서 빈 로그로 덮어써져 사라지지 않도록 한다."""
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = [{field: row.get(field, "") for field in cls._FIELDS} for row in reader]
        return cls(rows)

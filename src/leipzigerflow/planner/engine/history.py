from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from leipzigerflow.config.settings import DATA_DIR


@dataclass(slots=True)
class DecisionHistoryEntry:
    created_at: datetime
    order_id: int
    order_number: str
    selected_vehicle_id: int | None
    selected_vehicle_label: str
    selected_score: int
    confidence_percent: int
    decision: str
    reasons: list[str] = field(default_factory=list)
    rejected_alternatives: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


class DecisionHistoryStore:
    """Append-only JSONL-Protokoll für nachvollziehbare Dispositionsentscheidungen."""

    def __init__(self, path: Path | None = None):
        self.path = path or DATA_DIR / "dispatch_decisions.jsonl"

    def append(self, entry: DecisionHistoryEntry) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_json_dict(), ensure_ascii=False) + "\n")

    def read(self, limit: int | None = None) -> list[DecisionHistoryEntry]:
        if not self.path.exists():
            return []
        entries: list[DecisionHistoryEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                raw = json.loads(line)
                raw["created_at"] = datetime.fromisoformat(raw["created_at"])
                entries.append(DecisionHistoryEntry(**raw))
            except (ValueError, TypeError, json.JSONDecodeError, KeyError):
                continue
        return entries[-limit:] if limit is not None else entries

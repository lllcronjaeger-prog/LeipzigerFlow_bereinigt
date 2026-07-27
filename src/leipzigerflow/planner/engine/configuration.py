from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from leipzigerflow.config.settings import DATA_DIR
from leipzigerflow.planner.engine.models import DispatchWeights


class DispatchConfigurationStore:
    """Speichert die Gewichtungen ohne Datenbankmigration als JSON."""

    def __init__(self, path: Path | None = None):
        self.path = path or DATA_DIR / "dispatch_weights.json"

    def load(self) -> DispatchWeights:
        if not self.path.exists():
            return DispatchWeights()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = DispatchWeights.__dataclass_fields__
            values = {key: int(value) for key, value in data.items() if key in allowed}
            return DispatchWeights(**values)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return DispatchWeights()

    def save(self, weights: DispatchWeights) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(weights), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

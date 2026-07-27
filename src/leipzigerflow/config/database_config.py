from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from leipzigerflow.config.settings import DATA_DIR, DATABASE_FILE

CONFIG_FILE = DATA_DIR / "database_connection.json"


@dataclass(slots=True)
class DatabaseConfig:
    mode: str = "sqlite"
    sqlite_file: str = str(DATABASE_FILE)
    host: str = "localhost"
    port: int = 5432
    database: str = "leipzigerflow"
    username: str = "leipzigerflow_client"
    password: str = ""
    document_root: str = str(DATA_DIR / "documents")
    refresh_seconds: int = 3

    @property
    def url(self) -> str:
        if self.mode == "postgresql":
            from urllib.parse import quote_plus
            user = quote_plus(self.username)
            password = quote_plus(self.password)
            return f"postgresql+psycopg://{user}:{password}@{self.host}:{self.port}/{self.database}"
        path = Path(self.sqlite_file).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"


def load_database_config() -> DatabaseConfig:
    if not CONFIG_FILE.exists():
        return DatabaseConfig()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        allowed = DatabaseConfig.__dataclass_fields__.keys()
        return DatabaseConfig(**{key: value for key, value in data.items() if key in allowed})
    except (OSError, ValueError, TypeError):
        return DatabaseConfig()


def save_database_config(config: DatabaseConfig) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8")

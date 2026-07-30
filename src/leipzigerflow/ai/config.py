from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from leipzigerflow.config.settings import DATA_DIR

AI_CONFIG_FILE = DATA_DIR / "ai_config.json"

OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"
OLLAMA_DEFAULT_MODEL = "qwen3:4b"
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
OPENAI_DEFAULT_MODEL = "gpt-5-mini"


@dataclass(slots=True)
class AiConfig:
    """Konfiguration der optionalen KI-Anbindung.

    Ollama ist bewusst der Standard: Die Daten bleiben lokal und für die
    Nutzung ist weder ein Cloud-Konto noch ein API-Schlüssel erforderlich.
    """

    provider: str = "ollama"
    model: str = OLLAMA_DEFAULT_MODEL
    base_url: str = OLLAMA_DEFAULT_BASE_URL
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: int = 600
    max_context_records: int = 20
    enabled: bool = False


def provider_defaults(provider: str) -> tuple[str, str]:
    if provider == "openai":
        return OPENAI_DEFAULT_MODEL, OPENAI_DEFAULT_BASE_URL
    return OLLAMA_DEFAULT_MODEL, OLLAMA_DEFAULT_BASE_URL


def load_ai_config(path: Path = AI_CONFIG_FILE) -> AiConfig:
    if not path.exists():
        return AiConfig()
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AiConfig()
    allowed = AiConfig.__dataclass_fields__
    return AiConfig(**{key: value for key, value in values.items() if key in allowed})


def save_ai_config(config: AiConfig, path: Path = AI_CONFIG_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")

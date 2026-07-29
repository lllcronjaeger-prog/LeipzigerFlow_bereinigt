from pathlib import Path

from leipzigerflow.ai.config import (
    AiConfig,
    OLLAMA_DEFAULT_BASE_URL,
    OLLAMA_DEFAULT_MODEL,
    load_ai_config,
    provider_defaults,
    save_ai_config,
)


def test_ai_config_defaults_to_local_ollama():
    config = AiConfig()
    assert config.provider == "ollama"
    assert config.model == OLLAMA_DEFAULT_MODEL
    assert config.base_url == OLLAMA_DEFAULT_BASE_URL


def test_ai_config_roundtrip(tmp_path: Path):
    path = tmp_path / "ai.json"
    expected = AiConfig(
        provider="ollama",
        model="qwen3:4b",
        base_url="http://localhost:11434",
        enabled=True,
    )
    save_ai_config(expected, path)
    actual = load_ai_config(path)
    assert actual == expected


def test_invalid_ai_config_falls_back_to_defaults(tmp_path: Path):
    path = tmp_path / "ai.json"
    path.write_text("not json", encoding="utf-8")
    assert load_ai_config(path) == AiConfig()


def test_provider_defaults_are_available():
    assert provider_defaults("ollama") == ("qwen3:4b", "http://localhost:11434")
    assert provider_defaults("openai") == ("gpt-5-mini", "https://api.openai.com/v1")

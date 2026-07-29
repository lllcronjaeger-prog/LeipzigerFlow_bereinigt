from __future__ import annotations

import pytest

from leipzigerflow.ai.config import AiConfig
from leipzigerflow.ai.provider import AiProviderError, OllamaProvider, create_provider


def test_unknown_provider_is_rejected():
    with pytest.raises(AiProviderError, match="Unbekannter KI-Anbieter"):
        create_provider(AiConfig(provider="unbekannt"))


def test_ollama_missing_model_shows_pull_command(monkeypatch):
    provider = OllamaProvider(AiConfig(provider="ollama", model="qwen3:4b"))
    monkeypatch.setattr(provider, "installed_models", lambda: {"llama3.2:latest"})

    with pytest.raises(AiProviderError, match=r"ollama pull qwen3:4b"):
        provider.test_connection()


def test_ollama_accepts_latest_tag_for_untagged_model(monkeypatch):
    provider = OllamaProvider(AiConfig(provider="ollama", model="qwen3"))
    monkeypatch.setattr(provider, "installed_models", lambda: {"qwen3:latest"})
    provider.test_connection()

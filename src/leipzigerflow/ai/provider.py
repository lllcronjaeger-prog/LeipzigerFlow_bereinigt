from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import AiConfig


class AiProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AiMessage:
    role: str
    content: str


class AiProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[AiMessage]) -> str:
        raise NotImplementedError

    @abstractmethod
    def test_connection(self) -> None:
        raise NotImplementedError


class OpenAiProvider(AiProvider):
    def __init__(self, config: AiConfig):
        self.config = config

    def _api_key(self) -> str:
        key = os.getenv(self.config.api_key_env, "").strip()
        if not key or key.lower() in {"dein-api-schlüssel", "dein-api-schluessel"}:
            raise AiProviderError(
                f"Die Umgebungsvariable {self.config.api_key_env} enthält keinen gültigen API-Schlüssel."
            )
        return key

    def _request(self, path: str, payload: dict | None = None, *, method: str = "POST") -> dict:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._api_key()}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise AiProviderError(f"OpenAI-Fehler {exc.code}: {body[:500]}") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise AiProviderError(f"KI-Verbindung fehlgeschlagen: {exc}") from exc

    def complete(self, messages: list[AiMessage]) -> str:
        input_items = [
            {"role": message.role, "content": [{"type": "input_text", "text": message.content}]}
            for message in messages
        ]
        result = self._request(
            "responses",
            {"model": self.config.model, "input": input_items, "store": False},
        )
        text = result.get("output_text")
        if text:
            return str(text).strip()
        parts: list[str] = []
        for item in result.get("output", []):
            for content in item.get("content", []):
                value = content.get("text")
                if value:
                    parts.append(str(value))
        if not parts:
            raise AiProviderError("Die KI-Antwort enthielt keinen Text.")
        return "\n".join(parts).strip()

    def test_connection(self) -> None:
        self._request("models", method="GET")


class OllamaProvider(AiProvider):
    def __init__(self, config: AiConfig):
        self.config = config

    def _request(self, path: str, payload: dict | None = None, *, method: str = "GET") -> dict:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise AiProviderError(f"Ollama-Fehler {exc.code}: {body[:500]}") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise AiProviderError(
                "Ollama ist unter der eingetragenen Adresse nicht erreichbar. "
                "Bitte Ollama installieren bzw. starten und die Basis-URL prüfen. "
                f"Technische Meldung: {exc}"
            ) from exc

    def installed_models(self) -> set[str]:
        result = self._request("api/tags")
        models: set[str] = set()
        for item in result.get("models", []):
            name = str(item.get("name", "")).strip()
            model = str(item.get("model", "")).strip()
            if name:
                models.add(name)
            if model:
                models.add(model)
        return models

    def _ensure_model_installed(self) -> None:
        configured = self.config.model.strip()
        installed = self.installed_models()
        if configured in installed:
            return
        # Ollama ergänzt bei ungetaggten Modellen üblicherweise :latest.
        if ":" not in configured and f"{configured}:latest" in installed:
            return
        raise AiProviderError(
            f"Das Ollama-Modell '{configured}' ist noch nicht installiert.\n\n"
            f"Bitte in einer Eingabeaufforderung ausführen:\nollama pull {configured}"
        )

    def complete(self, messages: list[AiMessage]) -> str:
        self._ensure_model_installed()
        result = self._request(
            "api/chat",
            {
                "model": self.config.model,
                "stream": False,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
            },
            method="POST",
        )
        text = str(result.get("message", {}).get("content", "")).strip()
        if not text:
            raise AiProviderError("Ollama hat keine Textantwort geliefert.")
        return text

    def test_connection(self) -> None:
        self._ensure_model_installed()


def create_provider(config: AiConfig) -> AiProvider:
    if config.provider == "ollama":
        return OllamaProvider(config)
    if config.provider == "openai":
        return OpenAiProvider(config)
    raise AiProviderError(f"Unbekannter KI-Anbieter: {config.provider}")

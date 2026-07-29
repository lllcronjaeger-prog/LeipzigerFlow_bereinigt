from dataclasses import replace

import pytest

from leipzigerflow.ai.config import AiConfig
from leipzigerflow.ai.provider import AiMessage, AiProvider
from leipzigerflow.ai.service import AiService


class EmptyScalars:
    def all(self):
        return []


class EmptySession:
    def scalars(self, _statement):
        return EmptyScalars()


class StubProvider(AiProvider):
    def __init__(self):
        self.messages = []
        self.tested = False

    def complete(self, messages: list[AiMessage]) -> str:
        self.messages = messages
        return "Analyse abgeschlossen"

    def test_connection(self) -> None:
        self.tested = True


def test_ai_service_rejects_disabled_config():
    provider = StubProvider()
    service = AiService(EmptySession(), AiConfig(enabled=False), provider)
    with pytest.raises(RuntimeError):
        service.ask("Welche Tour ist kritisch?")


def test_ai_service_sends_read_only_prompt_and_question():
    provider = StubProvider()
    config = replace(AiConfig(), enabled=True)
    answer = AiService(EmptySession(), config, provider).ask("Welche Tour ist kritisch?")
    assert answer == "Analyse abgeschlossen"
    assert provider.messages[-1].content == "Welche Tour ist kritisch?"
    assert "keine Daten verändern" in provider.messages[0].content


def test_ai_service_tests_provider_connection():
    provider = StubProvider()
    service = AiService(EmptySession(), AiConfig(enabled=True), provider)
    service.test_connection()
    assert provider.tested is True

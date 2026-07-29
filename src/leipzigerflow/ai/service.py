from __future__ import annotations

from sqlalchemy.orm import Session

from .config import AiConfig, load_ai_config
from .context import AiContextBuilder
from .provider import AiMessage, AiProvider, create_provider

SYSTEM_PROMPT = """Du bist LeipzigerAI, ein deutschsprachiger Assistent für Disposition und Tourenplanung.
Nutze ausschließlich den bereitgestellten LeipzigerFlow-Kontext. Erfinde keine Datensätze.
Du darfst keine Daten verändern, keine Touren automatisch disponieren und keine Aktionen ausführen.
Formuliere konkrete, nachvollziehbare Analysen und kennzeichne Unsicherheiten klar.
Bei fehlenden Daten sage ausdrücklich, welche Information fehlt."""


class AiService:
    def __init__(self, session: Session, config: AiConfig | None = None, provider: AiProvider | None = None):
        self.session = session
        self.config = config or load_ai_config()
        self.provider = provider or create_provider(self.config)

    def ask(self, question: str, history: list[AiMessage] | None = None) -> str:
        question = question.strip()
        if not question:
            raise ValueError("Bitte eine Frage eingeben.")
        if not self.config.enabled:
            raise RuntimeError("Die KI-Anbindung ist in den Einstellungen nicht aktiviert.")
        context = AiContextBuilder(self.session, self.config.max_context_records).build()
        messages = [AiMessage("system", SYSTEM_PROMPT), AiMessage("system", context)]
        messages.extend((history or [])[-10:])
        messages.append(AiMessage("user", question))
        return self.provider.complete(messages)

    def test_connection(self) -> None:
        self.provider.test_connection()

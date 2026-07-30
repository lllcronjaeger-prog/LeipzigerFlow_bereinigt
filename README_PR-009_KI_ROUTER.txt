PR-009 – Schneller LeipzigerAI-Datenrouter

Änderungen:
- Eindeutige Faktenfragen werden direkt per SQL beantwortet.
- Ollama wird für einfache Zählfragen nicht mehr gestartet.
- Kontextabfragen verwenden SQL COUNT statt vollständige Tabellen zu laden.
- Höchstens 8 Detaildatensätze je relevantem Bereich.
- Gesamter KI-Kontext ist auf 5.000 Zeichen begrenzt.
- Ollama-Kontext auf 2.048 Token und Antwort auf 256 Token begrenzt.
- Denkmodus für Qwen3 deaktiviert und Modellhaltezeit auf 2 Minuten reduziert.
- Neue Tests für Router und Provider-Umgehung.

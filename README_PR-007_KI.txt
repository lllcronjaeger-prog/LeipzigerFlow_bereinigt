LeipzigerFlow – PR-007 KI-Grundsystem

Enthalten:
- Provider-Abstraktion für OpenAI und Ollama
- Read-only-Datenkontext aus Aufträgen, Touren und Ressourcen
- KI-Einstellungen mit Verbindungstest
- API-Key ausschließlich über Umgebungsvariable
- aktiver LeipzigerAI-Chatdialog
- Berechtigungen ai.use und api.manage
- keine automatischen Änderungen an Disposition oder Datenbestand

Einrichtung OpenAI:
1. Windows-Umgebungsvariable OPENAI_API_KEY setzen.
2. LeipzigerFlow neu starten.
3. KI > KI-Einstellungen öffnen.
4. OpenAI, Modell und Basis-URL prüfen.
5. Verbindung testen und KI aktivieren.

Einrichtung Ollama:
1. Ollama lokal starten.
2. Anbieter Ollama wählen.
3. Basis-URL z. B. http://localhost:11434 setzen.
4. Installiertes Modell eintragen.
5. Verbindung testen und KI aktivieren.

Teststand: 153 passed

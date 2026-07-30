LeipzigerFlow S1.3 – PR-008.1 KI-Stabilität und Streaming
==========================================================

Änderungen
----------
- Nur noch ein gemeinsamer Menüpunkt "LeipzigerAI – Dispositionsassistent".
- Touranalyse und Optimierung sind im Assistenten zusammengeführt.
- KI-Anfragen laufen in einem QThread; die Oberfläche bleibt bedienbar.
- Ollama-Antworten werden gestreamt und sofort im Dialog angezeigt.
- Abbrechen-Schaltfläche für laufende Anfragen.
- Fortschrittsanzeige und verständliche Statusmeldungen.
- Eigene Datenbank-Session im Worker-Thread.
- Frageabhängiger, verkleinerter Datenkontext.
- Standard-Timeout für lokale Generierung auf 600 Sekunden erhöht.
- Maximaler Kontext standardmäßig auf 20 Datensätze reduziert.
- Präzisere Meldungen für Erreichbarkeits- und Generierungs-Timeouts.

Installation
------------
ZIP über den aktuellen Projektordner entpacken.

Test
----
pytest -q

Erwartetes Ergebnis auf dem gelieferten Stand:
162 passed

Commit-Nachricht
----------------
S1.3 PR-008.1 KI-Streaming und Hintergrundverarbeitung integrieren

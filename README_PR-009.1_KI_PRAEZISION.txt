LeipzigerFlow S1.3 – PR-009.1 KI-Präzision
===========================================

Änderungen
----------
- Fachfragen zu offenen, geplanten, laufenden, abgeschlossenen und stornierten Touren
  werden direkt aus der Datenbank beantwortet.
- "Offen" ist verbindlich definiert als: nicht abgeschlossen, nicht erledigt und nicht storniert.
- Offene Touren werden mit Statusaufschlüsselung ausgegeben.
- Direkte Antworten für offene Touren ohne Fahrer oder ohne Fahrzeug.
- Direkte Antworten für freie Fahrzeuge und Trailer.
- Offene bzw. unverplante Transportaufträge werden über feste Statuswerte ermittelt.
- Strenger deutscher System-Prompt für Ollama.
- Keine internen Gedankengänge, englischen Zwischentexte oder Selbstgespräche.
- Qwen-Denkmodus zusätzlich über /no_think unterdrückt.

Teststand
---------
168 Tests erfolgreich.

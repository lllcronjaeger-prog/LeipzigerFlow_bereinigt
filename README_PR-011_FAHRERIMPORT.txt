PR-011.1 – Fahrerimport aus Dispoplan-Excel

- Unterstützt .xls und .xlsx
- Liest MatchCode, Anschrift und Kontakt
- Zerlegt Anschrift in Vorname, Nachname, Straße, Hausnummer, PLZ, Ort und Land
- Liest Telefonnummern aus Kontakt; Fallback aus Sonderberechtigungen bei "Tel."
- LMK Führung wird ignoriert
- Alle importierten Fahrer werden aktiv gesetzt
- Vorhandene Fahrer werden über den MatchCode aktualisiert
- Vorschau mit Korrekturmöglichkeit vor dem Import
- Aufruf über "Import / Export" oder die Fahrerverwaltung

Hinweis: Für .xls wird xlrd verwendet und über pyproject.toml installiert.

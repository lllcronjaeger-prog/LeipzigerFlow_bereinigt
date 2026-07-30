PR-011.3 – Kundenimport und Fahrer-Abwesenheiten

Kundenimport:
- Import / Export > Kunden aus Excel importieren
- Unterstützt .xls und .xlsx
- Übernimmt Name, MatchCode und Anschrift
- Verknüpft Hauptkunde als Frachtzahler
- Aktualisiert vorhandene Kunden anhand des MatchCodes

Fahrer-Abwesenheiten:
- Fahrer bearbeiten > Reiter Geplante Abwesenheiten
- Mehrere Zeiträume können hinzugefügt, bearbeitet und entfernt werden
- Zeitraum, Grund, Bemerkung und Aktiv-Status werden gespeichert

Test: pytest -q
Erwartet: 182 passed

PR-011.4 – Kundenstamm als Kunden und Standorte importieren

- Hauptkunde wird als Kunde/Frachtzahler angelegt oder aktualisiert.
- Jede Excel-Zeile wird als Kundenstandort importiert.
- Standorte werden eindeutig dem Kunden zugeordnet.
- Wiederholte Importe aktualisieren statt zu duplizieren.
- Gleiche MatchCodes an unterschiedlichen Anschriften bleiben getrennte Standorte.
- Gleiche Anschriften mit mehreren MatchCodes werden als ein Standort erkannt; weitere Codes werden als Aliases gespeichert.
- Unicode-/Umlaut-MatchCodes werden zuverlässig erkannt.
- Standortverwaltung zeigt den zugehörigen Kunden und erlaubt die manuelle Zuordnung.
- Schema-Migration ergänzt locations.customer_id automatisch.

Version: 2026.20.2
Tests: 185 bestanden
Echte Testdateien: Kunde Cola(1).xlsx und Kunde Cola 2.xlsx erfolgreich geprüft.

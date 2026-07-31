# PR-017.0a – Plantafel-Performance und Storno-Schutz

## Änderungen

- Die Plantafel lädt nur noch Touren des sichtbaren Tages, der sichtbaren Woche oder des sichtbaren Monats.
- Nicht disponierte Aufträge werden direkt für den ausgewählten Tag abgefragt.
- Die historische Bereinigung doppelter Fahrzeugtouren läuft je geöffnetem Plantafelfenster nur einmal statt bei jedem automatischen Refresh.
- Die automatische Abschlussprüfung wird auf den sichtbaren Zeitraum begrenzt.
- Aktive Dispositionsimportregeln werden unmittelbar vor dem tatsächlichen Import erneut ausgewertet.
- `STORNO LAUT KUNDE` wird dadurch auch dann sicher übersprungen, wenn die Vorschau nicht ausgeführt oder zwischen Vorschau und Import verändert wurde.

## Datenbank

Keine Migration erforderlich.

## Tests

204 Tests bestanden.

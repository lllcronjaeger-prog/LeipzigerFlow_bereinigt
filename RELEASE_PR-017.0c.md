# PR-017.0c – Import-Stabilität, Storno und Fahrergruppen

## Import und SQLite-Stabilität

- Der Dispositionsimport löst keine Routing- oder Geocodingberechnung mehr aus.
- Fahrerabschnitte werden während des Imports aus den vorhandenen Lade-/Entladezeiten gebildet.
- Stammfahrer und Stammtrailer werden ohne Aufruf der Online-Routenplanung übernommen.
- Damit entfällt der konkurrierende Schreibzugriff auf `geocode_cache`, der zu `sqlite3.OperationalError: database is locked` geführt hat.

## Storno laut Kunde

- `STORNO LAUT KUNDE` wird robust in allen relevanten Importfeldern erkannt.
- Die Prüfung erfolgt vor dem Anlegen von Kunden, Standorten, Aufträgen und Touren.
- Bereits früher importierte Aufträge werden bei einem späteren Storno-Import einschließlich ihrer Tourposition entfernt.

## Plantafel

- Beim Aufbau der Plantafel wird kein Online-Routing mehr für jede Tourkarte gestartet.
- Entfernungen werden erst in einer gezielten Detail- oder Planungsaktion berechnet.
- Die Fahrerauswahl zeigt bei vorhandener Dispositionsgruppe standardmäßig nur Fahrer dieser Gruppe.
- Bereits zugeordnete Fahrer bleiben auch bei abweichender Gruppenzuordnung auswählbar.

## Tests

- 208 Tests erfolgreich.

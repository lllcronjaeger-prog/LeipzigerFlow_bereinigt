# PR-017.0b – Plantafel-Performance

## Änderungen

- Touren werden für die Plantafel nur noch für den aktuell sichtbaren Tag, die sichtbare Woche oder den sichtbaren Monat geladen.
- Die automatische Abschlussprüfung wird auf den sichtbaren Zeitraum begrenzt.
- Nicht disponierte Aufträge werden direkt für den ausgewählten Tag aus der Datenbank geladen, statt zunächst den gesamten Bestand zu laden und anschließend in Python zu filtern.
- Die Bereinigung historischer doppelter Fahrzeugtouren wird beim Öffnen der Plantafel nur einmal ausgeführt und nicht mehr bei jedem Refresh.
- Die bereits vorhandenen Eager-Loading-Beziehungen für Fahrer, Fahrzeug, Trailer, Fahrerabschnitte, Aufträge, Kunden sowie Lade- und Entladestellen bleiben erhalten.

## Wirkung

Die Datenmenge pro Plantafel-Refresh wird deutlich reduziert. Besonders bei umfangreichen Importbeständen müssen nicht mehr sämtliche historischen Touren und offenen Aufträge eingelesen werden.

## Tests

- 205 Tests bestanden.
- Neue Tests prüfen die zeitliche Begrenzung der Tourabfrage und der automatischen Abschlussprüfung.

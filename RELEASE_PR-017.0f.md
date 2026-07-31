# PR-017.0f – Tourketten und Arbeitszeit

## Behoben

- Ein einzelner importierter Fahrerabschnitt verkürzt die angezeigte Arbeitszeit nicht mehr.
- Bei echten Fahrerwechseln wird nur produktive Zeit (Fahrt, Laden, Entladen) je Fahrer gerechnet; Ruhe- und Wartezeiten zählen nicht als Arbeitszeit.
- Die Plantafel lädt je Fahrzeug die letzte relevante Tour vor dem sichtbaren Zeitraum.
- Fernverkehrsfahrzeuge starten die Folgetour am letzten tatsächlichen Entladeort statt erneut an der Heimatbasis.
- Stornierte und leere Vorgängertouren werden bei der Standortfortschreibung ignoriert.
- Vorgängertouren aus früheren Tagen werden nicht erneut vollständig geroutet; dadurch bleibt die Plantafel schneller.

## Tests

- 213 Tests erfolgreich.

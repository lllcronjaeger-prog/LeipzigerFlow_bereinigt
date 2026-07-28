LeipzigerFlow – Bugfix Mehrtages-Disposition übernehmen

Ursache:
- Die Plantafel rief weiterhin ausschließlich DispatchSimulationService.simulate(planning_day) auf.
- simulate_horizon() war vorhanden, aber nicht mit der UI verbunden.
- apply() speicherte deshalb nur das Ergebnis des ausgewählten Tages.

Umgesetzt:
- Neues Feld "Planungstage" in der Plantafel (1 bis 14, Standard 3).
- Bei einem Planungstag bleibt der bisherige Varianten-Dialog unverändert.
- Bei mehreren Planungstagen wird simulate_horizon() aufgerufen.
- Neuer Mehrtages-Übersichtsdialog mit Tageszahlen für Aufträge, Zuordnungen, offene Aufträge und Touren.
- Neue Methode DispatchSimulationService.apply_horizon().
- Alle Tagesergebnisse werden chronologisch gespeichert.
- Nach der Übernahme wird die Plantafel aktualisiert.

Tests:
- 131 Tests erfolgreich.
- Neuer Regressionstest stellt sicher, dass alle simulierten Tage in der richtigen Reihenfolge übernommen und summiert werden.

Keine Datenbankmigration erforderlich.

LeipzigerFlow – Bugfix Replay, Mehrtagesdetails und doppelte Leertouren

Geänderte Dateien:
- src/leipzigerflow/ui/dialogs/dispatch_simulation_dialog.py
- src/leipzigerflow/services/daily_tour_service.py

Korrekturen:
1. Replay-Button Ein-Tagesplanung
   - Der Dialog startet nicht mehr bereits im Replay-Reiter.
   - Der Button wechselt sichtbar in den Replay-Reiter.

2. Mehrtagesplanung
   - Replay-Button auch im Mehrtagesdialog.
   - Detaillierte Tagesübersicht.
   - Gemeinsame Vorschlagsliste über alle Tage.
   - Alternativen über alle Tage.
   - Offene Aufträge über alle Tage.
   - Chronologischer Replay mit Tagesangabe.

3. Doppelte leere Touren
   - Eine vorhandene Tagestour wird anhand des Fahrzeugs erkannt.
   - Eine durch die Disposition angepasste Startzeit führt nicht mehr dazu,
     dass beim nächsten Simulationslauf eine neue leere Grundtour angelegt wird.
   - Bei echter sequenzieller Doppelschicht bleibt die zweite Fahrerschicht erhalten.

Tests:
- 135 Tests erfolgreich.

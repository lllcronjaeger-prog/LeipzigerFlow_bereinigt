LeipzigerFlow – Version 1.0 Ausbau: PlanningEngine-Fassade und Replay

Geänderte Dateien:
- src/leipzigerflow/planner/engine/facade.py (neu)
- src/leipzigerflow/planner/engine/__init__.py
- src/leipzigerflow/ui/dialogs/planning_board_dialog.py
- src/leipzigerflow/ui/dialogs/dispatch_simulation_dialog.py
- tests/test_dispatch_engine.py

Umgesetzt:
- Zentrale öffentliche PlanningEngine-Fassade für Tages- und Mehrtagesplanung
- Einheitliche Methoden simulate, simulate_horizon, apply und apply_horizon
- KPI-Auswertung über PlanningEngine.evaluate
- Replay-Modell für Tages- und Mehrtagesergebnisse
- Neuer Button und Reiter „Replay“ in der Tages-Simulation
- Plantafel greift nicht mehr direkt auf DispatchSimulationService zu
- Bestehende Hard Rules, Scoring- und Speicherlogik bleiben unverändert

Tests:
135 Tests erfolgreich.

Einbau:
Den Inhalt dieses ZIP-Archivs in das Projektverzeichnis kopieren und vorhandene
Dateien ersetzen. Die Ordnerstruktur ist bereits passend vorbereitet.

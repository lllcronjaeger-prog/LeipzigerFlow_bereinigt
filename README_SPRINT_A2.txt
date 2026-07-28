Sprint A.2 – Stabilisierung der Planungsengine

Geänderte Schwerpunkte:
1. Zentrale Arbeitszeitberechnung
   - Neue Datei planner/engine/workday.py
   - Leerfahrt, Warten, Laden, Fahrt, Entladen und genau eine Basisrückfahrt
     werden in einer gemeinsamen Berechnung zusammengeführt.
   - Dispatcher-Hard-Rules und Kapazitätsberechnung verwenden denselben Service.

2. Zentrale Fahrzeugzustands-Schnittstelle
   - Neue Datei planner/engine/vehicle_state_service.py
   - ResourceAvailabilityEngine bezieht Tagesstart, Basisrückkehr und Standort
     nur noch über diesen zentralen Einstiegspunkt.
   - Die vorhandene Resolver-Logik und ihre Methodennamen bleiben kompatibel.

3. Nachvollziehbares Kandidatenprotokoll
   - Neue Datei planner/engine/decision_log.py
   - DispatchSimulationResult enthält candidate_decisions.
   - Für jeden Auftrag/Fahrzeug-Kandidaten werden Zulässigkeit, Score,
     Ablehnungsgründe und die gewählte Zuordnung protokolliert.

4. Regressionstests
   - Einmalige Rückfahrt in der Arbeitszeitberechnung
   - Kandidatenprotokoll mit gewähltem Fahrzeug
   - Kundenprioritäten 1–10 ohne Überschreiben von Hard Rules
   - Bestehende 8043/8044-, Leerfahrt-, Folgetag- und Mannheim-Tests bleiben aktiv.

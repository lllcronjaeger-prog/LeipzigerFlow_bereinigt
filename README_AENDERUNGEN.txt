LeipzigerFlow – Bugfix Leerfahrt, Folgetag und Fahrerfenster

Geänderte Dateien:
- src/leipzigerflow/planner/engine/scoring.py
- src/leipzigerflow/planner/engine/dispatcher.py
- src/leipzigerflow/planner/engine/availability.py
- src/leipzigerflow/ui/dialogs/driver_dialog.py
- tests/test_dispatch_engine.py

Änderungen:
1. Die Leerfahrt vom aktuellen Fahrzeugstandort bzw. von der Basis zur ersten Ladestelle wird mit der tatsächlichen Routingdauer berechnet. 30 Minuten bleiben nur als Fallback bestehen.
2. Dieselbe Leerfahrtroute wird für Prüfung, Arbeitszeit, Vorschau und Toursegment verwendet.
3. Leere, automatisch angelegte Tagestouren starten mit einer frischen Tagesarbeitszeit. Zeitanteile und Rückfahrten des Vortags werden nicht übernommen.
4. Die Fahreransicht verwendet nur noch die zentrale Fensterverwaltung. Eine zweite, konkurrierende Wiederherstellung von Dialoggeometrie und Tabellenzustand wurde deaktiviert.

Prüfung:
- 119 Tests erfolgreich.
- Mit der mitgelieferten Datenbank am 27.07.2026: 6 interne Zuordnungen, 1 regelkonform offener Verkaufsauftrag.

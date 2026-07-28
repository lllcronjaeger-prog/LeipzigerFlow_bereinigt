LeipzigerFlow – Bugfix Planung Nah-/Fernverkehr
Stand: 27.07.2026

Geänderte Dateien:
- src/leipzigerflow/planner/engine/dispatcher.py
- src/leipzigerflow/planner/engine/scoring.py
- src/leipzigerflow/planner/time_planning.py
- src/leipzigerflow/ui/dialogs/planning_board_dialog.py
- tests/test_dispatch_engine.py

Korrekturen:
1. Nahverkehr darf keinen Auftrag mehr erhalten, dessen Entladung erst am Folgetag endet.
2. 8044 kann den Mannheim-Auftrag als Fernverkehrs-Tagesabschluss übernehmen und dort die Ruhezeit einlegen.
3. Die Dispositionsreihenfolge nutzt zuerst zwei Shuttle-Umläufe auf 8044 und danach Mannheim.
4. 8043 erhält drei Shuttle-Umläufe und kehrt noch am selben Kalendertag zur Basis zurück.
5. Die Leerfahrt von der Basis zur ersten Ladestelle wird auch in der vollständigen Tour-/Fahreransicht erzeugt.
6. Bei einem neuen Arbeitstag wird die Verfügbarkeit des Vortags nicht als heutige Arbeitszeit übernommen.
7. Standard-Koffer ist für einen reinen Standard-Plane-Auftrag freigegeben, sofern keine Mega-Anforderung besteht.

Reproduziertes Ergebnis für 27.07.2026 mit der mitgelieferten Datenbank:
- KA-LL 8043: 3 Shuttle-Aufträge Germersheim
- KA-LL 8044: 2 Shuttle-Aufträge Germersheim + Mannheim
- 6 interne Zuordnungen, 1 Verkaufsauftrag bleibt offen

Tests:
120 passed

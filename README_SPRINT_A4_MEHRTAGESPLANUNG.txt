LeipzigerFlow – Sprint A.4 Mehrtagesplanung

Umgesetzt:
- Mehrtägige Simulation über DispatchSimulationService.simulate_horizon().
- Explizite Fortschreibung des Fahrzeugstandorts von Tag zu Tag.
- Nahverkehr startet am Folgetag wieder an der Heimatbasis.
- Fernverkehr startet am Folgetag am letzten Zielort.
- Arbeitszeit wird für jeden neuen Planungstag frisch eröffnet.
- Trailer bleiben am Fahrzeug gekoppelt; keine Übergabe beim Kunden.
- Zukunftsbedarf erzeugt nur für Fernverkehr einen begrenzten Soft-Bonus.
- Heutige Hard Rules können durch den Zukunftsscore nicht überschrieben werden.
- Mehrtages-Protokoll und Tagesendzustände werden im Ergebnis bereitgestellt.

Neue zentrale Datei:
- src/leipzigerflow/planner/engine/multiday.py

Neue Service-Schnittstelle:
- DispatchSimulationService.simulate_horizon(start_day, horizon_days=3)

Keine Datenbankmigration erforderlich.

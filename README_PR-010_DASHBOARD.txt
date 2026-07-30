LeipzigerFlow – PR-010 Dashboard
================================

Umgesetzt:
- Acht große KPI-Karten in einem klaren 4x2-Raster
- Mindesthöhe 152 px und Mindestbreite 230 px je Karte
- Größere Kennzahlen, Icons, mehrzeilige Detailtexte und Hover-Effekt
- Farbige Statusakzente für Ressourcen, Planung und kritische Vorgänge
- Schnellzugriffe auf Plantafel, Aufträge, Touren, Fahrer, Zugmaschinen und LeipzigerAI
- Kompakte Zusammenfassungen für Ressourcenverfügbarkeit und heutigen Tourstatus
- Bestehende Warnungs-, Empfehlungs-, Touren- und Auftragstabellen bleiben erhalten
- Automatische Aktualisierung alle 30 Sekunden

Tests:
pytest -q
168 passed

Start:
py run.py

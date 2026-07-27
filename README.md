# LeipzigerFlow

LeipzigerFlow ist eine Desktop-Anwendung für Transportaufträge, Tourenplanung und Disposition.

## Aktueller Stand

- Transportaufträge mit getrennten Reitern **Aktive Aufträge** und **Archiv**
- Touren mit getrennten Reitern **Aktive Touren** und **Tourarchiv**
- kompakte Plantafel mit Drag & Drop
- Tourdetails in einem eigenständigen, skalierbaren Fenster
- automatische Disposition ausschließlich nach dem Ladedatum der gewählten Tagestour
- mehrtägige Zustellungen innerhalb eines Auftrags bleiben möglich
- Routing, Fahrzeit-, Pausen- und Ruhezeitberechnung
- Fahrer-, Fahrzeug- und Trailerverwaltung

## Einrichtung unter Windows

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

## Start

```powershell
py run.py
```

oder bei aktivierter virtueller Umgebung:

```powershell
python run.py
```

## Tests

```powershell
pytest -q
```

## Projektstruktur

```text
data/       lokale SQLite-Datenbank und Laufzeitdaten
docs/       Architektur, Fachkonzept und Roadmap
resources/  statische Ressourcen
scripts/    Hilfsskripte
src/        Anwendungsquellcode
tests/      automatisierte Tests
```

Die Ordner `.venv`, `.git`, `__pycache__` und `.pytest_cache` sind bewusst nicht Bestandteil des bereinigten Projektstands.

## Hotfix 2026.18.5.2

- Mehrtägige Touren zeigen in „Touren des Tages“ die höchste tatsächliche Arbeitszeit eines einzelnen Einsatztages gegen 10:00 Stunden.
- Übernachtungen, Kalenderwartezeiten und Wochenenden erhöhen die Auslastung nicht mehr.
- Sonntage sind in der Zeitplanung als vollständiges Fahr- und Arbeitsverbot gesperrt; die Planung wird am Montag fortgesetzt.

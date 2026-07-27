# LeipzigerFlow 2026.18.2 – Start

Dieser Ordner ist der bereinigte Arbeitsstand für alle weiteren Sprints.

## Virtuelle Umgebung

Eine vorhandene `.venv` kann in den Projektordner kopiert werden. Zuverlässiger ist das Neuerstellen:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

## Programm starten

```powershell
py run.py
```

oder bei aktivierter `.venv`:

```powershell
python run.py
```

## Projekt prüfen

```powershell
pytest -q
```

Die bestehende Datenbank befindet sich in `data/leipzigerflow.db` und wurde im Projektstand beibehalten.

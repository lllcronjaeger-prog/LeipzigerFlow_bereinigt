# Architektur

LeipzigerFlow verwendet eine klar getrennte Schichtenarchitektur:

```text
UI
 ↓
Service
 ↓
Repository
 ↓
SQLite / SQLAlchemy
```

## Verantwortlichkeiten

### UI

- Darstellung und Benutzereingaben
- keine SQL-Abfragen
- keine fachliche Validierung

### Service

- Fachlogik
- Validierung
- Orchestrierung von Repository-Aufrufen

### Repository

- ausschließlich Datenbankzugriffe
- keine UI-Abhängigkeiten
- keine fachliche Validierung

### Model

- Domänen- und Persistenzobjekte
- Beziehungen zwischen Entitäten

# Changelog

## 2026.20.1 – Kundenimport und Fahrer-Abwesenheitsplanung

- Kundenimport für Dispoplan-Dateien im Format XLS und XLSX ergänzt.
- Name, MatchCode und Anschrift werden automatisch übernommen und zerlegt.
- Hauptkunden werden als Frachtzahler verknüpft oder bei Bedarf angelegt.
- Wiederholte Importe aktualisieren Kunden anhand des MatchCodes.
- Fahrer-Abwesenheiten in einen separaten Reiter verschoben.
- Mehrere geplante Abwesenheiten je Fahrer mit Datum, Uhrzeit, Grund und Bemerkung möglich.
- Fahrerrotation, Dashboard und Fahrertabelle berücksichtigen die neue Abwesenheitsliste.
- Legacy-Abwesenheitsfelder bleiben für bestehende Datenbanken kompatibel.

## v1.5.3 – Konsolidierter Master-Stand

- Modernes Dashboard aus PR-010 wiederhergestellt.
- Fahrerimport aus PR-011.1 beibehalten.
- Fahrzeug- und Trailerimport aus PR-011.2 beibehalten.
- Speicherung der Fenstergrößen aus PR-011.2.1 beibehalten.
- Dashboard-Schnellzugriff auf LeipzigerAI wiederhergestellt.
- Projektstand erstmals als konsolidierter Master-Stand zusammengeführt.

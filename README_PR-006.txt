LeipzigerFlow – PR-006 Benutzer-, Rollen- und Berechtigungsverwaltung

Enthalten:
- Benutzer anlegen, bearbeiten, aktivieren/deaktivieren und löschen
- Rollen zuweisen
- Passwort auf temporäres Passwort zurücksetzen
- Rollen anlegen, bearbeiten und löschen
- Berechtigungen gruppiert per Checkbox zuweisen
- Schutz vor Deaktivierung/Löschung des aktuell angemeldeten Benutzers
- Schutz vor Löschung noch zugewiesener Rollen
- Menüeintrag unter Extras > Benutzer und Rollen
- Zugriff nur mit Berechtigung users.manage

Installation:
Den Inhalt dieses ZIP-Archivs über den bestehenden Projektordner kopieren.

Test:
pytest -q

Erwartetes Ergebnis auf dem gelieferten Projektstand:
148 passed

Commit-Nachricht:
S1.2 PR-006 Benutzer- und Rollenverwaltung integrieren

LeipzigerFlow – PR-008.2 QThread-Lebenszyklus-Fix
=================================================

Behobener Fehler:
  QThread: Destroyed while thread '' is still running

Ursache:
Der Schließen-Button und die Escape-Taste konnten den modalen KI-Dialog über
QDialog.accept()/reject() beenden, ohne dass closeEvent() aufgerufen wurde.
Dadurch wurde der zum Dialog gehörende QThread zerstört, obwohl die Ollama-
Anfrage noch lief.

Änderung:
- alle Schließwege des Dialogs werden zentral abgesichert
- Schließen-Button verwendet eine sichere Schließroutine
- accept(), reject(), done() und closeEvent() verhindern das Beenden während
  einer laufenden Anfrage
- der Benutzer wird aufgefordert, zuerst "Abbrechen" zu wählen und das Ende
  des Threads abzuwarten

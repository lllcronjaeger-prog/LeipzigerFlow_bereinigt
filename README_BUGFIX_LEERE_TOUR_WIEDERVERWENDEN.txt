LeipzigerFlow – Bugfix Mehrtages-Disposition: vorhandene leere Touren

Änderung:
- Bei der Übernahme eines Mehrtages-Ergebnisses wird zuerst nach einer bereits
  vorhandenen, leeren und nicht gesperrten Tour für dasselbe Fahrzeug und Datum gesucht.
- Diese Tour wird mit den disponierten Aufträgen befüllt.
- Eine neue Tour wird nur erzeugt, wenn keine passende leere Tour vorhanden ist.
- Fahrer und geplante Startzeit der noch leeren Tour werden an den angenommenen
  Planungsvorschlag angepasst.

Damit bleiben die durch DailyTourService vorbereiteten Fahrzeugtouren auch an
Folgetagen erhalten und werden nicht durch zusätzliche Duplikate umgangen.

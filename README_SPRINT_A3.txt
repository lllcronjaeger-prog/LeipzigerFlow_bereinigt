LeipzigerFlow – Sprint A.3: Optimierung und Erklärbarkeit

Enthaltene Änderungen:
- Teil-Scores je Kandidat (Priorität, Kompatibilität, Leerfahrt, Zeitfenster,
  Arbeitszeit, Fahrer/Fahrzeug, Kettenbildung, Flottenbalance und Stabilität).
- Das Entscheidungsprotokoll zeigt die Teil-Scores und gleicht sie exakt mit
  dem finalen Kandidatenscore ab.
- Vorhandene Transportketten- und Rundtourlogik bleibt aktiv und unverändert.
- Routing-Performance wird messbar: Kandidatenbewertungen, Cache-Einträge,
  Cache-Treffer/-Fehlschläge und Simulationsdauer.
- Zusätzliche Regressionstests sichern Score-Aufschlüsselung und Routing-Cache.

Es wurden keine bestehenden Fachregeln, Grenzwerte oder UI-Aufrufpfade entfernt.

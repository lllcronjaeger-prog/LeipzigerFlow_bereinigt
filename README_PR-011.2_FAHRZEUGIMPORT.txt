PR-011.2 – Dispoplan-Fahrzeugimport

- Unterstützt .xls und .xlsx.
- Verarbeitet ausschließlich die Spalte "Kennzeichen KfZ".
- KA-LL und KA LL werden als Zugmaschinen erkannt.
- Alle anderen gültigen Kennzeichen werden als Trailer erkannt.
- MatchCode ist grundsätzlich die Endnummer.
- Bei Überschneidungen erhält der Trailer den ersten Buchstaben der mittleren
  Kennzeichengruppe als Präfix, z. B. KA-ET 8043 -> E8043.
- Zugmaschinen werden als Standard/Nahverkehr, Trailer als Plane angelegt.
- Alle importierten Datensätze sind aktiv und zunächst frei.
- Platzhalter, ungültige und doppelte Kennzeichen werden in der Vorschau markiert
  und nicht importiert.

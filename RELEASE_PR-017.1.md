# PR-017.1 – Fahrerzyklen und sequenzielle Shuttle-Schichten

## Umgesetzt

- Arbeitszeit wird je Fahrerschicht statt pauschal je Fahrzeug fortgeschrieben.
- Ein planmäßiger Fahrerwechsel gibt dem zweiten Fahrer ein eigenes Arbeitszeitfenster.
- Bestehende Fahrerabschnitte einer Tour werden als nacheinander verfügbare Ressourcen desselben Fahrzeugs geladen.
- Ein Shuttle-Fahrzeug kann nach dem Fahrerwechsel ohne zweite Fahrzeugtour weiterfahren.
- 2/1- und 3/1-Fahrer behalten am Montag den auswärtigen Fahrzeugstandort, wenn sie lediglich ihre nächste Einsatzwoche beginnen.
- Beginnt am Montag ein neuer Fahrer beziehungsweise ein neuer Zyklus, startet die Planung an der Heimatbasis.
- Bei einer freien Stammfahrer-Rotation wird der verfügbare Wechselfahrer als Tagesfahrer gewählt.

## Fachliche Beispiele

- TS-ZM 1510: Fahrer 1 kann die ersten Umläufe fahren; Fahrer 2 übernimmt danach dasselbe Fahrzeug mit eigener Arbeitszeitgrenze.
- KA-LL 8045: Bei neuem Fahrer am Montag startet die Planung in Leipzig, obwohl die letzte Freitagszustellung in Wustermark endete.
- Ein Fahrer in Einsatzwoche 2 eines 2/1-Modells setzt den Fahrzeugstandort am Montag nicht künstlich auf die Basis zurück.

## Tests

219 Tests bestanden.

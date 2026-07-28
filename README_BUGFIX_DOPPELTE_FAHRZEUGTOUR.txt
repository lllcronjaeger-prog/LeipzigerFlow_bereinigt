LeipzigerFlow – Bugfix doppelte Fahrzeugverwendung bei Mehrtagesübernahme

Problem:
Am Folgetag konnten mehrere Vorschlagsblöcke für dasselbe Fahrzeug entstehen.
Der erste Block befüllte die vorhandene leere Tour. Beim zweiten Block war diese
Tour nicht mehr leer, sodass fälschlich eine weitere Tour für dasselbe Fahrzeug
und denselben Tag angelegt wurde.

Änderung:
- DispatchSimulationService.apply() führt jetzt eine Zuordnung je
  (Planungstag, Fahrzeug-ID).
- Weitere Vorschlagsblöcke desselben Fahrzeugs werden derselben bereits
  ausgewählten bzw. neu angelegten Tour hinzugefügt.
- Die Suche nach einer leeren Tour erfolgt je Fahrzeug und Tag nur einmal.
- Eine zusätzliche Tour wird nur erzeugt, wenn für dieses Fahrzeug und diesen
  Tag noch überhaupt keine Tour verwendet wurde.

Regressionstest:
- Zwei ProposedTour-Blöcke für dasselbe Fahrzeug und denselben Tag werden in
  einer vorhandenen leeren Tour zusammengeführt.
- Es entsteht keine dritte Tour und das Fahrzeug wird nicht doppelt verwendet.

Testergebnis:
133 Tests erfolgreich.

PR-011.3.1 – Bugfix Kundenimport bei bereits vorhandenem Kundennamen

Problem:
Ein Kunde konnte durch den vorherigen Dispositionsimport bereits mit demselben Namen,
aber einem anderen oder automatisch erzeugten MatchCode existieren. Da der Kundenname
in der Datenbank eindeutig ist, schlug der Excel-Import mit einer UNIQUE-Constraint-
Meldung fehl.

Korrektur:
Der Import sucht vorhandene Kunden zuerst anhand des MatchCodes und anschließend
anhand des Kundennamens. Ein vorhandener Namensdatensatz wird aktualisiert, statt
ein zweites Mal angelegt zu werden.

Test: 183 passed

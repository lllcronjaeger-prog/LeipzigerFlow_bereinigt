LeipzigerFlow – Sprint A.4: Basis-zentrierte Trailerlogik
========================================================

Umgesetzt:
- Zentrale BaseTrailerPolicy für Trailerzustand und Trailerwechsel.
- Trailer bleiben am Fahrzeug oder befinden sich an einer Heimatbasis.
- Ein Trailerstandort beim Kunden ist in der Planungsengine unzulässig.
- Trailerwechsel sind ausschließlich an der Heimatbasis zulässig.
- Beladene Trailerwechsel an der Basis bleiben als Ausnahme möglich.
- Beladene Wechsel erhalten 60 Minuspunkte, leere Wechsel 12 Minuspunkte.
- ResourceAvailability enthält künftig Trailer-ID, Bezeichnung, Standortart,
  Standortbezeichnung, Beladungsstatus und Wechselanforderung.
- Bestehende Fahrzeug-/Trailerkopplungen bleiben bevorzugt.

Kompatibilität:
- Keine Datenbankmigration erforderlich.
- Bestehende Klassen und Methoden wurden nicht umbenannt.
- Ohne explizite Wechselanforderung ändert sich die aktuelle Disposition nicht.

Tests:
- Trailerwechsel beim Kunden wird abgelehnt.
- Beladener Trailerwechsel an der Basis bleibt zulässig, aber nachrangig.
- Trailerzustand beim Kunden wird als Hard-Rule-Verstoß abgelehnt.
- Gesamtergebnis: 128 Tests erfolgreich.

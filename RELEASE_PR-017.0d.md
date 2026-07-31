# PR-017.0d – Fahrerwechsel, Fahrerimport und Plantafelpräferenzen

## Fahrerwechsel

- Der Dialog erfasst je Fahrer nur noch den Beginn beziehungsweise die Wechselzeit.
- Das Ende eines Fahrerabschnitts wird automatisch aus dem Beginn des nächsten Fahrers ermittelt.
- Der letzte Fahrerabschnitt endet automatisch mit dem berechneten Tourende.
- Dadurch können Fahrerwechsel innerhalb eines Tages gespeichert werden, ohne widersprüchliche Beginn-/Ende-Werte manuell pflegen zu müssen.

## Dispoplan-Fahrerübernahme

- Fahrernamen werden robuster abgeglichen.
- Unterstützt werden zusätzliche Leerzeichen, Kommas und die Reihenfolgen „Vorname Nachname“ sowie „Nachname, Vorname“.
- Matchcodes werden weiterhin berücksichtigt.
- Bei nicht eindeutigen Treffern wird bewusst keine automatische Zuordnung vorgenommen.

## Plantafel

- Die zuletzt ausgewählte Dispositionsgruppe wird in den Benutzereinstellungen gespeichert.
- Beim nächsten Öffnen der Plantafel wird diese Gruppe direkt wieder ausgewählt.

## Qualitätssicherung

- 209 automatisierte Tests bestanden.

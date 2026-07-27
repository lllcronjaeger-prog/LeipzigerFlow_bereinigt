# Datenmodell

## Geplante Kernbeziehungen

```text
Customer 1 ─── n Location
Customer 1 ─── n TransportOrder
Tour     1 ─── n TransportOrder
Vehicle  1 ─── n Tour
Driver   1 ─── n Tour
```

## Transportauftrag

Ein Transportauftrag enthält unter anderem:

- Dossiernummer im Format `YYYYMM-XXXX`
- Kundenauftragsnummer und Referenz
- Status und Kunde
- Abhol- und Lieferstandort
- Abhol- und Lieferzeitfenster
- Ladungsart FTL oder LTL
- Paletten, Gewicht und Lademeter
- Kühlung und Palettentausch
- Notizen

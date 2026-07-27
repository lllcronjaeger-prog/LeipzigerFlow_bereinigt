# Architektur- und Produktentscheidungen

## 2026-07-20 – Geschäftsumfang

LeipzigerFlow unterstützt FTL und LTL. Stückgut, Sammelgut und Hubverkehr gehören nicht zum Umfang.

## 2026-07-20 – Rechnungsempfänger

Ein gesonderter Rechnungsempfänger wird nicht im Transportauftrag geführt, weil die Rechnungsstellung extern erfolgt.

## 2026-07-20 – Dossiernummer

Interne Dossiernummern verwenden das Format `YYYYMM-XXXX`.

## 2026-07-20 – Schichtenarchitektur

Die verbindliche Aufrufrichtung lautet Model/Repository → Service → UI. Repositories enthalten nur Datenbankzugriffe; Services enthalten Validierung und Fachlogik.

## 2026-07-20 – Kundenbezug

Kunden werden als eigene Entität geführt. Standorte und Transportaufträge werden später über Fremdschlüssel mit Kunden verbunden.

## 2026-07-20 – Eindeutiger Kundenname

Kundennamen müssen ohne Beachtung der Groß- und Kleinschreibung eindeutig sein.

## 2026-07-20 – Oberfläche

LeipzigerFlow behält die native Windows-Optik. Stammdatenmodule verwenden eine einheitliche Suche, Button-Reihenfolge und Tastaturbedienung.

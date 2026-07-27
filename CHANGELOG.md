# 2026.18.6

- Auto-Disposition erzeugt mehrere echte, auswählbare Planungsvarianten.
- Variantenvergleich und Übernahme einer bewusst gewählten Alternative.

# Changelog

## 2026.18.5.3

- Geisterauftrag nach dem Zurückschieben eines Auftrags zu den offenen Aufträgen behoben.
- Tourpositionen werden nach dem Entfernen konsistent aus ORM und Datenbank entfernt.
- Verbleibende Positionen werden lückenlos positiv neu nummeriert.

# 2026.18.4

- Reguläre Planungsengine auf harte Dispositionsprioritäten umgestellt.
- Aufträge mit „Eigenfuhrpark bevorzugt“ werden vollständig vor Verkaufsaufträgen geplant.
- Verkaufsaufträge über 130 km werden als Fernverkehr für Subunternehmer priorisiert.
- Transportketten dürfen die Eigenfuhrpark-Priorität nicht mehr übersteuern.
- Tourkarten zeigen wieder die Arbeitszeitauslastung des Fahrers mit Fortschrittsbalken.
- Vereinfachte Detailansicht zeigt Arbeitszeit, Lenkzeit und prozentuale Auslastung.
- Tourdetailfenster enthält eine große Arbeitszeitauslastung; Laderaumwerte bleiben als untergeordnete Kapazitätskontrolle sichtbar.
- 91 automatisierte Tests bestanden.

# 2026.17.7.2

- Flexible Öffnungszeitfenster und reale Anschlusszeiten korrigiert.
- Fahrzeugkontinuität mit automatischer Leerfahrt zwischen Touren ergänzt.
- Einsatztage kalendarisch korrekt berechnet.
- Tour-Zeitachse und globales UI-Theme ergänzt.

# Sprint 17.5 – Planning Engine V3

- Transportketten werden vor der Einzelzuweisung erkannt.
- Folgeaufträge bleiben auf demselben Fahrzeug reserviert.
- Eigenfuhrpark wird vor unnötiger Fremdvergabe ausgeschöpft.
- Referenzszenario PE-001 als Regressionstest ergänzt.
- Mehrtägige Aufträge werden nicht mehr als eine einzige Kalenderschicht abgelehnt.

# Changelog

## 2026.16.4.2b – Tourreihenfolge / Service-API

- Fehler beim Übernehmen einer optimierten Tourreihenfolge behoben.
- Öffentliche Methode `TourService.save_position_order()` eingeführt.
- `apply_optimized_order()` verwendet nun die transaktionssichere Positionslogik aus Drag & Drop.
- Vollständigkeit und Zugehörigkeit der Tourpositionen werden vor dem Speichern geprüft.

## 2026.16.4.2a – Drag-Lifecycle und Scrollposition

- Periodische Plantafel-Aktualisierung während eines aktiven Drag-Vorgangs pausiert.
- Drop-Verarbeitung wird erst nach Rückkehr aus `QDrag.exec()` ausgeführt.
- Verhindert das Löschen von Tourkarten während der verschachtelten Qt-Eventschleife.
- Vertikale Scrollposition der Tages-Tourliste bleibt bei automatischen und manuellen Refreshes erhalten.
- Auswahl einer Zieltour nach dem Drop erzwingt kein Zurückspringen der Ansicht.

## 2026.16.4.2 – Drag-&-Drop-Stabilisierung

- Konfliktfreie, transaktionssichere Neunummerierung der Tourpositionen eingeführt.
- UNIQUE-Constraint-Fehler beim Verschieben zwischen belegten Touren beseitigt.
- Aufträge können wieder auf „Nicht disponierte Aufträge“ gezogen werden.
- Rand-Autoscroll für lange Tourlisten ergänzt.
- Drop- und Doppelklick-Refreshes werden erst nach Abschluss des Qt-Events ausgeführt.
- Schutz vor Zugriffen auf bereits gelöschte PySide6-Widgets ergänzt.

## 2026.16.2.2 – Routingzeiten und Lenkzeitunterbrechungen

- Starre 30-Minuten-Fahrzeiten in der Tourdarstellung entfernt.
- Jeder beladene und leere Fahrtabschnitt verwendet OSM-/Routing-Cache-Entfernungen.
- Planfahrzeit wird einheitlich mit 65 km/h Durchschnittsgeschwindigkeit berechnet.
- 45-minütige Fahrtunterbrechungen werden nach 4:30 h Lenkzeit automatisch in den Zeitstrahl eingefügt.
- Lade- und Entladezeiten bleiben sonstige Arbeit und setzen die Lenkzeit nicht zurück.
- Tages-, Wochen- und Zweiwochen-Lenkzeit sowie tägliche Ruhezeit werden transparent vorgeprüft.
- Tourkarte zeigt je Auftrag Strecke, Fahrzeit und eingerechnete Pausen.
- 55 automatisierte Tests bestanden.

## 2026.16.2 – Reihenfolgeoptimierung

- Route Optimizer bewertet jetzt beladene und leere Strecken vollständig.
- Gesamtstrecke, Fahrzeit, Wartezeit und Leer-km werden je Tourvariante berechnet.
- Zeitfensterverletzungen bleiben harte Ausschluss- bzw. Abwertungskriterien.
- Tourplanung zeigt die mögliche Kilometer- und Zeitersparnis vor der Übernahme.
- 54 automatisierte Tests bestanden.

## 2026.15.2

- Intelligente zeitbasierte Flottenauslastung ergänzt.
- Optimierungsvorschläge in Simulation und Excel-Export ergänzt.
- Tourbündelungen, Umbuchungen und Kapazitätsengpässe werden transparent ausgewiesen.

# Changelog

## 2026.16.4.2b – Tourreihenfolge / Service-API

- Fehler beim Übernehmen einer optimierten Tourreihenfolge behoben.
- Öffentliche Methode `TourService.save_position_order()` eingeführt.
- `apply_optimized_order()` verwendet nun die transaktionssichere Positionslogik aus Drag & Drop.
- Vollständigkeit und Zugehörigkeit der Tourpositionen werden vor dem Speichern geprüft.

## 2026.14.2.2

- Planungsvorschläge der automatischen Disposition können als formatierte Excel-Arbeitsmappe exportiert werden.
- Die Tourenverwaltung exportiert alle aktuell gefilterten Touren als Tourübersicht und detaillierte Auftragsreihenfolge.
- Export enthält Fahrer, Zugmaschine, Trailer, Tourstatus, Zeitfenster, Lade- und Entladestellen sowie offene Aufträge und Alternativen.
- 37 automatisierte Tests bestanden.

## 2026.14.2.1 – Dispositionskorrektur und Schichtbesetzung

- automatische Planung verteilt geeignete Aufträge auf mehrere verfügbare Fahrzeuge
- kumulative Fahrerschicht ist jetzt eine Hard Rule; Aufträge hinter dem Schichtende werden abgelehnt
- tägliche Grundtouren werden an Werktagen für alle einsatzfähigen Fahrzeuge automatisch angelegt
- Stammfahrer je Fahrzeug als Tourvorlage konfigurierbar
- optionale zweite, zeitlich anschließende 9-Stunden-Schicht mit Wechselfahrer
- keine Anwendung der Regeln für gleichzeitige Doppelbesatzung
- Werkstatt-, Defekt- und stillgelegte Fahrzeuge werden bei der Tagesanlage übersprungen
- 35 automatisierte Tests bestanden

## 2026.14.2 – Sprint 14.2

- Mehrstopp-Touren mit automatischer Reihenfolgeoptimierung
- Zeitfensterprüfung für Be- und Entladung
- transparente Tourqualität von 0 bis 100 Prozent
- Vergleich von aktueller und optimierter Reihenfolge
- konservativer Routing-Fallback ohne erfundene Kilometerwerte
- austauschbare Routing-Schnittstelle für spätere Dispoplan-/Kartendienste
- direkte Übernahme optimierter Reihenfolgen in der Tourdisposition
- 33 automatisierte Tests bestanden

# Sprint 12.2.3 – Mehrere Traileraufbauten pro Auftrag

- Mehrfachauswahl der zulässigen Traileraufbauten im Transportauftrag
- Bestehende Einzelwerte bleiben vollständig kompatibel
- Automatische Disposition akzeptiert jede ausgewählte Trailerart
- Mega-Zugmaschine wird nur verlangt, wenn ausschließlich Mega-Aufbauten zulässig sind
- Dashboard zählt Mega/Kühler nur bei zwingender Anforderung

# 2026.12.2.2

- Geplante Aufträge und Aufträge auf geplanten oder laufenden Touren werden im Leitstand nicht mehr als offen oder kritisch geführt.
- Transportaufträge besitzen jetzt den benötigten Trailertyp.
- Die automatische Disposition prüft den benötigten Trailertyp gegen den tatsächlich gekoppelten Trailer.
- Mega-Anforderungen benötigen weiterhin eine Mega-Zugmaschine und einen passenden Mega-Trailer.

# Sprint 12.2.1

- Aufträge mit Status „Unterwegs“ werden nicht mehr als offen gezählt.
- Aufträge in einer bereits laufenden Tour werden auch bei abweichendem Auftragsstatus aus der offenen Liste ausgeschlossen.
- Kennzahlen, kritische Aufträge sowie Mega-/Kühlerzählungen verwenden denselben bereinigten offenen Bestand.

## 2026.10.2
- Register „Auswertung“ in der Simulationsansicht an zweite Position verschoben.
- Direkte Schaltfläche „Auswertung anzeigen“ ergänzt.
- Scroll-Schaltflächen für schmale Registerleisten aktiviert.

# Changelog

## 2026.16.4.2b – Tourreihenfolge / Service-API

- Fehler beim Übernehmen einer optimierten Tourreihenfolge behoben.
- Öffentliche Methode `TourService.save_position_order()` eingeführt.
- `apply_optimized_order()` verwendet nun die transaktionssichere Positionslogik aus Drag & Drop.
- Vollständigkeit und Zugehörigkeit der Tourpositionen werden vor dem Speichern geprüft.

## 0.1.0

- Projekt erstellt
- PySide6 eingerichtet
- Logging
- SQLite
- SQLAlchemy
- erstes Datenmodell
## Sprint 9 – Automatische Disposition, Phase 1

- Ressourcenverfügbarkeit wird aus vorheriger Tour, Entladeort und Tourende abgeleitet.
- Öffnungszeiten und Zeitfenster bestimmen den frühesten nächsten Ladebeginn.
- Neue deterministische Prioritäts- und Bewertungsengine.
- Standard-/Mega-Kompatibilitätsprüfung.
- Simulation mit Vorschlägen, offenen Aufträgen und Subunternehmerbedarf.
- Dispoplan-Adapter als austauschbare Integrationsschnittstelle vorbereitet.

## 2026.10 – Sprint 10

- konfigurierbare Gewichtungen für die Auto-Disposition
- Tourenerweiterung wird vor Neubildung bewertet
- alternative Fahrzeug-/Fahrerzuordnungen je Auftrag
- nachvollziehbare Entscheidungs- und Ablehnungsgründe
- Managementauswertung mit Fahrzeugnutzung, Anfahrt, Wartezeit und Subunternehmerbedarf

## 2026.13.0 – Intelligente Tagesoptimierung

- Hard- und Soft-Regeln der Disposition klar getrennt.
- Flottenweiter Planungskontext für Trailerangebot und Auftragsnachfrage ergänzt.
- Knappe Mega-Ressourcen werden bei flexiblen Aufträgen bewusst geschont.
- Bestehende Kombinationen und stabile Tourerweiterungen werden bevorzugt.
- Anschlussverfügbarkeit fließt in die Bewertung ein.
- Planungshorizont ist über `dispatch_rules.json` konfigurierbar.
- Schnell-, Standard- und Optimiert-Profil besitzen unterschiedliche Suchtiefen.
- Nahezu gleichwertige Vorschläge werden anhand einer konfigurierbaren Punkteschwelle markiert.

## 2026.14.1 – Sprint 14.1

- modularen TourOptimizer-Core eingeführt
- Hard- und Soft-Regeln getrennt
- transparente Ergebnis- und Erklärungsobjekte ergänzt
- Optimierungsprofile zentralisiert
- vorhandenen DispatchOptimizer rückwärtskompatibel auf den neuen Kern migriert
- Unit-Tests für Auswahl, Ablehnung, Sperren, Gleichwertigkeit und Profile ergänzt

## 2026.15.1

- Automatische Tourbildung aus den Ergebnissen der Auto-Disposition
- Tourenaufteilung nach Fahrzeug und zeitlich getrennter Fahrerschicht
- Bestätigte Planung kann direkt auf bestehende oder neue Touren übernommen werden
- Excel-Planungsvorschlag um Tourübersicht, Tourdetails und Kennzahlen erweitert
- Tests für Tourgruppierung und erweiterten Excel-Export ergänzt

## 2026.15.1.1

- Excel-Export direkt aus der Plantafel ergänzt.
- Export berücksichtigt den sichtbaren Zeitraum und alle aktiven Plantafel-Filter.
- Auftragsaufteilung und Reihenfolge werden im Tabellenblatt „Tourpositionen“ ausgegeben.

## 2026.15.1.2
- Flexible Lade- und Entladezeitfenster mit Standardwert „verschiebbar“.
- Öffnungszeiten als harte Grenzen, gebuchte Termine als optimierbare Vorgabe.
- Umbuchungsvorschläge in Disposition und Excel-Export.

## 2026.15.1.2.1

- Excel-Export der Plantafel dauerhaft sichtbar im unteren Aktionsbereich ergänzt.
- Export bleibt auch bei kleineren Fensterbreiten und umfangreicher Filterleiste erreichbar.
- Fenstertitel der Plantafel auf Sprint 15.1.2.1 aktualisiert.

## 2026.15.2.1

- Doppelte Excel-Schaltfläche in der Plantafel entfernt; der dauerhaft sichtbare Export unten rechts bleibt erhalten.
- Kapazitätsanalyse der automatischen Disposition ergänzt: geplante, freie und verfügbare Minuten sowie Auslastung je Fahrzeug.
- Konkrete Hinweise ergänzt, wenn unterausgelastete Fahrzeuge zusätzliche eingekaufte Touren übernehmen können.
- Excel-Planungsvorschlag um das Tabellenblatt „Freie Kapazitäten“ erweitert.
- Separate Mehrfenster-Ansicht „Flottenauswertung“ mit frei wählbarem Zeitraum ergänzt.
- Auswertung zeigt Touren, Aufträge und Auslastung je Fahrzeug sowie die Aufteilung auf eigene und fremde Fahrzeuge.
- Zugmaschinenstamm um „Eigenes Fahrzeug“/„Fremdfahrzeug“ erweitert; bestehende Fahrzeuge bleiben standardmäßig eigene Fahrzeuge.
- Excel-Export der Flottenauswertung ergänzt.

## 2026.16.1

- TourBuilder 2.0 mit transparenter regionaler und zeitlicher Clusterbildung.
- Nicht kompatible Traileranforderungen und große Zeitlücken trennen Tourvorschläge automatisch.
- Simulation und Excel-Export zeigen Cluster, Qualität und Begründung.

## 2026.16.1.1 – Entfernungswerk und reale Fahrzeiten
- Zentrale, austauschbare RoutingEngine eingeführt.
- OSRM als Standard-Routingprovider und Nominatim für die Adressauflösung vorbereitet.
- Persistenter Routen- und Geocache in SQLite/PostgreSQL.
- Reale Kilometer und Fahrzeiten werden in der Mehrstopp-Optimierung verwendet.
- Konservativer, sichtbar geschätzter Fallback bei fehlendem Netz oder unvollständigen Adressen.
- Cache-Aufwärmung und gezielte Invalidierung nach Adressänderungen ergänzt.

## 2026.16.2.1

- Strecke und Routenfahrzeit in „Touren des Tages“ ergänzt.
- Automatische Verschiebung des Entladedatums bei Änderung des Ladedatums.
- Standardwerte für neue Aufträge auf 24.000 kg, 13,6 Lademeter und 33 Paletten gesetzt.
- Auftragstypabhängige Standardwerte, Plausibilitätsprüfung und Auftragsvorlagen ergänzt.
- Tastenkürzel für Suche, Neuanlage, Duplizieren und Löschen ergänzt.

## 2026.16.5

- Fahrzeugstandort als verbindlichen Startpunkt der Reihenfolgeoptimierung ergänzt.
- Startanfahrt wird als Leerfahrt mit Strecke und Fahrzeit bewertet.
- Zeitfensterverletzungen werden nach Anzahl und Verspätungsdauer priorisiert.
- Standort-Freitext der Zugmaschine wird gegen Standortstammdaten aufgelöst.

## 2026.17.6
- Planning Engine V3.1: beliebig lange Transportketten und Rundtour-Erkennung.
- Plantafel: Entladedatum bei Zustellung an einem anderen Tag sichtbar.
- Mehrtagestouren zeigen Datumsbereich und Übernachtungen.
- Tourkarten zeigen eine indikative Kapazitätsauslastung.

## 2026.17.6.1

- Tourarchiv mit getrennten Ansichten für aktive und abgeschlossene Touren ergänzt.
- Touren werden automatisch abgeschlossen, sobald alle enthaltenen Aufträge erledigt sind.
- Abgeschlossene Touren werden aus Tages-, Wochen- und Monatsplantafel ausgeblendet.
- Archivierte Touren können per Kontextmenü wieder aktiviert werden.

## 2026.17.7.3

- Leerfahrten in der Tagesübersicht als eigener Abschnitt ergänzt.
- Zeitliche statt ladungsbezogene Tourauslastung in der Plantafel.
- Lange Kontextmenüs automatisch gruppiert und kompakter gestaltet.
- Theme-Importe vollständig konsolidiert.

## 2026.17.7.4
- Kontextmenüs unter Windows stabilisiert und verkleinert.
- Absturzschutz für Rechtsklick auf Transportaufträge ergänzt.
- Transportauftragsformular scrollbar gemacht; Dialogbuttons bleiben sichtbar.
- Qt-Fontwarnung beim Schließen durch gültige FontRole-Schriften behoben.

## Sprint 18.0 – Plantafel 2.0
- Plantafel mit horizontalem Tourablauf und scrollbarer Ereignistabelle neu organisiert.
- Detailansicht unterhalb der Dispositionsbereiche über die gesamte Breite angeordnet.
- Transportauftragsarchiv als eigene Ansicht wiederhergestellt.
- Schließen der Plantafel gegen verzögerte Timer- und Scrollzugriffe abgesichert.

## Sprint 18.1 – Kompakte Plantafel

- Kompakte Tourkarten für mehr gleichzeitig sichtbare Tagestouren.
- Tourdetail und Zeitstrahl nur bei aktiver Auswahl sichtbar.
- Redundante Ereignistabelle entfernt.
- Detailkopf platzsparend zusammengefasst.
- Robuste Tourauswahl ohne Hashing von QListWidgetItem.


## 2026.18.2 – bereinigter Arbeitsstand

- Tourdetails aus der Plantafel in ein separates Fenster ausgelagert.
- Transportauftragsarchiv als eigener Reiter umgesetzt.
- Aufträge mit abweichendem Ladedatum werden nicht mehr derselben Tagestour zugeordnet.
- Auto-Disposition verarbeitet nur Aufträge des ausgewählten Ladetages.
- Transportauftrag-, Fahrer-, Fahrzeug- und Trailerdialoge kompakter angeordnet.
- Helles Anwendungstheme und lesbare Kontextmenüs konsolidiert.
- Projekt um virtuelle Umgebung, Git-Metadaten, Caches und alte Sprintdateien bereinigt.

## 2026.18.2.1 – Tourhinweise und flexible Detailansicht

- Hinweise und Konflikte werden im separaten Tourfenster vollständig angezeigt.
- Der Tourzeitstrahl ist über einen vertikalen Splitter in der Höhe frei verstellbar.
- Die Höhe des Zeitstrahls wird dauerhaft gespeichert.
- Fenstergröße und Fensterposition des Tourfensters werden gespeichert und wiederhergestellt.
- Außerhalb des sichtbaren Bildschirmbereichs gespeicherte Fenster werden auf den aktuellen Monitor zurückgesetzt.
- Die starre maximale Höhe der horizontalen Zeitachse wurde entfernt; die Scrollleiste erhält ausreichend Platz.

## 2026.18.3 – Zeitabhängige Ressourcenverfügbarkeit

- Fahrzeuge und Trailer können mehrere zeitlich begrenzte Sperrzeiten erhalten.
- Gründe: Werkstatt, Wartung, TÜV/Prüfung, Reparatur, Vermietung, außer Betrieb und sonstige Sperre.
- Sperrzeiten enthalten Beginn und Ende mit Uhrzeit, Grund, Bemerkung und Aktivstatus.
- Abgelaufene Sperrzeiten bleiben nachvollziehbar und geben die Ressource automatisch wieder frei.
- Tourprüfung erkennt Überschneidungen mit Fahrzeug- und Trailersperrzeiten.
- Doppelbelegungen von Fahrzeugen und Trailern werden als kritischer Konflikt angezeigt.
- Standard-Zugmaschinen mit Mega-Trailern sowie unpassende Traileranforderungen werden erkannt.
- HU- und SP-Fristen werden als abgelaufen oder bald fällig angezeigt.
- Die automatische Ressourcenplanung schließt gesperrte Fahrzeuge und gekoppelte Trailer aus.
- 87 automatisierte Tests bestanden.

## 2026.19.3 – Segmentbasierte Nahverkehrstouren

- Mo–Fr-Fahrer beginnen jeden Planungstag an der Heimatbasis.
- Tourvorschläge enthalten sichtbare Leerfahrt-, Transport- und Basisrückkehrsegmente.
- Start- und Endzeit sowie Kilometer und Fahrzeit berücksichtigen die vollständige Tour.
- Die Tourvorschlagsansicht zeigt die komplette Bewegungsfolge des Fahrzeugs.
- 114 automatisierte Tests bestanden.

## 2026.19.5
- Zustandsorientierte Nah-/Fernverkehrsplanung über mehrere Werktage.
- Fernverkehr kann am letzten Entladeort ruhen; Wochenendstart wieder an Heimatbasis.
- Fahrer-Heimatbasis als Standort-Dropdown und Datenbankreferenz.
- Fahrerverwaltungsfenster speichert Geometrie und Tabellenspalten.

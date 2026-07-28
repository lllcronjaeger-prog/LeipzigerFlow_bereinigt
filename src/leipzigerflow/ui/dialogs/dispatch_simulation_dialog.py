from __future__ import annotations

from dataclasses import fields
from datetime import timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from leipzigerflow.exports import export_dispatch_proposal
from leipzigerflow.planner.engine.configuration import DispatchConfigurationStore
from leipzigerflow.planner.engine.models import DispatchWeights


WEIGHT_LABELS = {
    "priority": "Auftragspriorität",
    "time_window": "Zeitfenster einhalten",
    "location_match": "Nähe zur Ladestelle",
    "vehicle_compatibility": "Fahrzeugkompatibilität",
    "keep_driver": "Fahrer beibehalten",
    "extend_existing_tour": "Bestehende Tour erweitern",
    "minimize_empty_run": "Leerfahrt minimieren",
    "avoid_subcontractor": "Subunternehmer vermeiden",
    "resource_reserve": "Knappe Trailerressourcen schonen",
    "avoid_recoupling": "Umkuppeln vermeiden",
    "followup_potential": "Anschlussverfügbarkeit",
    "planning_stability": "Bestehende Planung stabil halten",
}


class DispatchWeightsDialog(QDialog):
    def __init__(self, weights: DispatchWeights, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gewichtungen der Auto-Disposition")
        self.resize(480, 430)
        self._inputs: dict[str, QSpinBox] = {}

        root = QVBoxLayout(self)
        text = QLabel(
            "100 entspricht der Standardgewichtung. Höhere Werte machen ein Kriterium wichtiger, "
            "0 deaktiviert dessen positive oder negative Bewertung."
        )
        text.setWordWrap(True)
        root.addWidget(text)

        form = QFormLayout()
        for field_info in fields(DispatchWeights):
            spin = QSpinBox()
            spin.setRange(0, 200)
            spin.setSuffix(" %")
            spin.setValue(int(getattr(weights, field_info.name)))
            self._inputs[field_info.name] = spin
            form.addRow(WEIGHT_LABELS.get(field_info.name, field_info.name), spin)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def weights(self) -> DispatchWeights:
        return DispatchWeights(**{name: spin.value() for name, spin in self._inputs.items()})


class DispatchSimulationDialog(QDialog):
    def __init__(self, result, resources, weights, parent=None, apply_callback=None):
        super().__init__(parent)
        self.result = result
        self.resources = resources
        self.weights = weights
        self.apply_callback = apply_callback
        self.selected_variant = next(
            (v for v in (getattr(result, "planning_variants", []) or []) if getattr(v, "recommended", False)),
            None,
        )
        self.setWindowTitle("Automatische Disposition · Simulation")
        self.resize(1420, 860)
        self.setStyleSheet(self._stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 14)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Automatische Disposition · Simulation")
        title.setObjectName("title")
        title_block.addWidget(title)
        subtitle = QLabel(
            "Mehrere zulässige Planungsvarianten werden unabhängig berechnet, bewertet und vergleichbar dargestellt. "
            "Markieren Sie bewusst die Variante, die übernommen werden soll. Es werden zunächst keine Daten verändert."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        title_block.addWidget(subtitle)
        header.addLayout(title_block, 1)
        if self.apply_callback is not None:
            apply_button = QPushButton("Ausgewählte Variante übernehmen")
            apply_button.setToolTip("Übernimmt die in der Variantenansicht ausgewählte zulässige Planung")
            apply_button.clicked.connect(self._apply_plan)
            header.addWidget(apply_button)
        export_button = QPushButton("Vorschlag als Excel")
        export_button.clicked.connect(self._export_excel)
        header.addWidget(export_button)
        evaluation_button = QPushButton("Auswertung anzeigen")
        evaluation_button.clicked.connect(self._show_evaluation)
        header.addWidget(evaluation_button)
        replay_button = QPushButton("Replay anzeigen")
        replay_button.clicked.connect(self._show_replay)
        header.addWidget(replay_button)
        weights_button = QPushButton("Gewichtungen …")
        weights_button.clicked.connect(self._edit_weights)
        header.addWidget(weights_button)
        root.addLayout(header)

        metrics = QHBoxLayout()
        metrics.addWidget(self._metric("Offene Ladungen", result.orders_total))
        metrics.addWidget(self._metric("Intern disponierbar", result.assigned_count))
        metrics.addWidget(self._metric("Touren erweitert", result.extended_tour_count))
        metrics.addWidget(self._metric("Neue Touren", result.new_tour_count))
        metrics.addWidget(self._metric("Bleiben offen", result.open_count))
        metrics.addWidget(self._metric("Subunternehmer", result.subcontractor_count))
        root.addLayout(metrics)

        tabs = QTabWidget()
        self._tabs = tabs
        tabs.setUsesScrollButtons(True)
        tabs.setDocumentMode(False)
        self._replay_tab_index = tabs.addTab(self._replay_tab(), "Replay")
        tabs.addTab(self._planning_trace_tab(), "Planungsverlauf")
        self._variants_tab_index = tabs.addTab(self._variants_tab(), "Planvarianten")
        tabs.addTab(self._tours_tab(), "Tourenaufteilung")
        tabs.addTab(self._assignments_tab(), "Vorschläge")
        tabs.addTab(self._suggestions_tab(), f"Optimierungsvorschläge ({self.result.suggestion_count})")
        self._evaluation_tab_index = tabs.addTab(self._kpi_tab(), "Auswertung")
        tabs.addTab(self._unassigned_tab(), "Offene Aufträge")
        tabs.addTab(self._alternatives_tab(), "Alternativen")
        tabs.addTab(self._capacity_tab(), "Freie Kapazitäten")
        tabs.addTab(self._resources_tab(), "Ressourcen")
        tabs.addTab(self._weights_tab(), "Gewichtungen")
        root.addWidget(tabs, 1)
        # Open on the operational overview. The Replay button now performs a
        # visible action instead of pointing to the tab that was already active.
        tabs.setCurrentIndex(self._variants_tab_index)

        footer = QHBoxLayout()
        note = QLabel(
            "Hinweis: Der Planungskern verhindert gierige Einzelzuordnungen und priorisiert zunächst parallele Erststarts aller geeigneten Fahrzeuge. "
            "Die Gewichtungen werden für den nächsten Simulationslauf gespeichert."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        footer.addWidget(note, 1)
        close_button = QPushButton("Schließen")
        close_button.clicked.connect(self.accept)
        footer.addWidget(close_button)
        root.addLayout(footer)

    @staticmethod
    def _metric(caption: str, value) -> QFrame:
        frame = QFrame()
        frame.setObjectName("metric")
        layout = QVBoxLayout(frame)
        number = QLabel(str(value))
        number.setObjectName("metricValue")
        label = QLabel(caption)
        label.setObjectName("muted")
        label.setWordWrap(True)
        layout.addWidget(number)
        layout.addWidget(label)
        return frame


    def _apply_plan(self):
        if self.apply_callback is None:
            return
        answer = QMessageBox.question(
            self,
            "Planung übernehmen",
            f"Soll {getattr(self.selected_variant, 'name', 'die ausgewählte Variante')} jetzt übernommen werden?\n\n"
            "Es werden ausschließlich zulässige Touren gespeichert.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            selected_result = (
                getattr(self.selected_variant, "simulation_result", None)
                if self.selected_variant is not None else self.result
            ) or self.result
            created, assigned = self.apply_callback(selected_result)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Planung übernehmen",
                f"Die Planung konnte nicht übernommen werden:\n{error}",
            )
            return
        QMessageBox.information(
            self,
            "Planung übernommen",
            f"{assigned} Aufträge wurden disponiert. {created} zusätzliche Touren wurden angelegt.",
        )
        self.accept()



    def _show_replay(self):
        self._tabs.setCurrentIndex(self._replay_tab_index)

    def _replay_tab(self) -> QWidget:
        from leipzigerflow.planner.engine.facade import PlanningEngine
        widget = QWidget(); layout = QVBoxLayout(widget)
        info = QLabel("Der Replay zeigt die tatsächlichen Entscheidungsschritte in zeitlicher Reihenfolge und verändert keine Planung.")
        info.setWordWrap(True); info.setObjectName("muted"); layout.addWidget(info)
        table = QTableWidget(0, 4); table.setHorizontalHeaderLabels(["Schritt", "Phase", "Entscheidung", "Details"])
        replay = PlanningEngine.replay(self.result)
        for step in replay.steps:
            row = table.rowCount(); table.insertRow(row)
            self._set_row(table, row, [str(step.sequence), step.phase, step.message, step.details])
        if replay.is_empty:
            table.setRowCount(1); self._set_row(table, 0, ["–", "Kein Replay", "", ""])
        self._finish_table(table); layout.addWidget(table); return widget

    def _planning_trace_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Schritt", "Phase", "Ergebnis", "Details"])
        for entry in getattr(self.result, "planning_trace", []) or []:
            row = table.rowCount()
            table.insertRow(row)
            self._set_row(table, row, [str(entry.sequence), entry.phase.value, entry.message, entry.details])
        if table.rowCount() == 0:
            table.setRowCount(1)
            self._set_row(table, 0, ["–", "Kein Verlauf", "", ""])
        self._finish_table(table)
        layout.addWidget(table)
        return widget

    def _variants_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        info = QLabel(
            "Jede Zeile ist ein vollständig berechneter, zulässiger Planungsvorschlag. "
            "Die Empfehlung ist nur eine fachliche Bewertung; Sie können bewusst jede andere Variante auswählen."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._variant_selection_label = QLabel()
        self._variant_selection_label.setObjectName("warningBox")
        self._variant_selection_label.setWordWrap(True)
        layout.addWidget(self._variant_selection_label)

        table = QTableWidget(0, 12)
        self._variant_table = table
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setHorizontalHeaderLabels([
            "Variante", "Strategie", "Bewertung", "Fahrzeuge", "Touren", "Intern",
            "Offen", "Verkauf", "Leerfahrt", "Max. Arbeitszeit", "Empfohlen", "Beschreibung",
        ])
        variants = getattr(self.result, "planning_variants", []) or []
        selected_row = 0
        for variant in variants:
            row = table.rowCount()
            table.insertRow(row)
            table.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))
            self._set_row(table, row, [
                variant.name, variant.strategy.value, f"{variant.score} %",
                str(variant.vehicle_count), str(variant.tour_count), str(variant.assigned_orders),
                str(getattr(variant, "open_orders", 0)), str(getattr(variant, "subcontractor_orders", 0)),
                f"{getattr(variant, 'empty_run_minutes', 0)} min",
                f"{getattr(variant, 'max_vehicle_minutes', 0) // 60}:{getattr(variant, 'max_vehicle_minutes', 0) % 60:02d} h",
                "★ Empfohlen" if variant.recommended else "Alternative", variant.description,
            ])
            first = table.item(row, 0)
            if first is not None:
                first.setData(Qt.ItemDataRole.UserRole, variant)
            if variant is self.selected_variant:
                selected_row = row
        if table.rowCount() == 0:
            table.setRowCount(1)
            self._set_row(table, 0, ["Keine Varianten"] + [""] * 11)
        else:
            table.selectRow(selected_row)
        table.itemSelectionChanged.connect(self._variant_selected)
        table.itemDoubleClicked.connect(lambda _item: self._apply_plan())
        self._finish_table(table)
        layout.addWidget(table, 1)

        comparison = QLabel(
            "Auswahlhinweis: Varianten mit mehr Leerfahrt oder ungünstigerer Fahrzeugposition bleiben auswählbar, "
            "solange keine harte Regel verletzt wird. Arbeitszeiten über 10:00 Stunden werden nie angeboten."
        )
        comparison.setObjectName("muted")
        comparison.setWordWrap(True)
        layout.addWidget(comparison)
        self._update_variant_selection_label()
        return widget

    def _variant_selected(self):
        table = getattr(self, "_variant_table", None)
        if table is None:
            return
        row = table.currentRow()
        item = table.item(row, 0) if row >= 0 else None
        variant = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if variant is not None:
            self.selected_variant = variant
            self._update_variant_selection_label()

    def _update_variant_selection_label(self):
        label = getattr(self, "_variant_selection_label", None)
        if label is None:
            return
        variant = self.selected_variant
        if variant is None:
            label.setText("Keine Planungsvariante ausgewählt.")
            return
        reasons = " · ".join(getattr(variant, "reasons", []) or [])
        marker = "★ Empfohlen" if getattr(variant, "recommended", False) else "Manuell gewählte Alternative"
        label.setText(f"{marker}: {variant.name} · Bewertung {variant.score} %\n{reasons}")

    def _tours_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        table = QTableWidget(0, 15)
        table.setHorizontalHeaderLabels([
            "Tourvorschlag", "Vortour", "Fahrzeug", "Fahrer", "Aufträge",
            "Start", "Ende", "Strecke", "Fahrzeit", "Ø Score", "Cluster", "Clusterqualität", "Begründung", "Toursegmente", "Auftragsfolge",
        ])
        for tour in getattr(self.result, "proposed_tours", []) or []:
            row = table.rowCount()
            table.insertRow(row)
            values = [
                tour.proposal_number,
                tour.source_tour_number or "Neue Tour",
                tour.vehicle_label,
                tour.driver_label,
                str(tour.order_count),
                tour.planned_start_at.strftime("%d.%m.%Y %H:%M") if tour.planned_start_at else "–",
                tour.planned_end_at.strftime("%d.%m.%Y %H:%M") if tour.planned_end_at else "–",
                (f"{tour.total_distance_km:.1f} km" + (" geschätzt" if tour.distance_estimated else "")) if tour.total_distance_km is not None else "nicht verfügbar",
                f"{tour.total_route_minutes // 60}:{tour.total_route_minutes % 60:02d} h" if tour.total_route_minutes else "–",
                f"{tour.average_score:.1f}",
                getattr(tour, "cluster_label", ""),
                f"{getattr(tour, 'cluster_score', 0)} %",
                "; ".join(getattr(tour, "cluster_reasons", []) or []),
                " | ".join(
                    f"{segment.segment_type.value}: {segment.origin_label} → {segment.destination_label} "
                    f"({segment.duration_minutes} Min.)"
                    for segment in (getattr(tour, "segments", []) or [])
                ),
                " → ".join(item.order_number for item in tour.assignments),
            ]
            self._set_row(table, row, values)
        if table.rowCount() == 0:
            table.setRowCount(1)
            self._set_row(table, 0, ["Keine Touren gebildet"] + [""] * 14)
        self._finish_table(table)
        layout.addWidget(table)
        return widget

    def _export_excel(self):
        default_name = f"Planungsvorschlag_{self.result.created_at:%Y-%m-%d_%H-%M}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Planungsvorschlag exportieren",
            default_name,
            "Excel-Arbeitsmappe (*.xlsx)",
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            export_dispatch_proposal(path, self.result, self.resources)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Excel-Export",
                f"Der Planungsvorschlag konnte nicht exportiert werden:\n{error}",
            )
            return
        QMessageBox.information(
            self,
            "Excel-Export",
            "Der Planungsvorschlag wurde erfolgreich exportiert.",
        )

    def _show_evaluation(self):
        """Open the evaluation tab explicitly, even on narrow displays."""
        self._tabs.setCurrentIndex(self._evaluation_tab_index)

    def _edit_weights(self):
        dialog = DispatchWeightsDialog(self.weights, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        DispatchConfigurationStore().save(dialog.weights())
        self.accept()

    def _assignments_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        table = QTableWidget(0, 14)
        table.setHorizontalHeaderLabels([
            "Auftrag", "Planungsart", "Vortour", "Fahrzeug", "Fahrer",
            "Ladebeginn", "Wieder frei", "Entfernung", "Fahrzeit", "Anfahrt", "Wartezeit", "Score",
            "Entscheidungsgründe", "Status",
        ])
        for item in self.result.assignments:
            row = table.rowCount()
            table.insertRow(row)
            values = [
                item.order_number,
                item.mode.value,
                item.source_tour_number or "–",
                item.vehicle_label,
                item.driver_label,
                item.loading_at.strftime("%d.%m.%Y %H:%M"),
                item.available_again_at.strftime("%d.%m.%Y %H:%M"),
                (f"{item.route_distance_km:.1f} km" + (" (geschätzt)" if item.route_estimated else ""))
                if item.route_distance_km is not None else "nicht verfügbar",
                f"{item.route_duration_minutes // 60}:{item.route_duration_minutes % 60:02d} h"
                if item.route_duration_minutes else "–",
                f"{item.transfer_minutes} min",
                f"{item.waiting_minutes} min",
                str(item.score),
                "\n".join(item.reasons),
                ("Gleichwertige Alternativen" if getattr(item, "equivalent_best", False) else f"{item.confidence_label} ({item.confidence_percent} % )"),
            ]
            self._set_row(table, row, values)
        self._finish_table(table)
        layout.addWidget(table)
        return widget


    def _suggestions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        info = QLabel(
            "Diese Hinweise verändern keine Daten. Sie zeigen Umbuchungen, Bündelungen, "
            "Auslastungsunterschiede und verbleibende Engpässe für die fachliche Entscheidung."
        )
        info.setWordWrap(True)
        info.setObjectName("muted")
        layout.addWidget(info)
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels([
            "Stufe", "Kategorie", "Vorschlag", "Begründung", "Nutzen", "Betroffene Aufträge"
        ])
        for suggestion in getattr(self.result, "suggestions", []) or []:
            row = table.rowCount()
            table.insertRow(row)
            self._set_row(table, row, [
                suggestion.severity, suggestion.category, suggestion.title,
                suggestion.description, suggestion.benefit,
                ", ".join(suggestion.affected_orders) or "–",
            ])
        if table.rowCount() == 0:
            table.setRowCount(1)
            self._set_row(table, 0, ["Hinweis", "Planqualität", "Keine Vorschläge", "", "", ""])
        self._finish_table(table)
        layout.addWidget(table)
        return widget

    def _alternatives_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        table = QTableWidget(0, 8)
        table.setHorizontalHeaderLabels([
            "Auftrag", "Rang", "Fahrzeug", "Fahrer", "Planungsart",
            "Ladebeginn", "Score", "Bewertung / Ablehnung",
        ])
        for assignment in self.result.assignments:
            for rank, alternative in enumerate(assignment.alternatives, start=2):
                row = table.rowCount()
                table.insertRow(row)
                values = [
                    assignment.order_number,
                    str(rank),
                    alternative.vehicle_label,
                    alternative.driver_label,
                    alternative.mode.value,
                    alternative.loading_at.strftime("%d.%m.%Y %H:%M") if alternative.loading_at else "–",
                    str(alternative.score),
                    "\n".join(alternative.reasons),
                ]
                self._set_row(table, row, values)
        if table.rowCount() == 0:
            table.setRowCount(1)
            self._set_row(table, 0, ["Keine Alternativen vorhanden"] + [""] * 7)
        self._finish_table(table)
        layout.addWidget(table)
        return widget

    def _unassigned_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels([
            "Auftrag", "Priorität", "Grund", "Beste geprüfte Alternative", "Empfehlung"
        ])
        for item in self.result.unassigned:
            best = item.alternatives[0] if item.alternatives else None
            alternative_text = "–"
            if best:
                alternative_text = (
                    f"{best.vehicle_label} · Score {best.score}\n" + "\n".join(best.reasons)
                )
            row = table.rowCount()
            table.insertRow(row)
            values = [
                item.order_number,
                str(item.priority_score),
                "\n".join(item.reasons),
                alternative_text,
                "Subunternehmer prüfen" if item.subcontractor_recommended else "Intern prüfen",
            ]
            self._set_row(table, row, values)
        self._finish_table(table)
        layout.addWidget(table)
        return widget

    def _kpi_tab(self) -> QWidget:
        """Create a robust, always-visible summary without relying on table rendering."""
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        headline = QLabel("Planungsauswertung")
        headline.setObjectName("sectionTitle")
        outer.addWidget(headline)

        explanation = QLabel(
            "Diese Kennzahlen beziehen sich auf den aktuellen Simulationslauf. "
            "Die Simulation verändert noch keine Touren oder Aufträge."
        )
        explanation.setObjectName("muted")
        explanation.setWordWrap(True)
        outer.addWidget(explanation)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(10)

        sections = [
            ("Planungsergebnis", [
                ("Offene Ladungen", self.result.orders_total),
                ("Intern disponiert", self.result.assigned_count),
                ("Bleiben offen", self.result.open_count),
                ("Subunternehmer empfohlen", self.result.subcontractor_count),
            ]),
            ("Tourenbildung", [
                ("Bestehende Touren erweitert", self.result.extended_tour_count),
                ("Neue Touren gebildet", self.result.new_tour_count),
                ("Eingesetzte Fahrzeuge", f"{self.result.utilized_vehicle_count} von {self.result.resources_total}"),
                ("Fahrzeugnutzung", f"{self.result.utilization_percent:.1f} %"),
            ]),
            ("Qualität und Zeit", [
                ("Durchschnittlicher Vorschlags-Score", f"{self.result.average_score:.1f}"),
                ("Geschätzte Anfahrtszeit", self._duration(self.result.total_transfer_minutes)),
                ("Geschätzte Wartezeit", self._duration(self.result.total_waiting_minutes)),
                ("Berechnungsdauer", f"{self.result.simulation_seconds:.3f} Sekunden"),
            ]),
        ]

        for title, values in sections:
            section = QFrame()
            section.setObjectName("summarySection")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(14, 12, 14, 12)
            section_layout.setSpacing(7)
            section_title = QLabel(title)
            section_title.setObjectName("summaryTitle")
            section_layout.addWidget(section_title)
            for label_text, value in values:
                row = QHBoxLayout()
                label = QLabel(str(label_text))
                label.setObjectName("summaryLabel")
                value_label = QLabel(str(value))
                value_label.setObjectName("summaryValue")
                value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row.addWidget(label, 1)
                row.addWidget(value_label)
                section_layout.addLayout(row)
            content_layout.addWidget(section)

        if self.result.orders_total == 0:
            hint = QLabel(
                "Für den gewählten Planungstag wurden keine offenen Ladungen gefunden. "
                "Die Auswertung zeigt deshalb ausschließlich Nullwerte."
            )
            hint.setObjectName("warningBox")
            hint.setWordWrap(True)
            content_layout.addWidget(hint)
        elif self.result.assigned_count == 0:
            hint = QLabel(
                "Keine offene Ladung konnte intern zugeordnet werden. Prüfen Sie im Register "
                "„Offene Aufträge“ die konkreten Ablehnungsgründe."
            )
            hint.setObjectName("warningBox")
            hint.setWordWrap(True)
            content_layout.addWidget(hint)

        content_layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        return container

    def _capacity_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        info = QLabel(
            "Freie Zeit wird als aktives Umsatzpotenzial angezeigt. Fahrzeuge mit deutlicher "
            "Unterauslastung sollten möglichst eine zusätzliche eingekaufte Tour erhalten."
        )
        info.setWordWrap(True)
        info.setObjectName("muted")
        layout.addWidget(info)
        table = QTableWidget(0, 8)
        table.setHorizontalHeaderLabels([
            "Fahrzeug", "Aufbau", "Kapazität", "Geplant", "Frei",
            "Auslastung", "Zusätzliche Touren", "Empfehlung",
        ])
        for capacity in getattr(self.result, "vehicle_capacities", []) or []:
            row = table.rowCount()
            table.insertRow(row)
            self._set_row(table, row, [
                capacity.vehicle_label, capacity.trailer_type,
                self._duration(capacity.available_minutes),
                self._duration(capacity.planned_minutes),
                self._duration(capacity.free_minutes),
                f"{capacity.utilization_percent:.1f} %",
                str(capacity.suggested_additional_tours),
                capacity.recommendation,
            ])
        if table.rowCount() == 0:
            table.setRowCount(1)
            self._set_row(table, 0, ["Keine Kapazitätsdaten vorhanden"] + [""] * 7)
        self._finish_table(table)
        layout.addWidget(table)
        return widget

    def _resources_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        table = QTableWidget(0, 9)
        table.setHorizontalHeaderLabels([
            "Fahrzeug", "Klasse", "Fahrer", "Verfügbar ab", "Standort",
            "Zustand", "Vortour", "Tournummer", "Herleitung",
        ])
        for resource in self.resources:
            row = table.rowCount()
            table.insertRow(row)
            values = [
                resource.vehicle_label,
                resource.vehicle_class.value,
                resource.driver_label,
                resource.available_at.strftime("%d.%m.%Y %H:%M"),
                resource.location_label,
                resource.state.value,
                str(resource.source_tour_id or "–"),
                resource.source_tour_number or "–",
                resource.reason,
            ]
            self._set_row(table, row, values)
        self._finish_table(table)
        layout.addWidget(table)
        return widget

    def _weights_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        text = QLabel(
            "Die folgenden Gewichtungen wurden für diesen Planungslauf verwendet. "
            "Über „Gewichtungen …“ können sie für den nächsten Lauf geändert werden."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Kriterium", "Gewichtung"])
        for field_info in fields(DispatchWeights):
            row = table.rowCount()
            table.insertRow(row)
            self._set_row(table, row, [
                WEIGHT_LABELS.get(field_info.name, field_info.name),
                f"{getattr(self.weights, field_info.name)} %",
            ])
        self._finish_table(table)
        layout.addWidget(table)
        return widget

    @staticmethod
    def _duration(minutes: int) -> str:
        hours, remainder = divmod(int(minutes), 60)
        return f"{hours}:{remainder:02d} h"

    @staticmethod
    def _set_row(table: QTableWidget, row: int, values: list[str]) -> None:
        for column, value in enumerate(values):
            cell = QTableWidgetItem(str(value))
            cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            cell.setToolTip(str(value))
            table.setItem(row, column, cell)

    @staticmethod
    def _finish_table(table: QTableWidget) -> None:
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        table.setWordWrap(True)

    @staticmethod
    def _stylesheet() -> str:
        return """
        QDialog { background:#f8fafc; color:#0f172a; }
        QLabel#title { font-size:22px; font-weight:800; }
        QLabel#sectionTitle { font-size:17px; font-weight:750; }
        QLabel#muted { color:#64748b; }
        QFrame#metric { background:#ffffff; border:1px solid #dbe3ee; border-radius:9px; padding:8px; }
        QFrame#summarySection { background:#ffffff; border:1px solid #dbe3ee; border-radius:9px; }
        QLabel#summaryTitle { font-size:15px; font-weight:800; color:#0f172a; }
        QLabel#summaryLabel { color:#334155; font-size:13px; }
        QLabel#summaryValue { color:#1d4ed8; font-size:14px; font-weight:800; }
        QLabel#warningBox { background:#fff7ed; color:#9a3412; border:1px solid #fdba74; border-radius:7px; padding:10px; }
        QScrollArea { background:transparent; }
        QLabel#metricValue { font-size:22px; font-weight:800; color:#1d4ed8; }
        QTableWidget { background:#ffffff; alternate-background-color:#f8fafc; gridline-color:#e2e8f0; }
        QHeaderView::section { background:#e2e8f0; color:#0f172a; padding:7px; border:none; font-weight:700; }
        QPushButton { color:#0f172a; background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:7px 13px; }
        QPushButton:hover { background:#e2e8f0; }
        QSpinBox { color:#0f172a; background:#ffffff; border:1px solid #cbd5e1; padding:5px; }
        QTabWidget::pane { border:1px solid #cbd5e1; background:#ffffff; top:-1px; }
        QTabBar::tab { color:#0f172a; background:#e2e8f0; border:1px solid #cbd5e1; padding:8px 13px; margin-right:2px; }
        QTabBar::tab:selected { color:#ffffff; background:#1d4ed8; border-color:#1d4ed8; font-weight:700; }
        QTabBar::tab:hover:!selected { background:#cbd5e1; color:#0f172a; }
        """


class MultiDayDispatchSimulationDialog(QDialog):
    """Detailed review and apply dialog for a complete planning horizon."""

    def __init__(self, result, parent=None, apply_callback=None):
        super().__init__(parent)
        self.result = result
        self.apply_callback = apply_callback
        self.setWindowTitle("Automatische Disposition · Mehrtagesplanung")
        self.resize(1380, 820)
        self.setStyleSheet(DispatchSimulationDialog._stylesheet())

        root = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Automatische Disposition · Mehrtagesplanung")
        title.setObjectName("title")
        header.addWidget(title, 1)
        replay_button = QPushButton("Replay anzeigen")
        replay_button.clicked.connect(self._show_replay)
        header.addWidget(replay_button)
        if self.apply_callback is not None:
            apply_button = QPushButton("Gesamten Zeitraum übernehmen")
            apply_button.clicked.connect(self._apply_horizon)
            header.addWidget(apply_button)
        root.addLayout(header)

        end_day = result.start_day + timedelta(days=max(0, result.horizon_days - 1))
        info = QLabel(f"Planungszeitraum: {result.start_day:%d.%m.%Y} bis {end_day:%d.%m.%Y}. Alle Tage werden mit Vorschlägen, Alternativen und Entscheidungsverlauf dargestellt.")
        info.setWordWrap(True); info.setObjectName("muted"); root.addWidget(info)

        metrics = QHBoxLayout()
        metrics.addWidget(self._metric("Planungstage", result.horizon_days))
        metrics.addWidget(self._metric("Disponierte Aufträge", result.assigned_count))
        metrics.addWidget(self._metric("Offene Aufträge", result.open_count))
        metrics.addWidget(self._metric("Tourvorschläge", sum(getattr(r, "proposed_tour_count", 0) for r in result.daily_results.values())))
        root.addLayout(metrics)

        self._tabs = QTabWidget()
        self._overview_index = self._tabs.addTab(self._overview_tab(), "Tagesübersicht")
        self._tabs.addTab(self._assignments_tab(), "Vorschläge")
        self._tabs.addTab(self._alternatives_tab(), "Alternativen")
        self._tabs.addTab(self._open_orders_tab(), "Offene Aufträge")
        self._replay_index = self._tabs.addTab(self._replay_tab(), "Replay")
        self._tabs.setCurrentIndex(self._overview_index)
        root.addWidget(self._tabs, 1)

        close_button = QPushButton("Schließen")
        close_button.clicked.connect(self.reject)
        footer = QHBoxLayout(); footer.addStretch(1); footer.addWidget(close_button); root.addLayout(footer)

    @staticmethod
    def _metric(caption: str, value) -> QFrame:
        return DispatchSimulationDialog._metric(caption, value)

    @staticmethod
    def _finish(table):
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

    def _overview_tab(self):
        widget=QWidget(); layout=QVBoxLayout(widget); table=QTableWidget(0,8)
        table.setHorizontalHeaderLabels(["Tag","Aufträge","Disponiert","Offen","Touren","Fahrzeuge","Leerfahrt","Strategie"])
        for day,r in sorted(self.result.daily_results.items()):
            row=table.rowCount(); table.insertRow(row)
            values=[day.strftime("%A, %d.%m.%Y"),getattr(r,'orders_total',0),getattr(r,'assigned_count',0),getattr(r,'open_count',0),getattr(r,'proposed_tour_count',0),getattr(r,'utilized_vehicle_count',0),f"{getattr(r,'total_transfer_minutes',0)} min",getattr(getattr(r,'planning_strategy',None),'value','Mehrtagesplanung')]
            for c,v in enumerate(values): table.setItem(row,c,QTableWidgetItem(str(v)))
        self._finish(table); layout.addWidget(table); return widget

    def _assignments_tab(self):
        widget=QWidget(); layout=QVBoxLayout(widget); table=QTableWidget(0,10)
        table.setHorizontalHeaderLabels(["Tag","Auftrag","Fahrzeug","Fahrer","Ladebeginn","Wieder frei","Anfahrt","Wartezeit","Score","Entscheidungsgründe"])
        for day,r in sorted(self.result.daily_results.items()):
            for a in getattr(r,'assignments',[]) or []:
                row=table.rowCount(); table.insertRow(row)
                values=[day.strftime('%d.%m.%Y'),a.order_number,a.vehicle_label,a.driver_label,a.loading_at.strftime('%d.%m.%Y %H:%M'),a.available_again_at.strftime('%d.%m.%Y %H:%M'),f"{a.transfer_minutes} min",f"{a.waiting_minutes} min",a.score,"; ".join(a.reasons)]
                for c,v in enumerate(values): table.setItem(row,c,QTableWidgetItem(str(v)))
        self._finish(table); layout.addWidget(table); return widget

    def _alternatives_tab(self):
        widget=QWidget(); layout=QVBoxLayout(widget); table=QTableWidget(0,9)
        table.setHorizontalHeaderLabels(["Tag","Auftrag","Rang","Fahrzeug","Fahrer","Planungsart","Ladebeginn","Score","Bewertung / Ablehnung"])
        for day,r in sorted(self.result.daily_results.items()):
            for a in getattr(r,'assignments',[]) or []:
                for rank,alt in enumerate(getattr(a,'alternatives',[]) or [],2):
                    row=table.rowCount(); table.insertRow(row)
                    values=[day.strftime('%d.%m.%Y'),a.order_number,rank,alt.vehicle_label,alt.driver_label,getattr(alt.mode,'value',str(alt.mode)),alt.loading_at.strftime('%d.%m.%Y %H:%M') if alt.loading_at else '–',alt.score,"; ".join(alt.reasons)]
                    for c,v in enumerate(values): table.setItem(row,c,QTableWidgetItem(str(v)))
        if table.rowCount()==0:
            table.setRowCount(1); table.setItem(0,0,QTableWidgetItem("Keine Alternativen vorhanden"))
        self._finish(table); layout.addWidget(table); return widget

    def _open_orders_tab(self):
        widget=QWidget(); layout=QVBoxLayout(widget); table=QTableWidget(0,5)
        table.setHorizontalHeaderLabels(["Tag","Auftrag","Priorität","Grund","Empfehlung"])
        for day,r in sorted(self.result.daily_results.items()):
            for item in getattr(r,'unassigned',[]) or []:
                row=table.rowCount(); table.insertRow(row)
                values=[day.strftime('%d.%m.%Y'),item.order_number,item.priority_score,"; ".join(item.reasons),"Subunternehmer prüfen" if item.subcontractor_recommended else "Intern prüfen"]
                for c,v in enumerate(values): table.setItem(row,c,QTableWidgetItem(str(v)))
        self._finish(table); layout.addWidget(table); return widget

    def _replay_tab(self):
        from leipzigerflow.planner.engine.facade import PlanningEngine
        widget=QWidget(); layout=QVBoxLayout(widget); table=QTableWidget(0,5)
        table.setHorizontalHeaderLabels(["Schritt","Tag","Phase","Entscheidung","Details"])
        replay=PlanningEngine.replay(self.result)
        for step in replay.steps:
            row=table.rowCount(); table.insertRow(row)
            values=[step.sequence,step.planning_day.strftime('%d.%m.%Y') if step.planning_day else '–',step.phase,step.message,step.details]
            for c,v in enumerate(values): table.setItem(row,c,QTableWidgetItem(str(v)))
        if replay.is_empty:
            table.setRowCount(1); table.setItem(0,0,QTableWidgetItem("Kein Replay vorhanden"))
        self._finish(table); layout.addWidget(table); return widget

    def _show_replay(self):
        self._tabs.setCurrentIndex(self._replay_index)

    def _apply_horizon(self):
        answer = QMessageBox.question(self,"Mehrtagesplanung übernehmen",f"Sollen die Touren für alle {self.result.horizon_days} Planungstage gespeichert werden?")
        if answer != QMessageBox.StandardButton.Yes: return
        try: created, assigned = self.apply_callback(self.result)
        except Exception as error:
            QMessageBox.critical(self,"Mehrtagesplanung übernehmen",f"Die Planung konnte nicht vollständig übernommen werden:\n{error}"); return
        QMessageBox.information(self,"Mehrtagesplanung übernommen",f"{assigned} Aufträge wurden über {self.result.horizon_days} Tage disponiert. {created} zusätzliche Touren wurden angelegt.")
        self.accept()


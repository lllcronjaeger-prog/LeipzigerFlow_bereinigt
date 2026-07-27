import json

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from leipzigerflow.services.tour_service import TourService, TourValidationError
from leipzigerflow.ui.models.tour_order_table_model import (
    ORDER_MIME_TYPE,
    TOUR_ORDER_MIME_TYPE,
    TourOrderTableModel,
)


class AssignedOrderDropTable(QTableView):
    ordersDropped = Signal(list, int)
    orderReordered = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat(ORDER_MIME_TYPE) or mime.hasFormat(TOUR_ORDER_MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat(ORDER_MIME_TYPE) or mime.hasFormat(TOUR_ORDER_MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        row = self.indexAt(event.position().toPoint()).row()
        if row < 0:
            row = self.model().rowCount()

        mime = event.mimeData()
        try:
            if mime.hasFormat(TOUR_ORDER_MIME_TYPE):
                ids = json.loads(bytes(mime.data(TOUR_ORDER_MIME_TYPE)).decode("utf-8"))
                if ids:
                    self.orderReordered.emit(int(ids[0]), row)
                    event.acceptProposedAction()
                    return
            if mime.hasFormat(ORDER_MIME_TYPE):
                ids = json.loads(bytes(mime.data(ORDER_MIME_TYPE)).decode("utf-8"))
                self.ordersDropped.emit([int(value) for value in ids], row)
                event.acceptProposedAction()
                return
        except (ValueError, TypeError, json.JSONDecodeError):
            event.ignore()
            return
        super().dropEvent(event)


class UnassignedOrderDropTable(QTableView):
    ordersReturned = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(TOUR_ORDER_MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(TOUR_ORDER_MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        mime = event.mimeData()
        if not mime.hasFormat(TOUR_ORDER_MIME_TYPE):
            super().dropEvent(event)
            return

        try:
            ids = json.loads(
                bytes(mime.data(TOUR_ORDER_MIME_TYPE)).decode("utf-8")
            )
            order_ids = [int(value) for value in ids]
        except (ValueError, TypeError, json.JSONDecodeError):
            event.ignore()
            return

        if not order_ids:
            event.ignore()
            return

        self.ordersReturned.emit(order_ids)
        event.acceptProposedAction()


class TourPlanningDialog(QDialog):
    def __init__(self, service: TourService, tour_id: int, parent=None):
        super().__init__(parent)
        self.service = service
        self.tour_id = tour_id
        self.tour = None
        self._all_unassigned = []

        self.setWindowTitle("Tour disponieren")
        self.resize(1500, 800)

        root = QVBoxLayout(self)
        self.header_label = QLabel()
        root.addWidget(self.header_label)

        hint = QLabel(
            "Aufträge können per Drag & Drop in die Tour gezogen, dort neu sortiert "
            "und zurück zu den nicht disponierten Aufträgen gezogen werden."
        )
        hint.setStyleSheet("color: #64748b; padding-bottom: 4px;")
        root.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("<b>Nicht disponierte Aufträge</b>"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Aufträge suchen …")
        self.search_edit.textChanged.connect(self._filter_unassigned)
        left_layout.addWidget(self.search_edit)

        self.unassigned_model = TourOrderTableModel()
        self.unassigned_table = UnassignedOrderDropTable()
        self._configure_table(self.unassigned_table, self.unassigned_model)
        self.unassigned_table.doubleClicked.connect(self._add_selected)
        self.unassigned_table.ordersReturned.connect(self._return_orders_to_unassigned)
        left_layout.addWidget(self.unassigned_table, 1)
        splitter.addWidget(left)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.addStretch()
        self.add_button = QPushButton(">>")
        self.remove_button = QPushButton("<<")
        self.add_button.clicked.connect(self._add_selected)
        self.remove_button.clicked.connect(self._remove_selected)
        center_layout.addWidget(self.add_button)
        center_layout.addWidget(self.remove_button)
        center_layout.addStretch()
        splitter.addWidget(center)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("<b>Aufträge dieser Tour</b>"))
        self.quality_label = QLabel()
        self.quality_label.setWordWrap(True)
        right_layout.addWidget(self.quality_label)
        self.assigned_model = TourOrderTableModel(show_position=True)
        self.assigned_table = AssignedOrderDropTable()
        self._configure_table(self.assigned_table, self.assigned_model)
        self.assigned_table.doubleClicked.connect(self._remove_selected)
        self.assigned_table.ordersDropped.connect(self._drop_unassigned_orders)
        self.assigned_table.orderReordered.connect(self._reorder_assigned_order)
        right_layout.addWidget(self.assigned_table, 1)

        move_row = QHBoxLayout()
        self.up_button = QPushButton("Nach oben")
        self.down_button = QPushButton("Nach unten")
        self.up_button.clicked.connect(lambda: self._move_selected(-1))
        self.down_button.clicked.connect(lambda: self._move_selected(1))
        move_row.addWidget(self.up_button)
        move_row.addWidget(self.down_button)
        self.analyze_button = QPushButton("Tourqualität prüfen")
        self.optimize_button = QPushButton("Reihenfolge optimieren")
        self.analyze_button.clicked.connect(self._show_tour_analysis)
        self.optimize_button.clicked.connect(self._optimize_tour_order)
        move_row.addWidget(self.analyze_button)
        move_row.addWidget(self.optimize_button)
        move_row.addStretch()
        right_layout.addLayout(move_row)

        splitter.addWidget(right)
        splitter.setSizes([650, 90, 650])

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_button = QPushButton("Schließen")
        close_button.clicked.connect(self.accept)
        close_row.addWidget(close_button)
        root.addLayout(close_row)
        self._refresh()

    @classmethod
    def _table(cls, model):
        table = QTableView()
        cls._configure_table(table, model)
        return table

    @staticmethod
    def _configure_table(table, model):
        table.setModel(model)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)
        table.horizontalHeader().setStretchLastSection(True)

    def _refresh(self) -> None:
        self.tour = self.service.get(self.tour_id)
        if self.tour is None:
            QMessageBox.warning(self, "Tour nicht gefunden", "Die Tour wurde nicht gefunden.")
            self.reject()
            return

        self.header_label.setText(
            "<h2>"
            f"{self.tour.tour_number} – {self.tour.tour_date.strftime('%d.%m.%Y')}"
            "</h2>"
            f"Fahrer: {self.tour.driver_display or 'offen'} &nbsp;&nbsp; "
            f"Fahrzeug: {self.tour.vehicle_display or 'offen'} &nbsp;&nbsp; "
            f"Status: {self.tour.status}"
        )
        self._all_unassigned = self.service.get_unassigned_orders()
        self._filter_unassigned()
        self.assigned_model.set_items(
            sorted(self.tour.positions, key=lambda item: item.position)
        )
        self.unassigned_table.resizeColumnsToContents()
        self.assigned_table.resizeColumnsToContents()
        self._update_quality_indicator()

    def _filter_unassigned(self, *_args) -> None:
        term = self.search_edit.text().strip().casefold()
        orders = self._all_unassigned if not term else [
            order for order in self._all_unassigned if term in order.search_text.casefold()
        ]
        self.unassigned_model.set_items(orders)

    @staticmethod
    def _selected_items(table, model):
        selection = table.selectionModel()
        rows = selection.selectedRows() if selection else []
        return [model.item_at(row.row()) for row in rows if model.item_at(row.row())]

    @staticmethod
    def _selected_item(table, model):
        items = TourPlanningDialog._selected_items(table, model)
        return items[0] if items else None

    def _add_selected(self, *_args) -> None:
        orders = self._selected_items(self.unassigned_table, self.unassigned_model)
        if not orders:
            return
        self._assign_orders(orders, None)

    def _drop_unassigned_orders(self, order_ids: list[int], target_row: int) -> None:
        by_id = {order.id: order for order in self._all_unassigned}
        orders = [by_id[order_id] for order_id in order_ids if order_id in by_id]
        self._assign_orders(orders, target_row)

    def _assign_orders(self, orders, target_row: int | None) -> None:
        if not orders:
            return
        try:
            insert_at = target_row
            for order in orders:
                self.tour = self.service.add_order_at(self.tour, order, insert_at)
                if insert_at is not None:
                    insert_at += 1
        except TourValidationError as error:
            QMessageBox.warning(
                self,
                "Auftrag konnte nicht zugeordnet werden",
                str(error),
            )
            return
        except Exception as error:
            QMessageBox.critical(self, "Fehler bei der Disposition", str(error))
            return
        self._refresh()

    def _remove_selected(self, *_args) -> None:
        positions = self._selected_items(self.assigned_table, self.assigned_model)
        if not positions:
            return
        self._return_orders_to_unassigned(
            [position.transport_order_id for position in positions]
        )

    def _return_orders_to_unassigned(self, order_ids: list[int]) -> None:
        if not order_ids:
            return

        try:
            for order_id in order_ids:
                self.tour = self.service.remove_order(self.tour, order_id)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Auftrag konnte nicht zurückgesetzt werden",
                str(error),
            )
            return

        self._refresh()

    def _reorder_assigned_order(self, order_id: int, target_row: int) -> None:
        try:
            self.tour = self.service.reorder_order(self.tour, order_id, target_row)
        except Exception as error:
            QMessageBox.critical(self, "Reihenfolge konnte nicht geändert werden", str(error))
            return
        self._refresh()
        self._select_assigned_order(order_id)

    def _move_selected(self, direction: int) -> None:
        position = self._selected_item(self.assigned_table, self.assigned_model)
        if position is None:
            return
        order_id = position.transport_order_id
        self.tour = self.service.move_order(self.tour, order_id, direction)
        self._refresh()
        self._select_assigned_order(order_id)

    def _select_assigned_order(self, order_id: int) -> None:
        for row in range(self.assigned_model.rowCount()):
            item = self.assigned_model.item_at(row)
            if item and item.transport_order_id == order_id:
                self.assigned_table.selectRow(row)
                self.assigned_table.scrollTo(self.assigned_model.index(row, 0))
                break

    def _tour_analysis(self):
        return self.service.analyze_multi_stop_tour(self.tour)

    def _update_quality_indicator(self) -> None:
        if not self.tour or not self.tour.positions:
            self.quality_label.setText("Tourqualität: noch keine Aufträge")
            self.quality_label.setStyleSheet("color: #64748b; padding: 4px;")
            self.optimize_button.setEnabled(False)
            return
        self.optimize_button.setEnabled(len(self.tour.positions) > 1)
        result = self._tour_analysis()
        plan = result.current
        if plan.quality_score >= 85:
            background = "#dcfce7"
            foreground = "#166534"
        elif plan.quality_score >= 60:
            background = "#fef3c7"
            foreground = "#92400e"
        else:
            background = "#fee2e2"
            foreground = "#991b1b"
        distance_text = (
            f"{plan.total_distance_km:.1f} km"
            if plan.total_distance_km is not None
            else "nicht vollständig berechenbar"
        )
        empty_text = (
            f"{plan.empty_distance_km:.1f} km"
            if plan.empty_distance_km is not None
            else "–"
        )
        self.quality_label.setText(
            f"<b>Tourqualität: {plan.quality_score} % – {plan.quality_label}</b> &nbsp; "
            f"Strecke: <b>{distance_text}</b> &nbsp; "
            f"Leer-km: <b>{empty_text}</b> &nbsp; "
            f"Fahrzeit: <b>{plan.total_drive_minutes} Min.</b> &nbsp; "
            f"Wartezeit: {plan.total_waiting_minutes} Min."
        )
        self.quality_label.setStyleSheet(
            f"background: {background}; color: {foreground}; padding: 7px; border-radius: 4px;"
        )

    def _show_tour_analysis(self) -> None:
        result = self._tour_analysis()
        current = result.current
        optimized = result.optimized
        current_distance = (
            f"{current.total_distance_km:.1f} km"
            if current.total_distance_km is not None else "unvollständig"
        )
        optimized_distance = (
            f"{optimized.total_distance_km:.1f} km"
            if optimized.total_distance_km is not None else "unvollständig"
        )
        lines = [
            f"Aktuelle Qualität: {current.quality_score} % ({current.quality_label})",
            f"Optimierbare Qualität: {optimized.quality_score} % ({optimized.quality_label})",
            f"Gesamtstrecke aktuell/optimiert: {current_distance} / {optimized_distance}",
            f"Leerstrecke aktuell/optimiert: "
            f"{current.empty_distance_km or 0:.1f}/{optimized.empty_distance_km or 0:.1f} km",
            f"Fahrzeit aktuell/optimiert: {current.total_drive_minutes}/{optimized.total_drive_minutes} Min.",
            f"Wartezeit aktuell/optimiert: {current.total_waiting_minutes}/{optimized.total_waiting_minutes} Min.",
            f"Transfer aktuell/optimiert: {current.total_transfer_minutes}/{optimized.total_transfer_minutes} Min.",
        ]
        if not current.has_complete_distance_data:
            lines.append(
                "Hinweis: Noch keine echte Routing-Schnittstelle verbunden; "
                "unbekannte Transferzeiten werden konservativ geschätzt."
            )
        if optimized.violations:
            lines.append("")
            lines.append("Zeitfensterhinweise:")
            lines.extend(f"• {item.order_number}: {item.message}" for item in optimized.violations)
        elif result.changed:
            lines.append("")
            lines.append("Eine bessere Reihenfolge wurde gefunden.")
        else:
            lines.append("")
            lines.append("Die aktuelle Reihenfolge ist bereits die beste geprüfte Variante.")
        QMessageBox.information(self, "Tourqualität", "\n".join(lines))

    def _optimize_tour_order(self) -> None:
        result = self._tour_analysis()
        if not result.changed:
            QMessageBox.information(
                self,
                "Reihenfolge optimieren",
                "Die aktuelle Reihenfolge ist bereits die beste geprüfte Variante.",
            )
            return
        current_numbers = [stop.order_number for stop in result.current.stops]
        optimized_numbers = [stop.order_number for stop in result.optimized.stops]
        message = (
            f"Qualität: {result.current.quality_score} % → {result.optimized.quality_score} %\n"
            f"Wartezeit: {result.current.total_waiting_minutes} → "
            f"{result.optimized.total_waiting_minutes} Minuten\n\n"
            f"Bisher: {' → '.join(current_numbers)}\n"
            f"Vorschlag: {' → '.join(optimized_numbers)}\n\n"
            "Soll die optimierte Reihenfolge übernommen werden?"
        )
        answer = QMessageBox.question(
            self,
            "Optimierte Reihenfolge übernehmen",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.tour = self.service.apply_optimized_order(
                self.tour, result.optimized.order_ids
            )
        except Exception as error:
            QMessageBox.critical(
                self, "Optimierung konnte nicht übernommen werden", str(error)
            )
            return
        self._refresh()

from sqlalchemy import select
from sqlalchemy.orm import Session

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from leipzigerflow.ui.context_menu import create_context_menu
from leipzigerflow.models.customer import Customer
from leipzigerflow.models.location import Location
from leipzigerflow.services.transport_order_service import (
    TransportOrderService,
    TransportOrderValidationError,
)
from leipzigerflow.ui.dialogs.transport_order_edit_dialog import (
    TransportOrderEditDialog,
)
from leipzigerflow.ui.dialogs.transport_order_series_dialog import (
    TransportOrderSeriesDialog,
)
from leipzigerflow.ui.models.transport_order_table_model import (
    TransportOrderTableModel,
)


class TransportOrderDialog(QDialog):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self.service = TransportOrderService(session)
        self.setWindowTitle("Transportaufträge")
        self.resize(1450, 800)

        layout = QVBoxLayout(self)
        filter_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Interne Nummer, Kundenauftrag, Kunde, Standort oder Text suchen …"
        )
        self.search_edit.textChanged.connect(self._apply_filters)
        filter_row.addWidget(self.search_edit, 1)

        filter_row.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("Alle", "")
        for status in TransportOrderService.STATUSES:
            self.status_filter.addItem(status, status)
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.status_filter)

        filter_row.addWidget(QLabel("Typ:"))
        self.type_filter = QComboBox()
        self.type_filter.addItem("Alle", "")
        for order_type in TransportOrderService.ORDER_TYPES:
            self.type_filter.addItem(order_type, order_type)
        self.type_filter.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self.type_filter)
        layout.addLayout(filter_row)

        action_row = QHBoxLayout()
        self.new_button = QPushButton("Neu")
        self.edit_button = QPushButton("Bearbeiten")
        self.copy_button = QPushButton("Kopieren")
        self.series_button = QPushButton("Serie")
        self.delete_button = QPushButton("Löschen")
        self.new_button.clicked.connect(self._create_order)
        self.edit_button.clicked.connect(self._edit_order)
        self.copy_button.clicked.connect(self._copy_order)
        self.series_button.clicked.connect(self._create_series)
        self.delete_button.clicked.connect(self._delete_order)
        for button in (
            self.new_button, self.edit_button, self.copy_button,
            self.series_button, self.delete_button,
        ):
            action_row.addWidget(button)

        action_row.addSpacing(24)
        action_row.addWidget(QLabel("Status ändern:"))
        self.quick_status_combo = QComboBox()
        self.quick_status_combo.addItems(TransportOrderService.STATUSES)
        action_row.addWidget(self.quick_status_combo)
        self.apply_status_button = QPushButton("Übernehmen")
        self.apply_status_button.clicked.connect(self._apply_quick_status)
        action_row.addWidget(self.apply_status_button)
        action_row.addStretch()
        self.close_button = QPushButton("Schließen")
        self.close_button.clicked.connect(self.accept)
        action_row.addWidget(self.close_button)
        layout.addLayout(action_row)

        self.tabs = QTabWidget()
        self.active_model = TransportOrderTableModel()
        self.archive_model = TransportOrderTableModel()
        self.active_table = self._create_table(self.active_model)
        self.archive_table = self._create_table(self.archive_model)
        self.tabs.addTab(self._table_page(self.active_table), "Aktive Aufträge (0)")
        self.tabs.addTab(self._table_page(self.archive_table), "Archiv (0)")
        self.tabs.currentChanged.connect(self._tab_changed)
        layout.addWidget(self.tabs, 1)

        self._shortcuts = [
            QShortcut(QKeySequence("F2"), self, activated=lambda: self.search_edit.setFocus()),
            QShortcut(QKeySequence("F5"), self, activated=self._create_order),
            QShortcut(QKeySequence("Ctrl+D"), self, activated=self._copy_order),
            QShortcut(QKeySequence("Delete"), self, activated=self._delete_order),
        ]
        self._load_orders()

    def _create_table(self, model: TransportOrderTableModel) -> QTableView:
        table = QTableView()
        table.setModel(model)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(True)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.doubleClicked.connect(self._edit_order)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda position, source=table: self._open_context_menu(position, source)
        )
        return table

    @staticmethod
    def _table_page(table: QTableView) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(table)
        return page

    @property
    def table(self) -> QTableView:
        return self.archive_table if self.tabs.currentIndex() == 1 else self.active_table

    @property
    def model(self) -> TransportOrderTableModel:
        return self.archive_model if self.tabs.currentIndex() == 1 else self.active_model

    def _tab_changed(self, *_args) -> None:
        archived = self.tabs.currentIndex() == 1
        self.new_button.setEnabled(not archived)
        self.series_button.setEnabled(not archived)
        self.copy_button.setEnabled(not archived)
        self.delete_button.setText("Wieder aktivieren" if archived else "Löschen")
        try:
            self.table.setFocus()
        except RuntimeError:
            pass

    def _load_orders(self) -> None:
        self._apply_filters()
        self.active_table.resizeColumnsToContents()
        self.archive_table.resizeColumnsToContents()

    def _apply_filters(self, *_args) -> None:
        orders = self.service.search(
            search_text=self.search_edit.text(),
            status=str(self.status_filter.currentData() or ""),
            order_type=str(self.type_filter.currentData() or ""),
        )
        archived_statuses = {"Erledigt", "Storniert"}
        active = [order for order in orders if order.status not in archived_statuses]
        archived = [order for order in orders if order.status in archived_statuses]
        self.active_model.set_orders(active)
        self.archive_model.set_orders(archived)
        self.tabs.setTabText(0, f"Aktive Aufträge ({len(active)})")
        self.tabs.setTabText(1, f"Archiv ({len(archived)})")

    def _selected_orders(self):
        selection_model = self.table.selectionModel()
        rows = (
            selection_model.selectedRows()
            if selection_model
            else []
        )
        return [
            self.model.order_at(index.row())
            for index in sorted(
                rows,
                key=lambda item: item.row(),
            )
            if self.model.order_at(index.row()) is not None
        ]

    def _selected_order(self):
        orders = self._selected_orders()
        return orders[0] if orders else None

    def _require_selected_orders(self):
        selected = self._selected_orders()
        if not selected:
            QMessageBox.information(
                self,
                "Keine Auswahl",
                "Bitte mindestens einen Transportauftrag "
                "auswählen.",
            )
            return []
        return selected

    def _require_selected_order(self):
        selected = self._selected_order()
        if selected is None:
            QMessageBox.information(
                self,
                "Keine Auswahl",
                "Bitte einen Transportauftrag auswählen.",
            )
            return None
        return selected

    def _master_data(self):
        customers = list(
            self._session.scalars(
                select(Customer)
                .where(Customer.active.is_(True))
                .order_by(Customer.name)
            )
        )
        locations = list(
            self._session.scalars(
                select(Location)
                .where(Location.active.is_(True))
                .order_by(Location.name)
            )
        )
        return customers, locations

    def _create_order(self) -> None:
        customers, locations = self._master_data()

        if not customers:
            QMessageBox.warning(
                self,
                "Keine Kunden",
                "Bitte zuerst mindestens einen aktiven "
                "Kunden anlegen.",
            )
            return

        if not locations:
            QMessageBox.warning(
                self,
                "Keine Standorte",
                "Bitte zuerst mindestens einen aktiven "
                "Standort anlegen.",
            )
            return

        dialog = TransportOrderEditDialog(
            customers,
            locations,
            parent=self,
        )

        while (
            dialog.exec()
            == QDialog.DialogCode.Accepted
        ):
            try:
                created = self.service.create(
                    dialog.get_transport_order_data()
                )
            except TransportOrderValidationError as error:
                QMessageBox.warning(
                    self,
                    "Eingabe prüfen",
                    str(error),
                )
                continue

            self._load_orders()
            QMessageBox.information(
                self,
                "Transportauftrag angelegt",
                "Der Auftrag wurde mit der internen Nummer "
                f"{created.order_number} angelegt.",
            )
            return

    def _edit_order(self, *_args) -> None:
        selected = self._require_selected_order()
        if selected is None:
            return

        order = self.service.get(selected.id)
        if order is None:
            self._load_orders()
            return

        customers, locations = self._master_data()

        if (
            order.customer
            and all(
                item.id != order.customer.id
                for item in customers
            )
        ):
            customers.append(order.customer)

        for used_location in (
            order.loading_location,
            order.unloading_location,
        ):
            if (
                used_location
                and all(
                    item.id != used_location.id
                    for item in locations
                )
            ):
                locations.append(used_location)

        dialog = TransportOrderEditDialog(
            customers,
            locations,
            order=order,
            parent=self,
        )

        while (
            dialog.exec()
            == QDialog.DialogCode.Accepted
        ):
            try:
                self.service.update(
                    order,
                    dialog.get_transport_order_data(),
                )
            except TransportOrderValidationError as error:
                self._session.rollback()
                QMessageBox.warning(
                    self,
                    "Eingabe prüfen",
                    str(error),
                )
                continue

            self._load_orders()
            return

    def _copy_order(self) -> None:
        selected = self._require_selected_order()
        if selected is None:
            return

        source = self.service.get(selected.id)
        if source is None:
            self._load_orders()
            return

        created = self.service.copy(source)
        self._load_orders()

        QMessageBox.information(
            self,
            "Auftrag kopiert",
            "Die Kopie wurde als "
            f"{created.order_number} angelegt.",
        )

    def _create_series(self) -> None:
        selected = self._require_selected_order()
        if selected is None:
            return

        source = self.service.get(selected.id)
        if source is None:
            self._load_orders()
            return

        dialog = TransportOrderSeriesDialog(
            source,
            parent=self,
        )
        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        try:
            created = self.service.create_series(
                source=source,
                count=dialog.count(),
                interval_minutes=(
                    dialog.interval_minutes()
                ),
            )
        except TransportOrderValidationError as error:
            QMessageBox.warning(
                self,
                "Serie konnte nicht angelegt werden",
                str(error),
            )
            return

        self._load_orders()

        QMessageBox.information(
            self,
            "Auftragsserie angelegt",
            f"{len(created)} neue Aufträge wurden erzeugt.",
        )

    def _apply_quick_status(self) -> None:
        self._change_status(
            self.quick_status_combo.currentText()
        )

    def _change_status(self, status: str) -> None:
        selected = self._require_selected_orders()
        if not selected:
            return

        orders = []
        for item in selected:
            order = self.service.get(item.id)
            if order is not None:
                orders.append(order)

        if not orders:
            self._load_orders()
            return

        try:
            self.service.update_status_many(
                orders,
                status,
            )
        except TransportOrderValidationError as error:
            QMessageBox.warning(
                self,
                "Status konnte nicht geändert werden",
                str(error),
            )
            return

        self._load_orders()

    def _delete_order(self) -> None:
        selected = self._require_selected_orders()
        if not selected:
            return
        if hasattr(self, "tabs") and self.tabs.currentIndex() == 1:
            self._change_status("Neu")
            return

        if len(selected) == 1:
            question = (
                "Soll der Transportauftrag "
                f"„{selected[0].order_number}“ wirklich "
                "gelöscht werden?"
            )
        else:
            question = (
                f"Sollen die {len(selected)} ausgewählten "
                "Transportaufträge wirklich gelöscht werden?"
            )

        question += (
            "\n\nZugehörige Einträge in Touren werden "
            "automatisch entfernt."
        )

        answer = QMessageBox.question(
            self,
            "Transportauftrag löschen",
            question,
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        orders = []
        for item in selected:
            order = self.service.get(item.id)
            if order is not None:
                orders.append(order)

        if orders:
            self.service.delete_many(orders)

        self._load_orders()

    def _open_context_menu(
        self,
        position: QPoint,
        source_table: QTableView | None = None,
    ) -> None:
        """Öffnet ein kleines, fehlertolerantes Auftragsmenü."""
        try:
            table = source_table or self.table
            if table is not self.table:
                self.tabs.setCurrentIndex(1 if table is self.archive_table else 0)
            index = table.indexAt(position)
            if index.isValid() and not table.selectionModel().isRowSelected(
                index.row(),
                index.parent(),
            ):
                table.clearSelection()
                table.selectRow(index.row())

            if not self._selected_orders():
                return

            menu = create_context_menu(table)
            menu.addAction("Bearbeiten", self._edit_order)
            if self.tabs.currentIndex() == 0:
                create_menu = menu.addMenu("Erstellen")
                create_menu.addAction("Kopieren", self._copy_order)
                create_menu.addAction("Serie erzeugen", self._create_series)

            status_menu = menu.addMenu("Status")
            for status in TransportOrderService.STATUSES:
                action = status_menu.addAction(status)
                action.triggered.connect(
                    lambda checked=False, value=status: self._change_status(value)
                )

            menu.addSeparator()
            if self.tabs.currentIndex() == 1:
                menu.addAction("Wieder aktivieren", lambda: self._change_status("Neu"))
            else:
                menu.addAction("Löschen", self._delete_order)
            menu.exec(table.viewport().mapToGlobal(position))
        except Exception as error:
            # Ein Fehler in einem Kontextmenü darf niemals die Anwendung beenden.
            QMessageBox.critical(
                self,
                "Kontextmenü konnte nicht geöffnet werden",
                f"Das Kontextmenü des Transportauftrags konnte nicht geöffnet werden.\n\n{error}",
            )


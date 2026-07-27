from sqlalchemy import select
from sqlalchemy.orm import Session

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from leipzigerflow.exports import export_tours
from leipzigerflow.models.driver import Driver
from leipzigerflow.models.vehicle import Vehicle
from leipzigerflow.ui.context_menu import create_context_menu
from leipzigerflow.services.tour_service import TourService, TourValidationError
from leipzigerflow.ui.dialogs.tour_edit_dialog import TourEditDialog
from leipzigerflow.ui.dialogs.tour_planning_dialog import TourPlanningDialog
from leipzigerflow.ui.models.tour_table_model import TourTableModel


class TourDialog(QDialog):
    """Tourverwaltung mit automatischer Trennung von aktiven und erledigten Touren."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self.service = TourService(session)

        self.setWindowTitle("Touren")
        self.resize(1200, 720)
        layout = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Tournummer, Fahrer oder Fahrzeug suchen …")
        self.search_edit.textChanged.connect(self._load_tours)
        filter_row.addWidget(self.search_edit, 1)
        filter_row.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("Alle", "")
        for status in TourService.STATUSES:
            self.status_filter.addItem(status, status)
        self.status_filter.currentIndexChanged.connect(self._load_tours)
        filter_row.addWidget(self.status_filter)
        layout.addLayout(filter_row)

        button_row = QHBoxLayout()
        self.new_button = QPushButton("Neu")
        self.edit_button = QPushButton("Bearbeiten")
        self.plan_button = QPushButton("Disponieren")
        self.delete_button = QPushButton("Löschen")
        self.export_button = QPushButton("Excel exportieren")
        self.new_button.clicked.connect(self._create_tour)
        self.edit_button.clicked.connect(self._edit_tour)
        self.plan_button.clicked.connect(self._plan_tour)
        self.delete_button.clicked.connect(self._delete_tour)
        self.export_button.clicked.connect(self._export_excel)
        for button in (self.new_button, self.edit_button, self.plan_button, self.delete_button, self.export_button):
            button_row.addWidget(button)
        button_row.addSpacing(24)
        button_row.addWidget(QLabel("Status ändern:"))
        self.quick_status_combo = QComboBox()
        self.quick_status_combo.addItems(TourService.STATUSES)
        button_row.addWidget(self.quick_status_combo)
        self.status_button = QPushButton("Übernehmen")
        self.status_button.clicked.connect(self._change_status)
        button_row.addWidget(self.status_button)
        button_row.addStretch()
        close_button = QPushButton("Schließen")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self.tabs = QTabWidget()
        self.active_model = TourTableModel()
        self.archive_model = TourTableModel()
        self.active_table = self._create_table(self.active_model)
        self.archive_table = self._create_table(self.archive_model)
        self.archive_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.archive_table.customContextMenuRequested.connect(self._show_archive_menu)
        self.tabs.addTab(self._table_page(self.active_table), "Aktive Touren (0)")
        self.tabs.addTab(self._table_page(self.archive_table), "Tourarchiv (0)")
        self.tabs.currentChanged.connect(self._tab_changed)
        layout.addWidget(self.tabs)
        self._load_tours()

    def _create_table(self, model: TourTableModel) -> QTableView:
        table = QTableView()
        table.setModel(model)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.doubleClicked.connect(self._plan_tour)
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
    def model(self) -> TourTableModel:
        return self.archive_model if self.tabs.currentIndex() == 1 else self.active_model

    def _tab_changed(self, *_args) -> None:
        archived = self.tabs.currentIndex() == 1
        self.new_button.setEnabled(not archived)
        self.plan_button.setEnabled(not archived)
        self.edit_button.setEnabled(not archived)
        self.quick_status_combo.setCurrentText("Geplant" if archived else self.quick_status_combo.currentText())

    def _load_tours(self, *_args) -> None:
        self.service.synchronize_completed_tours()
        tours = self.service.search(
            search_text=self.search_edit.text(),
            status=str(self.status_filter.currentData() or ""),
        )
        active = [tour for tour in tours if not self.service.is_archived(tour)]
        archived = [tour for tour in tours if self.service.is_archived(tour)]
        self.active_model.set_tours(active)
        self.archive_model.set_tours(archived)
        self.tabs.setTabText(0, f"Aktive Touren ({len(active)})")
        self.tabs.setTabText(1, f"Tourarchiv ({len(archived)})")
        self.active_table.resizeColumnsToContents()
        self.archive_table.resizeColumnsToContents()

    def _selected_tours(self):
        selection = self.table.selectionModel()
        rows = selection.selectedRows() if selection else []
        return [tour for index in sorted(rows, key=lambda item: item.row()) if (tour := self.model.tour_at(index.row())) is not None]

    def _selected_tour(self):
        selected = self._selected_tours()
        return selected[0] if selected else None

    def _require_selected_tour(self):
        tour = self._selected_tour()
        if tour is None:
            QMessageBox.information(self, "Keine Auswahl", "Bitte eine Tour auswählen.")
        return tour

    def _master_data(self):
        drivers = list(self._session.scalars(select(Driver).where(Driver.active.is_(True)).order_by(Driver.last_name, Driver.first_name)))
        vehicles = list(self._session.scalars(select(Vehicle).where(Vehicle.active.is_(True)).order_by(Vehicle.license_plate)))
        return drivers, vehicles

    def _create_tour(self) -> None:
        drivers, vehicles = self._master_data()
        dialog = TourEditDialog(drivers, vehicles, parent=self)
        while dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                created = self.service.create(dialog.get_tour_data())
            except TourValidationError as error:
                QMessageBox.warning(self, "Eingabe prüfen", str(error))
                continue
            self._load_tours()
            TourPlanningDialog(self.service, created.id, parent=self).exec()
            self._load_tours()
            return

    def _edit_tour(self) -> None:
        selected = self._require_selected_tour()
        if selected is None:
            return
        if self.tabs.currentIndex() == 1:
            QMessageBox.information(self, "Tourarchiv", "Archivierte Touren bitte zuerst wieder aktivieren.")
            return
        if len(self._selected_tours()) > 1:
            QMessageBox.information(self, "Mehrfachauswahl", "Zum Bearbeiten bitte genau eine Tour auswählen.")
            return
        tour = self.service.get(selected.id)
        if tour is None:
            self._load_tours(); return
        drivers, vehicles = self._master_data()
        if tour.driver and all(item.id != tour.driver.id for item in drivers): drivers.append(tour.driver)
        if tour.vehicle and all(item.id != tour.vehicle.id for item in vehicles): vehicles.append(tour.vehicle)
        dialog = TourEditDialog(drivers, vehicles, tour=tour, parent=self)
        while dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.service.update(tour, dialog.get_tour_data())
            except TourValidationError as error:
                self._session.rollback(); QMessageBox.warning(self, "Eingabe prüfen", str(error)); continue
            self._load_tours(); return

    def _plan_tour(self, *_args) -> None:
        selected = self._require_selected_tour()
        if selected is None:
            return
        if self.tabs.currentIndex() == 1:
            QMessageBox.information(self, "Tourarchiv", "Archivierte Touren bitte zuerst wieder aktivieren.")
            return
        TourPlanningDialog(self.service, selected.id, parent=self).exec()
        self._load_tours()

    def _visible_tours(self):
        return [self.model.tour_at(row) for row in range(self.model.rowCount()) if self.model.tour_at(row) is not None]

    def _export_excel(self) -> None:
        tours = self._visible_tours()
        if not tours:
            QMessageBox.information(self, "Excel-Export", "In der aktuellen Ansicht sind keine Touren vorhanden.")
            return
        default_name = "Tourarchiv.xlsx" if self.tabs.currentIndex() == 1 else "Tourenplanung.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Touren exportieren", default_name, "Excel-Arbeitsmappe (*.xlsx)")
        if not path: return
        if not path.lower().endswith(".xlsx"): path += ".xlsx"
        try: export_tours(path, tours)
        except Exception as error:
            QMessageBox.critical(self, "Excel-Export", f"Die Touren konnten nicht exportiert werden:\n{error}"); return
        QMessageBox.information(self, "Excel-Export", f"{len(tours)} Tour(en) wurden erfolgreich exportiert.")

    def _change_status(self) -> None:
        selected = self._selected_tours()
        if not selected:
            QMessageBox.information(self, "Keine Auswahl", "Bitte mindestens eine Tour auswählen."); return
        status = self.quick_status_combo.currentText()
        try:
            for row_tour in selected:
                tour = self.service.get(row_tour.id)
                if tour is not None: self.service.change_status(tour, status)
        except TourValidationError as error:
            QMessageBox.warning(self, "Status konnte nicht geändert werden", str(error)); return
        self._load_tours()

    def _restore_selected_tours(self) -> None:
        selected = self._selected_tours()
        if not selected:
            return
        try:
            for row_tour in selected:
                tour = self.service.get(row_tour.id)
                if tour is not None:
                    self.service.change_status(tour, "Geplant")
        except TourValidationError as error:
            QMessageBox.warning(self, "Tour konnte nicht aktiviert werden", str(error)); return
        self._load_tours()

    def _show_archive_menu(self, position: QPoint) -> None:
        index = self.archive_table.indexAt(position)
        if index.isValid() and not self.archive_table.selectionModel().isRowSelected(index.row(), index.parent()):
            self.archive_table.selectRow(index.row())
        if not self._selected_tours():
            return
        menu = create_context_menu(self)
        restore = menu.addAction("↩ Tour wieder aktivieren")
        selected_action = menu.exec(self.archive_table.viewport().mapToGlobal(position))
        if selected_action == restore:
            self._restore_selected_tours()

    def _delete_tour(self) -> None:
        selected = self._selected_tours()
        if not selected:
            QMessageBox.information(self, "Keine Auswahl", "Bitte mindestens eine Tour auswählen."); return
        names = ", ".join(tour.tour_number for tour in selected[:5])
        suffix = " …" if len(selected) > 5 else ""
        answer = QMessageBox.question(self, "Touren löschen", f"Sollen {len(selected)} Tour(en) wirklich gelöscht werden?\n\n{names}{suffix}\n\nDie enthaltenen Aufträge werden wieder auf ‚Neu‘ gesetzt.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes: return
        for row_tour in selected:
            tour = self.service.get(row_tour.id)
            if tour is not None: self.service.delete(tour)
        self._load_tours()

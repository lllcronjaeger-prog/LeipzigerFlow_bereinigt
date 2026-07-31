from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QCheckBox,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from leipzigerflow.models.driver import Driver
from leipzigerflow.services.driver_service import (
    DriverService,
)
from leipzigerflow.services.location_service import LocationService
from leipzigerflow.ui.dialogs.driver_import_dialog import DriverImportDialog
from leipzigerflow.ui.dialogs.driver_merge_dialog import DriverMergeDialog
from leipzigerflow.ui.dialogs.driver_edit_dialog import (
    DriverEditDialog,
)
from leipzigerflow.ui.models.driver_table_model import (
    DriverTableModel,
)


class DriverDialog(QDialog):
    def __init__(
        self,
        session,
        parent=None,
    ):
        super().__init__(parent)

        self.service = DriverService(session)
        self.location_service = LocationService(session)
        self._settings = QSettings("LeipzigerFlow", "DriverManagement")

        self.setWindowTitle("Fahrerverwaltung")
        self.setMinimumSize(760, 480)

        main_layout = QVBoxLayout(self)

        # -----------------------------------------------------
        # Suche
        # -----------------------------------------------------

        search_layout = QHBoxLayout()

        search_layout.addWidget(
            QLabel("Suche:")
        )

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText(
            (
                "Name, Ort, Telefon, E-Mail oder "
                "Führerscheinnummer"
            )
        )
        self.edit_search.setClearButtonEnabled(True)

        search_layout.addWidget(
            self.edit_search
        )

        self.chk_archived = QCheckBox("Archivierte Fahrer anzeigen")
        search_layout.addWidget(self.chk_archived)

        main_layout.addLayout(
            search_layout
        )

        # -----------------------------------------------------
        # Tabelle
        # -----------------------------------------------------

        self.table_model = DriverTableModel()

        self.table_view = QTableView()
        self.table_view.setModel(
            self.table_model
        )

        self.table_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table_view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table_view.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.table_view.setShowGrid(False)

        self.table_view.verticalHeader().setVisible(False)

        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(True)

        self.table_view.setColumnWidth(0, 240)
        self.table_view.setColumnWidth(1, 190)
        self.table_view.setColumnWidth(2, 160)
        self.table_view.setColumnWidth(3, 180)
        self.table_view.setColumnWidth(4, 70)

        main_layout.addWidget(
            self.table_view
        )

        # -----------------------------------------------------
        # Aktionen
        # -----------------------------------------------------

        action_layout = QHBoxLayout()

        self.btn_import = QPushButton("Excel-Import")
        self.btn_new = QPushButton("Neu")
        self.btn_edit = QPushButton("Bearbeiten")
        self.btn_delete = QPushButton("Archivieren/Aktivieren")
        self.btn_merge = QPushButton("Zusammenführen")

        action_layout.addWidget(self.btn_import)
        action_layout.addWidget(
            self.btn_new
        )
        action_layout.addWidget(
            self.btn_edit
        )
        action_layout.addWidget(
            self.btn_delete
        )
        action_layout.addWidget(self.btn_merge)
        action_layout.addStretch()

        close_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )

        close_buttons.rejected.connect(
            self.reject
        )

        action_layout.addWidget(
            close_buttons
        )

        main_layout.addLayout(
            action_layout
        )

        # -----------------------------------------------------
        # Signale
        # -----------------------------------------------------

        self.edit_search.textChanged.connect(
            self._search
        )
        self.chk_archived.toggled.connect(lambda _checked: self._search(self.edit_search.text()))

        self.btn_import.clicked.connect(self._import_drivers)

        self.btn_new.clicked.connect(
            self._new_driver
        )

        self.btn_edit.clicked.connect(
            self._edit_driver
        )

        self.btn_delete.clicked.connect(
            self._delete_driver
        )
        self.btn_merge.clicked.connect(self._merge_driver)

        self.table_view.doubleClicked.connect(
            self._edit_driver
        )

        # -----------------------------------------------------
        # Initiale Daten
        # -----------------------------------------------------

        self._load_drivers()
        # Die Fenstergeometrie wird zentral vom WindowManager verwaltet.
        # Ein zweites restoreGeometry() auf dem eingebetteten Dialog konnte
        # das vollständige Fahrerfenster unsichtbar oder stark verkleinert öffnen.

    # ---------------------------------------------------------
    # Laden und Suchen
    # ---------------------------------------------------------

    def _load_drivers(self):
        drivers = self.service.get_all(include_archived=self.chk_archived.isChecked())

        self.table_model.setDrivers(
            drivers
        )

        if drivers:
            self.table_view.selectRow(0)

    def _search(
        self,
        text: str,
    ):
        drivers = self.service.search_drivers(
            text, include_archived=self.chk_archived.isChecked()
        )

        self.table_model.setDrivers(
            drivers
        )

        if drivers:
            self.table_view.selectRow(0)

    # ---------------------------------------------------------
    # Auswahl
    # ---------------------------------------------------------

    def _selected_driver(
        self,
    ) -> Driver | None:
        selection_model = (
            self.table_view.selectionModel()
        )

        if selection_model is None:
            return None

        rows = selection_model.selectedRows()

        if not rows:
            return None

        return self.table_model.driver_at(
            rows[0].row()
        )


    def _import_drivers(self):
        dialog = DriverImportDialog(self.service.repository._session, self)
        if dialog.exec():
            self._load_drivers()

    # ---------------------------------------------------------
    # Neu
    # ---------------------------------------------------------

    def _new_driver(self):
        dialog = DriverEditDialog(
            locations=self.location_service.get_all(),
            parent=self,
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        driver = Driver(
            **dialog.get_driver_data()
        )

        try:
            self.service.add(driver)
            self.service.replace_absences(driver, dialog.get_absence_drafts())

        except ValueError as error:
            QMessageBox.warning(
                self,
                "Fahrer konnte nicht gespeichert werden",
                str(error),
            )
            return

        except Exception as error:
            QMessageBox.critical(
                self,
                "Fehler",
                (
                    "Der Fahrer konnte nicht "
                    "gespeichert werden.\n\n"
                    f"{error}"
                ),
            )
            return

        self._refresh(
            selected_driver_id=driver.id
        )

    # ---------------------------------------------------------
    # Bearbeiten
    # ---------------------------------------------------------

    def _edit_driver(self, *_):
        driver = self._selected_driver()

        if driver is None:
            QMessageBox.information(
                self,
                "Fahrer auswählen",
                (
                    "Bitte zuerst einen Fahrer "
                    "auswählen."
                ),
            )
            return

        dialog = DriverEditDialog(
            driver=driver,
            locations=self.location_service.get_all(),
            parent=self,
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        data = dialog.get_driver_data()

        original_data = {
            field_name: getattr(
                driver,
                field_name,
            )
            for field_name in data
        }

        for field_name, value in data.items():
            setattr(
                driver,
                field_name,
                value,
            )

        try:
            self.service.update(driver)
            self.service.replace_absences(driver, dialog.get_absence_drafts())

        except ValueError as error:
            self._restore_driver_data(
                driver,
                original_data,
            )

            QMessageBox.warning(
                self,
                "Fahrer konnte nicht gespeichert werden",
                str(error),
            )
            return

        except Exception as error:
            self._restore_driver_data(
                driver,
                original_data,
            )

            QMessageBox.critical(
                self,
                "Fehler",
                (
                    "Der Fahrer konnte nicht "
                    "gespeichert werden.\n\n"
                    f"{error}"
                ),
            )
            return

        self._refresh(
            selected_driver_id=driver.id
        )

    # ---------------------------------------------------------
    # Löschen
    # ---------------------------------------------------------

    def _delete_driver(self):
        driver = self._selected_driver()
        if driver is None:
            return
        action = "reaktivieren" if not driver.active else "archivieren"
        answer = QMessageBox.question(
            self,
            "Fahrerstatus ändern",
            f"Soll {driver.full_name} wirklich {action} werden?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            if driver.active:
                self.service.archive(driver)
            else:
                self.service.reactivate(driver)
        except Exception as error:
            QMessageBox.critical(self, "Fahrer konnte nicht geändert werden", str(error))
            return
        self._search(self.edit_search.text())

    def _merge_driver(self):
        source = self._selected_driver()
        if source is None:
            QMessageBox.information(self, "Fahrer auswählen", "Bitte zuerst den doppelten Fahrer auswählen.")
            return
        targets = [driver for driver in self.service.get_all(include_archived=False) if driver.id != source.id]
        if not targets:
            QMessageBox.information(self, "Zusammenführen", "Es ist kein anderer aktiver Zielfahrer vorhanden.")
            return
        dialog = DriverMergeDialog(source, targets, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        target = self.service.get(dialog.target_driver_id) if dialog.target_driver_id else None
        if target is None:
            return
        answer = QMessageBox.question(
            self,
            "Zusammenführen bestätigen",
            f"Alle Daten von {source.full_name} werden auf {target.full_name} übertragen. "
            "Der Quellfahrer wird archiviert. Fortfahren?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.merge(source, target)
        except Exception as error:
            QMessageBox.critical(self, "Zusammenführen fehlgeschlagen", str(error))
            return
        QMessageBox.information(
            self,
            "Fahrer zusammengeführt",
            f"{source.full_name} wurde in {target.full_name} zusammengeführt und archiviert.",
        )
        self._refresh(selected_driver_id=target.id)

    def _refresh(
        self,
        selected_driver_id: int | None = None,
    ):
        search_text = (
            self.edit_search.text().strip()
        )

        if search_text:
            drivers = (
                self.service.search_drivers(
                    search_text, include_archived=self.chk_archived.isChecked()
                )
            )
        else:
            drivers = self.service.get_all(include_archived=self.chk_archived.isChecked())

        self.table_model.setDrivers(
            drivers
        )

        if not drivers:
            return

        if selected_driver_id is None:
            self.table_view.selectRow(0)
            return

        for row, driver in enumerate(drivers):
            if driver.id == selected_driver_id:
                self.table_view.selectRow(row)
                self.table_view.scrollTo(
                    self.table_model.index(
                        row,
                        0,
                    )
                )
                return

        self.table_view.selectRow(0)

    @staticmethod
    def _restore_driver_data(
        driver: Driver,
        original_data: dict,
    ):
        for field_name, value in original_data.items():
            setattr(
                driver,
                field_name,
                value,
            )

    # ---------------------------------------------------------
    # Tastatur
    # ---------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            if self.table_view.hasFocus():
                self._edit_driver()
                return

        if event.key() == Qt.Key.Key_Delete:
            if self.table_view.hasFocus():
                self._delete_driver()
                return

        super().keyPressEvent(event)
    def _restore_window_state(self) -> None:
        geometry = self._settings.value("geometry")
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)
            frame = self.frameGeometry()
            if not any(screen.availableGeometry().intersects(frame) for screen in QGuiApplication.screens()):
                target = QGuiApplication.primaryScreen().availableGeometry()
                self.move(target.center() - self.rect().center())
        else:
            self.resize(1250, 650)
        header_state = self._settings.value("table_header")
        if isinstance(header_state, QByteArray) and not header_state.isEmpty():
            self.table_view.horizontalHeader().restoreState(header_state)

    def _save_window_state(self) -> None:
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("table_header", self.table_view.horizontalHeader().saveState())
        self._settings.sync()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        super().closeEvent(event)

    def accept(self) -> None:
        super().accept()

    def reject(self) -> None:
        super().reject()


from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from leipzigerflow.models.customer import Customer
from leipzigerflow.services.customer_service import (
    CustomerService,
)
from leipzigerflow.ui.dialogs.customer_import_dialog import CustomerImportDialog
from leipzigerflow.ui.dialogs.customer_edit_dialog import (
    CustomerEditDialog,
)
from leipzigerflow.ui.models.customer_table_model import (
    CustomerTableModel,
)


class CustomerDialog(QDialog):
    def __init__(
        self,
        session,
        parent=None,
    ):
        super().__init__(parent)

        self.service = CustomerService(session)

        self.setWindowTitle("Kundenverwaltung")
        self.resize(800, 500)

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
            "Name, Kurzname oder Ort"
        )
        self.edit_search.setClearButtonEnabled(True)

        search_layout.addWidget(self.edit_search)

        main_layout.addLayout(search_layout)

        # -----------------------------------------------------
        # Tabelle
        # -----------------------------------------------------

        self.table_model = CustomerTableModel()

        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)

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

        self.table_view.setColumnWidth(0, 260)
        self.table_view.setColumnWidth(1, 130)
        self.table_view.setColumnWidth(2, 220)
        self.table_view.setColumnWidth(3, 70)

        main_layout.addWidget(self.table_view)

        # -----------------------------------------------------
        # Aktionen
        # -----------------------------------------------------

        action_layout = QHBoxLayout()

        self.btn_import = QPushButton("Excel-Import")
        self.btn_new = QPushButton("Neu")
        self.btn_edit = QPushButton("Bearbeiten")
        self.btn_delete = QPushButton("Löschen")

        action_layout.addWidget(self.btn_new)
        action_layout.addWidget(self.btn_edit)
        action_layout.addWidget(self.btn_delete)
        action_layout.addStretch()

        close_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )

        close_buttons.rejected.connect(self.reject)

        action_layout.addWidget(close_buttons)

        main_layout.addLayout(action_layout)

        # -----------------------------------------------------
        # Signale
        # -----------------------------------------------------

        self.edit_search.textChanged.connect(
            self._search
        )

        self.btn_import.clicked.connect(self._import_customers)

        self.btn_new.clicked.connect(
            self._new_customer
        )

        self.btn_edit.clicked.connect(
            self._edit_customer
        )

        self.btn_delete.clicked.connect(
            self._delete_customer
        )

        self.table_view.doubleClicked.connect(
            self._edit_customer
        )

        # -----------------------------------------------------
        # Initiale Daten
        # -----------------------------------------------------

        self._load_customers()

    # ---------------------------------------------------------
    # Laden und Suchen
    # ---------------------------------------------------------

    def _load_customers(self):
        customers = self.service.get_all()

        self.table_model.setCustomers(customers)

        if customers:
            self.table_view.selectRow(0)

    def _search(
        self,
        text: str,
    ):
        customers = self.service.search_customers(text)

        self.table_model.setCustomers(customers)

        if customers:
            self.table_view.selectRow(0)

    # ---------------------------------------------------------
    # Auswahl
    # ---------------------------------------------------------

    def _selected_customer(
        self,
    ) -> Customer | None:
        selection_model = (
            self.table_view.selectionModel()
        )

        if selection_model is None:
            return None

        rows = selection_model.selectedRows()

        if not rows:
            return None

        row = rows[0].row()

        return self.table_model.customer_at(row)

    def _import_customers(self):
        dialog = CustomerImportDialog(self.service.repository._session, self)
        if dialog.exec():
            self._load_customers()

    # ---------------------------------------------------------
    # Neu
    # ---------------------------------------------------------

    def _new_customer(self):
        dialog = CustomerEditDialog(
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_customer_data()

        customer = Customer(**data)

        try:
            self.service.add(customer)

        except ValueError as error:
            QMessageBox.warning(
                self,
                "Kunde konnte nicht gespeichert werden",
                str(error),
            )
            return

        except Exception as error:
            QMessageBox.critical(
                self,
                "Fehler",
                (
                    "Der Kunde konnte nicht gespeichert "
                    f"werden.\n\n{error}"
                ),
            )
            return

        self._refresh()

    # ---------------------------------------------------------
    # Bearbeiten
    # ---------------------------------------------------------

    def _edit_customer(self, *_):
        customer = self._selected_customer()

        if customer is None:
            QMessageBox.information(
                self,
                "Kunde auswählen",
                (
                    "Bitte zuerst einen Kunden "
                    "auswählen."
                ),
            )
            return

        dialog = CustomerEditDialog(
            customer=customer,
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_customer_data()

        for field_name, value in data.items():
            setattr(customer, field_name, value)

        try:
            self.service.update(customer)

        except ValueError as error:
            QMessageBox.warning(
                self,
                "Kunde konnte nicht gespeichert werden",
                str(error),
            )
            return

        except Exception as error:
            QMessageBox.critical(
                self,
                "Fehler",
                (
                    "Der Kunde konnte nicht gespeichert "
                    f"werden.\n\n{error}"
                ),
            )
            return

        self._refresh(
            selected_customer_id=customer.id
        )

    # ---------------------------------------------------------
    # Löschen
    # ---------------------------------------------------------

    def _delete_customer(self):
        customer = self._selected_customer()

        if customer is None:
            QMessageBox.information(
                self,
                "Kunde auswählen",
                (
                    "Bitte zuerst einen Kunden "
                    "auswählen."
                ),
            )
            return

        answer = QMessageBox.question(
            self,
            "Kunde löschen",
            (
                f'Soll der Kunde "{customer.name}" '
                "wirklich gelöscht werden?"
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.service.delete(customer)

        except Exception as error:
            QMessageBox.critical(
                self,
                "Fehler",
                (
                    "Der Kunde konnte nicht gelöscht "
                    f"werden.\n\n{error}"
                ),
            )
            return

        self._refresh()

    # ---------------------------------------------------------
    # Aktualisieren
    # ---------------------------------------------------------

    def _refresh(
        self,
        selected_customer_id: int | None = None,
    ):
        search_text = self.edit_search.text().strip()

        if search_text:
            customers = self.service.search_customers(
                search_text
            )
        else:
            customers = self.service.get_all()

        self.table_model.setCustomers(customers)

        if not customers:
            return

        if selected_customer_id is None:
            self.table_view.selectRow(0)
            return

        for row, customer in enumerate(customers):
            if customer.id == selected_customer_id:
                self.table_view.selectRow(row)
                self.table_view.scrollTo(
                    self.table_model.index(row, 0)
                )
                return

        self.table_view.selectRow(0)

    # ---------------------------------------------------------
    # Tastatur
    # ---------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            if self.table_view.hasFocus():
                self._edit_customer()
                return

        if event.key() == Qt.Key.Key_Delete:
            if self.table_view.hasFocus():
                self._delete_customer()
                return

        super().keyPressEvent(event)
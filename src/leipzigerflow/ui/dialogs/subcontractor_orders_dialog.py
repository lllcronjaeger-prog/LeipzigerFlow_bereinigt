from PySide6.QtWidgets import QDialog, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from leipzigerflow.models.contractor import ContractorType
from leipzigerflow.models.transport_order import TransportOrder


class SubcontractorOrdersDialog(QDialog):
    """Separate Übersicht für extern vergebene Aufträge.

    Für aus Dispoplan importierte Unternehmer genügt der Name. Der Import legt bei
    Bedarf automatisch einen schlanken Unternehmer-Datensatz an; vollständige
    Adress- oder Kontaktdaten sind für die Zuordnung nicht erforderlich.
    """

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Subunternehmer-Aufträge")
        self.resize(1250, 650)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Bereits extern vergebene Aufträge. Sie bleiben in LeipzigerFlow sichtbar, "
            "werden aber weder in der Plantafel noch in der Auto-Disposition angeboten."
        ))
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Kundenauftrag", "Dossier", "Subunternehmer", "Ladetag",
            "Ladestelle", "Liefertag", "Entladestelle", "Status", "Referenz",
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self):
        statement = (
            select(TransportOrder)
            .options(
                selectinload(TransportOrder.contractor),
                selectinload(TransportOrder.loading_location),
                selectinload(TransportOrder.unloading_location),
            )
            .where(TransportOrder.assignment_type == ContractorType.SUBCONTRACTOR.value)
            .order_by(TransportOrder.loading_date, TransportOrder.customer_order_number, TransportOrder.order_number)
        )
        rows = list(self.session.scalars(statement))
        self.table.setRowCount(len(rows))
        for row_index, order in enumerate(rows):
            contractor_name = order.contractor.display_name if order.contractor else order.contractor_raw
            values = [
                order.customer_order_number or order.order_number,
                order.dossier,
                contractor_name,
                order.loading_date,
                order.loading_location.full_display if order.loading_location else "",
                order.unloading_date,
                order.unloading_location.full_display if order.unloading_location else "",
                order.status,
                order.reference,
            ]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(str(value or "")))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

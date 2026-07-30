from PySide6.QtWidgets import QDialog,QLabel,QTableWidget,QTableWidgetItem,QVBoxLayout
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from leipzigerflow.models.transport_order import TransportOrder
from leipzigerflow.models.contractor import ContractorType

class SubcontractorOrdersDialog(QDialog):
    def __init__(self,session,parent=None):
        super().__init__(parent); self.session=session; self.setWindowTitle('Subunternehmer-Aufträge'); self.resize(1200,650)
        layout=QVBoxLayout(self); layout.addWidget(QLabel('Aufträge, die nicht im eigenen Fuhrpark verplant werden.'))
        self.table=QTableWidget(0,8); self.table.setHorizontalHeaderLabels(['Auftrag','Unternehmer','Ladetag','Ladestelle','Liefertag','Entladestelle','Status','Referenz']); layout.addWidget(self.table); self.refresh()
    def refresh(self):
        stmt=select(TransportOrder).options(selectinload(TransportOrder.contractor),selectinload(TransportOrder.loading_location),selectinload(TransportOrder.unloading_location)).where(TransportOrder.assignment_type==ContractorType.SUBCONTRACTOR.value).order_by(TransportOrder.loading_date,TransportOrder.order_number)
        rows=list(self.session.scalars(stmt)); self.table.setRowCount(len(rows))
        for r,o in enumerate(rows):
            vals=[o.order_number,o.contractor.display_name if o.contractor else o.contractor_raw,str(o.loading_date),o.loading_location.full_display,str(o.unloading_date),o.unloading_location.full_display,o.status,o.reference]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(str(v or '')))
        self.table.resizeColumnsToContents()

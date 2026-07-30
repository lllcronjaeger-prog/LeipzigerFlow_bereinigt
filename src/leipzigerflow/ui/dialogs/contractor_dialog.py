from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QHBoxLayout, QInputDialog, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout
from sqlalchemy import select
from leipzigerflow.models.contractor import Contractor, ContractorType

class ContractorDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent); self.session=session; self.setWindowTitle('Unternehmer'); self.resize(850,500)
        layout=QVBoxLayout(self); self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(['MatchCode','Name','Typ','Aktiv']); layout.addWidget(self.table)
        row=QHBoxLayout(); add=QPushButton('Neu'); add.clicked.connect(self._add); edit=QPushButton('Typ ändern'); edit.clicked.connect(self._edit_type); row.addWidget(add); row.addWidget(edit); row.addStretch(); layout.addLayout(row); self.refresh()
    def refresh(self):
        items=list(self.session.scalars(select(Contractor).order_by(Contractor.contractor_type,Contractor.name)))
        self.table.setRowCount(len(items))
        for r,item in enumerate(items):
            vals=[item.match_code,item.name,item.contractor_type,'Ja' if item.active else 'Nein']
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(v))
            self.table.item(r,0).setData(256,item.id)
        self.table.resizeColumnsToContents()
    def _add(self):
        code,ok=QInputDialog.getText(self,'Unternehmer','MatchCode:');
        if not ok or not code.strip(): return
        name,ok=QInputDialog.getText(self,'Unternehmer','Name:');
        if not ok: return
        self.session.add(Contractor(match_code=code.strip(),name=name.strip(),contractor_type=ContractorType.SUBCONTRACTOR.value)); self.session.commit(); self.refresh()
    def _edit_type(self):
        row=self.table.currentRow();
        if row<0:return
        obj=self.session.get(Contractor,self.table.item(row,0).data(256));
        values=[x.value for x in ContractorType]; value,ok=QInputDialog.getItem(self,'Unternehmertyp','Typ:',values,values.index(obj.contractor_type) if obj.contractor_type in values else 0,False)
        if ok: obj.contractor_type=value; self.session.commit(); self.refresh()

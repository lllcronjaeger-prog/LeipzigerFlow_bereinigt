from datetime import date, timedelta
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor

class VehicleTableModel(QAbstractTableModel):
    HEADERS=["Fahrzeugnummer","Kennzeichen","Fahrzeugart","Fahrzeugklasse","HU","Standort","Status","Gekoppelter Trailer","Aktiv"]
    def __init__(self,vehicles=None): super().__init__(); self._vehicles=vehicles or []
    def rowCount(self,parent=QModelIndex()): return len(self._vehicles)
    def columnCount(self,parent=QModelIndex()): return len(self.HEADERS)
    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid(): return None
        v=self._vehicles[index.row()]; t=getattr(v,'trailer',None)
        vals=[v.vehicle_number,v.license_plate,getattr(v,'ownership_type','Eigenes Fahrzeug') or 'Eigenes Fahrzeug',getattr(v,'vehicle_class','Standard') or 'Standard',v.hu_date.strftime('%d.%m.%Y') if v.hu_date else '',v.location,v.status,t.display_name if t else '', 'Ja' if v.active else 'Nein']
        if role==Qt.DisplayRole:return vals[index.column()]
        if role==Qt.TextAlignmentRole and index.column() in (2,3,4,8):return Qt.AlignCenter
        if role==Qt.BackgroundRole and index.column()==4 and v.hu_date:
            days=(v.hu_date-date.today()).days
            return QBrush(QColor('#ffd6d6' if days<0 else '#fff2bf' if days<=60 else '#d9f2df'))
        if role==Qt.ForegroundRole and not v.active:return QBrush(QColor('#777777'))
        return None
    def headerData(self,s,o,r): return self.HEADERS[s] if o==Qt.Horizontal and r==Qt.DisplayRole else super().headerData(s,o,r)
    def setVehicles(self,x): self.beginResetModel();self._vehicles=x;self.endResetModel()
    def vehicle_at(self,row): return self._vehicles[row] if 0<=row<len(self._vehicles) else None
    def sort(self,c,o):
        rev=o==Qt.DescendingOrder; keys=[lambda v:v.vehicle_number.upper(),lambda v:v.license_plate.upper(),lambda v:getattr(v,'ownership_type','').upper(),lambda v:v.vehicle_class.upper(),lambda v:v.hu_date or date.min,lambda v:v.location.upper(),lambda v:v.status.upper(),lambda v:(v.trailer.display_name if v.trailer else '').upper(),lambda v:v.active]
        self.layoutAboutToBeChanged.emit();self._vehicles.sort(key=keys[c],reverse=rev);self.layoutChanged.emit()

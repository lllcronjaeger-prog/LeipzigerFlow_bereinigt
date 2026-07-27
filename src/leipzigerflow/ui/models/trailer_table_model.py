from datetime import date
from PySide6.QtCore import QAbstractTableModel,QModelIndex,Qt
from PySide6.QtGui import QBrush,QColor
class TrailerTableModel(QAbstractTableModel):
    HEADERS=["Trailernummer","Kennzeichen","Trailertyp","HU","SP","Standort","Status","Aktiv"]
    def __init__(self,trailers=None):super().__init__();self._trailers=trailers or []
    def rowCount(self,parent=QModelIndex()):return len(self._trailers)
    def columnCount(self,parent=QModelIndex()):return len(self.HEADERS)
    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid():return None
        t=self._trailers[index.row()]; vals=[t.trailer_number,t.license_plate,t.trailer_type,t.hu_date.strftime('%d.%m.%Y') if t.hu_date else '',t.sp_date.strftime('%d.%m.%Y') if t.sp_date else '',t.location,t.status,'Ja' if t.active else 'Nein']
        if role==Qt.DisplayRole:return vals[index.column()]
        if role==Qt.TextAlignmentRole and index.column() in (3,4,7):return Qt.AlignCenter
        if role==Qt.BackgroundRole and index.column() in (3,4):
            d=t.hu_date if index.column()==3 else t.sp_date
            if d:
                days=(d-date.today()).days
                return QBrush(QColor('#ffd6d6' if days<0 else '#fff2bf' if days<=60 else '#d9f2df'))
        if role==Qt.ForegroundRole and not t.active:return QBrush(QColor('#777777'))
        return None
    def headerData(self,s,o,r):return self.HEADERS[s] if o==Qt.Horizontal and r==Qt.DisplayRole else super().headerData(s,o,r)
    def setTrailers(self,x):self.beginResetModel();self._trailers=x;self.endResetModel()
    def trailer_at(self,row):return self._trailers[row] if 0<=row<len(self._trailers) else None

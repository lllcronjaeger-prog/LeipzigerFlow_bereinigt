from datetime import date
from PySide6.QtCore import QAbstractTableModel,QModelIndex,Qt
from PySide6.QtGui import QBrush,QColor
class DriverTableModel(QAbstractTableModel):
    HEADERS=['Name','Ort','Telefon','Führerscheinklassen','Fahrerkarte','Module 95','ADR','Abwesenheit','Aktiv']
    def __init__(self,drivers=None):super().__init__();self._drivers=drivers or []
    def rowCount(self,parent=QModelIndex()):return len(self._drivers)
    def columnCount(self,parent=QModelIndex()):return len(self.HEADERS)
    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid():return None
        d=self._drivers[index.row()]
        absence=''
        active_absences = [a for a in (getattr(d, 'absences', ()) or ()) if getattr(a, 'active', True)]
        if active_absences:
            a = sorted(active_absences, key=lambda item: item.starts_at)[0]
            absence = f"{a.starts_at:%d.%m.%Y}–{a.ends_at:%d.%m.%Y} {a.reason}".strip()
        elif d.absence_from or d.absence_until:
            absence=f"{d.absence_from.strftime('%d.%m.%Y') if d.absence_from else '?'}–{d.absence_until.strftime('%d.%m.%Y') if d.absence_until else '?'} {d.absence_reason or ''}".strip()
        vals=[d.full_name,f'{d.postal_code} {d.city}'.strip(),d.mobile or d.phone,d.license_classes,d.driver_card_valid_until.strftime('%d.%m.%Y') if d.driver_card_valid_until else '',d.module_95_valid_until.strftime('%d.%m.%Y') if d.module_95_valid_until else '',d.adr_valid_until.strftime('%d.%m.%Y') if d.adr_valid_until else '',absence,'Ja' if d.active else 'Nein']
        if role==Qt.DisplayRole:return vals[index.column()]
        if role==Qt.BackgroundRole and index.column() in (4,5,6):
            dt=(d.driver_card_valid_until,d.module_95_valid_until,d.adr_valid_until)[index.column()-4]
            if dt:
                days=(dt-date.today()).days;return QBrush(QColor('#ffd6d6' if days<0 else '#fff2bf' if days<=60 else '#d9f2df'))
        if role==Qt.ForegroundRole and not d.active:return QBrush(QColor('#777777'))
        if role==Qt.TextAlignmentRole and index.column() in (4,5,6,8):return Qt.AlignCenter
        return None
    def headerData(self,s,o,r):return self.HEADERS[s] if o==Qt.Horizontal and r==Qt.DisplayRole else super().headerData(s,o,r)
    def setDrivers(self,x):self.beginResetModel();self._drivers=x;self.endResetModel()
    def driver_at(self,row):return self._drivers[row] if 0<=row<len(self._drivers) else None
    def sort(self,c,o):
        rev=o==Qt.DescendingOrder;self.layoutAboutToBeChanged.emit();self._drivers.sort(key=lambda d:str(self.data(self.index(self._drivers.index(d),c),Qt.DisplayRole)).upper(),reverse=rev);self.layoutChanged.emit()

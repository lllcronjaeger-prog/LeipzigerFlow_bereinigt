import json

from PySide6.QtCore import QAbstractTableModel, QMimeData, QModelIndex, Qt

ORDER_MIME_TYPE = "application/x-leipzigerflow-order-ids"
TOUR_ORDER_MIME_TYPE = "application/x-leipzigerflow-tour-order"


class TourOrderTableModel(QAbstractTableModel):
    HEADERS = ["Pos.", "Auftrag", "Typ", "Kunde", "Laden", "Von", "Nach", "Status"]

    def __init__(self, orders=None, show_position=False, parent=None):
        super().__init__(parent)
        self._orders = list(orders or [])
        self._show_position = show_position

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._orders)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._orders[index.row()]
        position = item if self._show_position else None
        order = item.transport_order if self._show_position else item
        if role == Qt.ItemDataRole.DisplayRole:
            values = [
                str(position.position) if position else "",
                order.order_number,
                order.order_type,
                order.customer.display_name if order.customer else "",
                order.loading_date.strftime("%d.%m.%Y"),
                order.loading_location.full_display if order.loading_location else "",
                order.unloading_location.full_display if order.unloading_location else "",
                order.status,
            ]
            return values[index.column()]
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in (0, 2, 4, 7):
            return Qt.AlignmentFlag.AlignCenter
        return None

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid():
            flags |= Qt.ItemFlag.ItemIsDragEnabled
            if self._show_position:
                flags |= Qt.ItemFlag.ItemIsDropEnabled
        return flags

    def mimeTypes(self):
        return [ORDER_MIME_TYPE, TOUR_ORDER_MIME_TYPE]

    def mimeData(self, indexes):
        rows = sorted({index.row() for index in indexes if index.isValid()})
        mime = QMimeData()
        if self._show_position:
            ids = [self._orders[row].transport_order_id for row in rows]
            mime.setData(TOUR_ORDER_MIME_TYPE, json.dumps(ids).encode("utf-8"))
        else:
            ids = [self._orders[row].id for row in rows]
            mime.setData(ORDER_MIME_TYPE, json.dumps(ids).encode("utf-8"))
        return mime

    def supportedDragActions(self):
        return Qt.DropAction.MoveAction

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def set_items(self, items):
        self.beginResetModel()
        self._orders = list(items)
        self.endResetModel()

    def item_at(self, row):
        if 0 <= row < len(self._orders):
            return self._orders[row]
        return None

from PySide6.QtCore import QAbstractTableModel, QMimeData, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication

from leipzigerflow.ui.dragdrop.mime_types import (
    ORDER_MIME_TYPE,
    OrderDragPayload,
    encode_order_payload,
)


class PlanningTourTableModel(QAbstractTableModel):
    HEADERS = ("Tour", "Fahrer", "Fahrzeug", "Aufträge", "Status")

    def __init__(self, tours=None, parent=None):
        super().__init__(parent)
        self._tours = list(tours or [])

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._tours)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        tour = self._tours[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            values = (
                tour.tour_number,
                tour.driver_display or "offen",
                tour.vehicle_display or "offen",
                str(tour.order_count),
                tour.status,
            )
            return values[index.column()]
        if role == Qt.ItemDataRole.FontRole and index.column() == 0:
            font = QFont(QApplication.font())
            if font.pointSize() <= 0:
                font.setPointSize(10)
            font.setBold(True)
            return font
        if role == Qt.ItemDataRole.ForegroundRole:
            if index.column() in (1, 2) and not (
                tour.driver_display if index.column() == 1 else tour.vehicle_display
            ):
                return QColor("#b45309")
            if index.column() == 4:
                return {
                    "Geplant": QColor("#2563eb"),
                    "Unterwegs": QColor("#d97706"),
                    "Abgeschlossen": QColor("#15803d"),
                    "Storniert": QColor("#b91c1c"),
                }.get(tour.status)
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in (3, 4):
            return Qt.AlignmentFlag.AlignCenter
        return None

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid():
            flags |= Qt.ItemFlag.ItemIsDropEnabled
        return flags

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def set_tours(self, tours):
        self.beginResetModel()
        self._tours = list(tours)
        self.endResetModel()

    def tour_at(self, row):
        if 0 <= row < len(self._tours):
            return self._tours[row]
        return None


class PlanningOrderTableModel(QAbstractTableModel):
    HEADERS = (
        "Auftrag",
        "Kundenauftrag",
        "Typ",
        "Kunde",
        "Ladezeit",
        "Von",
        "Nach",
        "Status",
    )

    def __init__(self, orders=None, parent=None):
        super().__init__(parent)
        self._orders = list(orders or [])

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._orders)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    @staticmethod
    def _time_text(order):
        start = order.loading_time_from
        end = order.loading_time_until
        if start and end:
            return f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"
        if start:
            return start.strftime("%H:%M")
        if end:
            return f"bis {end.strftime('%H:%M')}"
        return ""

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        order = self._orders[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            values = (
                order.order_number,
                order.customer_order_number,
                order.order_type,
                order.customer.display_name if order.customer else "",
                self._time_text(order),
                order.loading_location.full_display if order.loading_location else "",
                order.unloading_location.full_display if order.unloading_location else "",
                order.status,
            )
            return values[index.column()]
        if role == Qt.ItemDataRole.FontRole and index.column() == 0:
            font = QFont(QApplication.font())
            if font.pointSize() <= 0:
                font.setPointSize(10)
            font.setBold(True)
            return font
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in (2, 4, 7):
            return Qt.AlignmentFlag.AlignCenter
        return None

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid():
            flags |= Qt.ItemFlag.ItemIsDragEnabled
        return flags

    def mimeTypes(self):
        return [ORDER_MIME_TYPE]

    def mimeData(self, indexes):
        rows = sorted({index.row() for index in indexes if index.isValid()})
        order_ids = [self._orders[row].id for row in rows]
        mime = QMimeData()
        mime.setData(
            ORDER_MIME_TYPE,
            encode_order_payload(OrderDragPayload(tuple(int(value) for value in order_ids))),
        )
        return mime

    def supportedDragActions(self):
        return Qt.DropAction.MoveAction

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def set_orders(self, orders):
        self.beginResetModel()
        self._orders = list(orders)
        self.endResetModel()

    def order_at(self, row):
        if 0 <= row < len(self._orders):
            return self._orders[row]
        return None

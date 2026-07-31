from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
)


from leipzigerflow.services.trailer_compatibility import display_trailer_types
class TransportOrderTableModel(QAbstractTableModel):
    HEADERS = [
        "Kundenauftrag",
        "Dossier",
        "Interne Nr.",
        "Typ",
        "Priorität",
        "Trailertyp",
        "Kunde",
        "Laden",
        "Ladestelle",
        "Entladen",
        "Entladestelle",
        "Status",
    ]

    def __init__(self, orders=None):
        super().__init__()
        self._orders = list(orders or [])

    def rowCount(self, parent=QModelIndex()):
        return len(self._orders)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(
        self,
        index,
        role=Qt.ItemDataRole.DisplayRole,
    ):
        if not index.isValid():
            return None

        order = self._orders[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            values = [
                order.customer_order_number,
                getattr(order, "dossier", ""),
                order.order_number,
                order.order_type,
                getattr(order, "dispatch_priority", "Eigenfuhrpark bevorzugt"),
                display_trailer_types(getattr(order, "required_trailer_type", "Plane")),
                (
                    order.customer.display_name
                    if order.customer
                    else ""
                ),
                order.loading_date.strftime("%d.%m.%Y"),
                (
                    order.loading_location.full_display
                    if order.loading_location
                    else ""
                ),
                order.unloading_date.strftime("%d.%m.%Y"),
                (
                    order.unloading_location.full_display
                    if order.unloading_location
                    else ""
                ),
                order.status,
            ]
            return values[index.column()]

        if (
            role == Qt.ItemDataRole.TextAlignmentRole
            and index.column() in (3, 4, 5, 7, 9, 11)
        ):
            return Qt.AlignmentFlag.AlignCenter

        return None

    def headerData(
        self,
        section,
        orientation,
        role=Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self.HEADERS[section]

        return super().headerData(
            section,
            orientation,
            role,
        )

    def set_orders(self, orders):
        self.beginResetModel()
        self._orders = list(orders)
        self.endResetModel()

    def order_at(self, row):
        if 0 <= row < len(self._orders):
            return self._orders[row]
        return None

    def sort(
        self,
        column,
        order=Qt.SortOrder.AscendingOrder,
    ):
        reverse = (
            order == Qt.SortOrder.DescendingOrder
        )

        keys = {
            0: lambda item: item.customer_order_number.casefold(),
            1: lambda item: getattr(item, "dossier", "").casefold(),
            2: lambda item: item.order_number.casefold(),
            3: lambda item: item.order_type.casefold(),
            4: lambda item: getattr(item, "dispatch_priority", "Eigenfuhrpark bevorzugt").casefold(),
            5: lambda item: display_trailer_types(getattr(item, "required_trailer_type", "Plane")).casefold(),
            6: lambda item: (item.customer.display_name.casefold() if item.customer else ""),
            7: lambda item: item.loading_date,
            8: lambda item: (item.loading_location.full_display.casefold() if item.loading_location else ""),
            9: lambda item: item.unloading_date,
            10: lambda item: (item.unloading_location.full_display.casefold() if item.unloading_location else ""),
            11: lambda item: item.status.casefold(),
        }

        self.layoutAboutToBeChanged.emit()
        self._orders.sort(
            key=keys.get(column, keys[0]),
            reverse=reverse,
        )
        self.layoutChanged.emit()

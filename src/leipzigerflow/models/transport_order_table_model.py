from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
)

from leipzigerflow.models.transport_order import TransportOrder


class TransportOrderTableModel(QAbstractTableModel):

    HEADERS = [
        "Dossier",
        "Auftragsnummer",
        "Kunde",
        "Abholung",
        "Lieferung",
        "Liefertermin",
        "Status",
    ]

    def __init__(self, orders=None):
        super().__init__()
        self._orders = orders or []

    def rowCount(self, parent=QModelIndex()):
        return len(self._orders)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=Qt.DisplayRole):

        if not index.isValid():
            return None

        order = self._orders[index.row()]

        if role == Qt.DisplayRole:

            match index.column():

                case 0:
                    return order.dossier

                case 1:
                    return order.customer_order_number

                case 2:
                    return order.customer.name

                case 3:
                    return order.pickup_location.name

                case 4:
                    return order.delivery_location.name

                case 5:
                    return order.delivery_time.strftime(
                        "%d.%m.%Y %H:%M"
                    )

                case 6:
                    return order.status.display_name

        if role == Qt.TextAlignmentRole:

            if index.column() == 6:
                return Qt.AlignCenter

        return None

    def headerData(
        self,
        section,
        orientation,
        role,
    ):

        if (
            orientation == Qt.Horizontal
            and role == Qt.DisplayRole
        ):
            return self.HEADERS[section]

        return super().headerData(
            section,
            orientation,
            role,
        )

    def setOrders(self, orders):
        self.beginResetModel()
        self._orders = orders
        self.endResetModel()

    def order_at(self, row):

        if row < 0 or row >= len(self._orders):
            return None

        return self._orders[row]

    def sort(self, column, order):

        reverse = (
            order == Qt.SortOrder.DescendingOrder
        )

        self.layoutAboutToBeChanged.emit()

        match column:

            case 0:
                self._orders.sort(
                    key=lambda o: o.dossier,
                    reverse=reverse,
                )

            case 1:
                self._orders.sort(
                    key=lambda o: o.customer_order_number.upper(),
                    reverse=reverse,
                )

            case 2:
                self._orders.sort(
                    key=lambda o: o.customer.name.upper(),
                    reverse=reverse,
                )

            case 3:
                self._orders.sort(
                    key=lambda o: o.pickup_location.name.upper(),
                    reverse=reverse,
                )

            case 4:
                self._orders.sort(
                    key=lambda o: o.delivery_location.name.upper(),
                    reverse=reverse,
                )

            case 5:
                self._orders.sort(
                    key=lambda o: o.delivery_time,
                    reverse=reverse,
                )

            case 6:
                self._orders.sort(
                    key=lambda o: o.status.value,
                    reverse=reverse,
                )

        self.layoutChanged.emit()
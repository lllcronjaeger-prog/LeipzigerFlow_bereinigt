from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
)

from leipzigerflow.models.customer import Customer


class CustomerTableModel(QAbstractTableModel):

    HEADERS = [
        "Name",
        "Kurzname",
        "Ort",
        "Aktiv",
    ]

    def __init__(self, customers=None):
        super().__init__()
        self._customers = customers or []

    def rowCount(self, parent=QModelIndex()):
        return len(self._customers)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=Qt.DisplayRole):

        if not index.isValid():
            return None

        customer = self._customers[index.row()]

        if role == Qt.DisplayRole:

            match index.column():

                case 0:
                    return customer.name

                case 1:
                    return customer.short_name

                case 2:
                    return (
                        f"{customer.postal_code} "
                        f"{customer.city}"
                    ).strip()

                case 3:
                    return (
                        "Ja"
                        if customer.active
                        else "Nein"
                    )

        if role == Qt.TextAlignmentRole:

            if index.column() == 3:
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

    def setCustomers(self, customers):
        self.beginResetModel()
        self._customers = customers
        self.endResetModel()

    def customer_at(self, row):

        if row < 0 or row >= len(self._customers):
            return None

        return self._customers[row]

    def sort(self, column, order):

        reverse = (
            order == Qt.SortOrder.DescendingOrder
        )

        self.layoutAboutToBeChanged.emit()

        match column:

            case 0:
                self._customers.sort(
                    key=lambda c: c.name.upper(),
                    reverse=reverse,
                )

            case 1:
                self._customers.sort(
                    key=lambda c: (
                        c.short_name or ""
                    ).upper(),
                    reverse=reverse,
                )

            case 2:
                self._customers.sort(
                    key=lambda c: (
                        c.postal_code,
                        c.city.upper(),
                    ),
                    reverse=reverse,
                )

            case 3:
                self._customers.sort(
                    key=lambda c: c.active,
                    reverse=reverse,
                )

        self.layoutChanged.emit()
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
)


class TourTableModel(QAbstractTableModel):
    HEADERS = [
        "Tournummer",
        "Datum",
        "Fahrer",
        "Fahrzeug",
        "Aufträge",
        "Status",
    ]

    def __init__(self, tours=None):
        super().__init__()
        self._tours = list(tours or [])

    def rowCount(self, parent=QModelIndex()):
        return len(self._tours)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(
        self,
        index,
        role=Qt.ItemDataRole.DisplayRole,
    ):
        if not index.isValid():
            return None

        tour = self._tours[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            values = [
                tour.tour_number,
                tour.tour_date.strftime("%d.%m.%Y"),
                tour.driver_display,
                tour.vehicle_display,
                str(tour.order_count),
                tour.status,
            ]
            return values[index.column()]

        if (
            role == Qt.ItemDataRole.TextAlignmentRole
            and index.column() in (1, 4, 5)
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

    def set_tours(self, tours):
        self.beginResetModel()
        self._tours = list(tours)
        self.endResetModel()

    def tour_at(self, row):
        if 0 <= row < len(self._tours):
            return self._tours[row]
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
            0: lambda item: item.tour_number.casefold(),
            1: lambda item: item.tour_date,
            2: lambda item: item.driver_display.casefold(),
            3: lambda item: item.vehicle_display.casefold(),
            4: lambda item: item.order_count,
            5: lambda item: item.status.casefold(),
        }

        self.layoutAboutToBeChanged.emit()
        self._tours.sort(
            key=keys.get(column, keys[0]),
            reverse=reverse,
        )
        self.layoutChanged.emit()

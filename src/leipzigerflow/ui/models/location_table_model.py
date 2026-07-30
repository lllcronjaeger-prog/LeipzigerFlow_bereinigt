from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
)

from leipzigerflow.models.location import Location


class LocationTableModel(QAbstractTableModel):

    HEADERS = [
        "Typ",
        "Kunde",
        "Kurzname",
        "Name",
        "Ort",
        "Ansprechpartner",
        "Telefon",
        "Aktiv",
    ]

    def __init__(self, locations=None):
        super().__init__()
        self._locations = locations or []

    def rowCount(self, parent=QModelIndex()):
        return len(self._locations)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=Qt.DisplayRole):

        if not index.isValid():
            return None

        location = self._locations[index.row()]

        if role == Qt.DisplayRole:

            match index.column():

                case 0:
                    return location.location_type.display_name

                case 1:
                    return location.customer.display_name if location.customer else "—"

                case 2:
                    return location.short_name

                case 3:
                    return location.name

                case 4:
                    return (
                        f"{location.postal_code} "
                        f"{location.city}"
                    ).strip()

                case 5:
                    return location.contact_person

                case 6:
                    return location.phone

                case 7:
                    return "Ja" if location.active else "Nein"

        if role == Qt.TextAlignmentRole:

            if index.column() == 7:
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

    def setLocations(self, locations):
        self.beginResetModel()
        self._locations = locations
        self.endResetModel()

    def location_at(self, row):

        if row < 0 or row >= len(self._locations):
            return None

        return self._locations[row]

    def sort(self, column, order):

        reverse = (
            order == Qt.SortOrder.DescendingOrder
        )

        self.layoutAboutToBeChanged.emit()

        match column:

            case 0:
                self._locations.sort(
                    key=lambda l: l.location_type.value,
                    reverse=reverse,
                )

            case 1:
                self._locations.sort(
                    key=lambda l: (l.customer.display_name if l.customer else "").upper(),
                    reverse=reverse,
                )

            case 2:
                self._locations.sort(
                    key=lambda l: (l.short_name or "").upper(),
                    reverse=reverse,
                )

            case 3:
                self._locations.sort(
                    key=lambda l: l.name.upper(),
                    reverse=reverse,
                )

            case 4:
                self._locations.sort(
                    key=lambda l: (
                        l.postal_code,
                        l.city.upper(),
                    ),
                    reverse=reverse,
                )

            case 5:
                self._locations.sort(
                    key=lambda l: (l.contact_person or "").upper(),
                    reverse=reverse,
                )

            case 6:
                self._locations.sort(
                    key=lambda l: l.phone,
                    reverse=reverse,
                )

            case 7:
                self._locations.sort(
                    key=lambda l: l.active,
                    reverse=reverse,
                )

        self.layoutChanged.emit()
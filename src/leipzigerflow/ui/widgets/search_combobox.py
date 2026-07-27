from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter


class SearchComboBox(QComboBox):
    """
    Editierbare ComboBox mit integrierter Suche.
    Basisklasse für alle Such-Comboboxen.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self.setMaxVisibleItems(15)

        completer = QCompleter(self.model(), self)
        completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        completer.setFilterMode(
            Qt.MatchFlag.MatchContains
        )

        self.setCompleter(completer)

    def current_object(self):
        """
        Gibt das aktuell ausgewählte Objekt zurück.
        """
        return self.currentData()

    def set_current_object(self, obj):
        """
        Wählt anhand des gespeicherten Objekts den Eintrag aus.
        """
        for row in range(self.count()):
            if self.itemData(row) == obj:
                self.setCurrentIndex(row)
                return

    def clear_items(self):
        self.clear()

    def add_object(self, text, obj):
        self.addItem(text, obj)
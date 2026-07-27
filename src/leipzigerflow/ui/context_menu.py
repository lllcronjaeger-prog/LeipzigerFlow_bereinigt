"""Einheitliche, kompakte Kontextmenüs für LeipzigerFlow."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QMenu, QWidget


_CONTEXT_MENU_STYLESHEET = """
QMenu {
    color: #0f172a;
    background-color: #ffffff;
    border: 1px solid #94a3b8;
    border-radius: 6px;
    padding: 3px;
}
QMenu::item {
    color: #0f172a;
    background-color: transparent;
    padding: 5px 24px 5px 9px;
    margin: 0;
    border-radius: 4px;
    min-width: 145px;
}
QMenu::item:selected {
    color: #ffffff;
    background-color: #2563eb;
}
QMenu::item:disabled {
    color: #94a3b8;
    background-color: transparent;
}
QMenu::separator {
    height: 1px;
    background-color: #cbd5e1;
    margin: 3px 5px;
}
"""


class CompactContextMenu(QMenu):
    """Kontrastreiches Qt-Menü mit bewusst wenigen Einträgen je Ebene."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSeparatorsCollapsible(True)
        self._apply_readable_appearance()

    def _apply_readable_appearance(self) -> None:
        palette = QPalette()
        for role in (
            QPalette.ColorRole.Window,
            QPalette.ColorRole.Base,
            QPalette.ColorRole.Button,
        ):
            palette.setColor(QPalette.ColorGroup.All, role, QColor("#ffffff"))
        for role in (
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.Text,
            QPalette.ColorRole.ButtonText,
        ):
            palette.setColor(QPalette.ColorGroup.Active, role, QColor("#0f172a"))
            palette.setColor(QPalette.ColorGroup.Inactive, role, QColor("#0f172a"))
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#94a3b8"))
        palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Highlight, QColor("#2563eb"))
        palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(palette)

        app = QApplication.instance()
        base_font = app.font() if app is not None else QFont()
        font = QFont(base_font)
        if font.pointSizeF() <= 0:
            font.setPointSize(10)
        self.setFont(font)
        self.setStyleSheet(_CONTEXT_MENU_STYLESHEET)

    def addMenu(self, title_or_menu):  # type: ignore[override]
        submenu = super().addMenu(title_or_menu)
        submenu.setPalette(self.palette())
        submenu.setFont(self.font())
        submenu.setStyleSheet(_CONTEXT_MENU_STYLESHEET)
        submenu.setSeparatorsCollapsible(True)
        return submenu


def create_context_menu(parent: QWidget | None = None) -> CompactContextMenu:
    return CompactContextMenu(parent)

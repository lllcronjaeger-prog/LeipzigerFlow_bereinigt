from __future__ import annotations

from PySide6.QtGui import QColor


STATUS_COLORS = {
    "Neu": ("#dbeafe", "#1d4ed8"),
    "Geplant": ("#ede9fe", "#6d28d9"),
    "Unterwegs": ("#cffafe", "#0e7490"),
    "Erledigt": ("#e5e7eb", "#4b5563"),
    "Abgeschlossen": ("#e5e7eb", "#4b5563"),
    "Storniert": ("#fee2e2", "#991b1b"),
}

PRIORITY_COLORS = {
    "Eigenfuhrpark bevorzugt": ("#dcfce7", "#166534"),
    "Flexibel": ("#fef3c7", "#92400e"),
    "Verkauf bevorzugt": ("#e0e7ff", "#3730a3"),
}

STATUS_ICONS = {
    "Neu": "●", "Geplant": "◆", "Unterwegs": "▶",
    "Erledigt": "✓", "Abgeschlossen": "✓", "Storniert": "×",
}

PRIORITY_ICONS = {
    "Eigenfuhrpark bevorzugt": "▣", "Flexibel": "↔", "Verkauf bevorzugt": "€",
}


def colors_for_status(status: str) -> tuple[QColor, QColor]:
    background, foreground = STATUS_COLORS.get(status, ("#ffffff", "#0f172a"))
    return QColor(background), QColor(foreground)


def colors_for_priority(priority: str) -> tuple[QColor, QColor]:
    background, foreground = PRIORITY_COLORS.get(priority, ("#ffffff", "#0f172a"))
    return QColor(background), QColor(foreground)


def application_stylesheet() -> str:
    """Zentrales helles Theme für alle Arbeitsfenster und Dialoge."""
    return """
    QWidget { color:#0f172a; font-size:13px; }
    QMainWindow, QDialog { background:#f1f5f9; color:#0f172a; }
    QLabel { color:#0f172a; background:transparent; }
    QToolBar { background:#ffffff; border-bottom:1px solid #dbe3ee; spacing:5px; padding:5px; }
    QToolButton, QPushButton {
        color:#0f172a; background:#ffffff; border:1px solid #cbd5e1;
        border-radius:6px; padding:6px 10px;
    }
    QToolButton:hover, QPushButton:hover { background:#e2e8f0; }
    QToolButton:pressed, QPushButton:pressed { background:#cbd5e1; }
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QDateEdit, QTimeEdit, QSpinBox, QDoubleSpinBox {
        color:#0f172a; background:#ffffff; border:1px solid #cbd5e1;
        border-radius:6px; padding:6px; selection-color:#ffffff;
        selection-background-color:#2563eb;
    }
    QComboBox QAbstractItemView, QAbstractItemView {
        color:#0f172a; background:#ffffff; selection-color:#0f172a;
        selection-background-color:#dbeafe;
    }
    QTableView, QTableWidget, QTreeView, QListView, QListWidget {
        color:#0f172a; background:#ffffff; alternate-background-color:#f8fafc;
        border:1px solid #dbe3ee; gridline-color:#e2e8f0;
        selection-color:#0f172a; selection-background-color:#dbeafe;
    }
    QTableView::item, QTableWidget::item, QTreeView::item, QListView::item {
        color:#0f172a; padding:4px;
    }
    QHeaderView::section {
        color:#0f172a; background:#e2e8f0; border:none;
        border-right:1px solid #cbd5e1; padding:7px; font-weight:600;
    }
    QTabWidget::pane { background:#ffffff; border:1px solid #cbd5e1; }
    QTabBar::tab { color:#334155; background:#e2e8f0; padding:8px 14px; margin-right:2px; }
    QTabBar::tab:selected { color:#ffffff; background:#2563eb; font-weight:700; }
    QMenu { color:#0f172a; background:#ffffff; border:1px solid #cbd5e1; padding:5px; }
    QMenu::item { color:#0f172a; padding:7px 24px 7px 10px; border-radius:4px; }
    QMenu::item:selected { color:#ffffff; background:#2563eb; }
    QStatusBar { color:#334155; background:#ffffff; border-top:1px solid #dbe3ee; }
    QGroupBox { color:#0f172a; font-weight:600; border:1px solid #cbd5e1; border-radius:7px; margin-top:9px; padding-top:8px; }
    QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 4px; }
    QCheckBox, QRadioButton { color:#0f172a; spacing:6px; }
    QScrollArea { background:transparent; border:none; }
    QScrollArea > QWidget > QWidget { background:#ffffff; }
    QFrame#tourWarningsPanel { background:#ffffff; border:1px solid #cbd5e1; border-radius:7px; }
    QLabel#tourWarningsTitle { color:#0f172a; font-size:14px; font-weight:700; }
    QLabel#tourWarningsOk { color:#166534; background:#dcfce7; border:1px solid #86efac; border-radius:5px; padding:7px; font-weight:600; }
    QLabel#warningError { color:#991b1b; background:#fee2e2; border:1px solid #fecaca; border-radius:5px; padding:7px; }
    QLabel#warningWarning { color:#92400e; background:#fef3c7; border:1px solid #fcd34d; border-radius:5px; padding:7px; }
    QLabel#warningInfo { color:#1e40af; background:#dbeafe; border:1px solid #93c5fd; border-radius:5px; padding:7px; }
    QLabel#mutedText { color:#64748b; font-size:12px; }
    QFrame#timelinePanel { background:#ffffff; border:1px solid #cbd5e1; border-radius:7px; }
    QSplitter::handle:vertical { background:#cbd5e1; height:7px; margin:1px 80px; border-radius:3px; }
    QSplitter::handle:vertical:hover { background:#2563eb; }
    """

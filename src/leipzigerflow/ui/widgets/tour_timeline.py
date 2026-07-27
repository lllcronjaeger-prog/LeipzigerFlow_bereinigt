from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from leipzigerflow.planner.timeline import build_timeline_entries


_KIND_META = {
    "loading": ("L", "Laden"),
    "unloading": ("E", "Entladen"),
    "loaded_travel": ("F", "Fahrt"),
    "empty_run": ("LF", "Leerfahrt"),
    "break": ("P", "Pause"),
    "rest": ("R", "Ruhezeit"),
    "waiting": ("W", "Warten"),
}


class TourTimelineWidget(QWidget):
    """Kompakte horizontale Tour-Zeitachse ohne redundante Ereignistabelle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tourTimeline")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("timelineScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setMinimumHeight(150)
        self.scroll_area.setSizeAdjustPolicy(QScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self.container = QWidget()
        self.container.setObjectName("timelineContainer")
        self.cards = QHBoxLayout(self.container)
        self.cards.setContentsMargins(4, 4, 4, 4)
        self.cards.setSpacing(8)
        self.scroll_area.setWidget(self.container)
        root.addWidget(self.scroll_area)


    def _clear_cards(self) -> None:
        while self.cards.count():
            item = self.cards.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def set_schedule(self, schedule) -> None:
        self._clear_cards()
        entries = build_timeline_entries(schedule)
        if not entries:
            empty = QLabel("Keine Zeitachsen-Daten vorhanden")
            empty.setObjectName("timelineEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumWidth(320)
            self.cards.addWidget(empty)
            self.cards.addStretch(1)
            return

        for row_index, entry in enumerate(entries):
            icon, caption = _KIND_META.get(entry.kind, ("•", entry.kind))
            duration_minutes = max(0, int((entry.ended_at - entry.started_at).total_seconds() // 60))

            card = QFrame()
            card.setObjectName("timelineBlock")
            card.setProperty("timelineKind", entry.kind)
            card.setMinimumWidth(max(150, min(290, 120 + duration_minutes)))
            card.setMaximumWidth(320)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(3)
            title = QLabel(f"<b>{icon} · {caption}</b>")
            title.setTextFormat(Qt.TextFormat.RichText)
            card_layout.addWidget(title)
            period = QLabel(f"{entry.started_at:%d.%m. %H:%M} – {entry.ended_at:%d.%m. %H:%M}")
            period.setObjectName("timelinePeriod")
            card_layout.addWidget(period)
            description = QLabel(entry.title)
            description.setWordWrap(True)
            card_layout.addWidget(description)
            if entry.detail:
                detail = QLabel(entry.detail)
                detail.setObjectName("timelineDetail")
                detail.setWordWrap(True)
                card_layout.addWidget(detail)
            self.cards.addWidget(card)



        self.cards.addStretch(1)

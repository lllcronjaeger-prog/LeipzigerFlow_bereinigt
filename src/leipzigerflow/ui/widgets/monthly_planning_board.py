from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


class MonthlyPlanningBoard(QWidget):
    dayRequested = Signal(object)

    DAY_NAMES = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(6)

    def set_data(self, anchor_date, tours):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for col, name in enumerate(self.DAY_NAMES):
            label = QLabel(f"<b>{name}</b>")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(label, 0, col)

        grouped = defaultdict(list)
        for tour in tours:
            day = _as_date(tour.tour_date)
            if day:
                grouped[day].append(tour)

        year, month = anchor_date.year, anchor_date.month
        cal = calendar.Calendar(firstweekday=0)
        for row, week in enumerate(cal.monthdatescalendar(year, month), start=1):
            for col, day in enumerate(week):
                day_tours = grouped.get(day, []) if day.month == month else []
                vehicles = {t.vehicle_display for t in day_tours if t.vehicle_display}
                active = sum(t.status == "Unterwegs" for t in day_tours)
                text = f"{day.day}\n{len(day_tours)} Touren\n{len(vehicles)} Fahrzeuge"
                if active:
                    text += f"\n{active} unterwegs"
                button = QPushButton(text)
                button.setObjectName("monthDayOutside" if day.month != month else "monthDay")
                button.setEnabled(day.month == month)
                button.setMinimumHeight(92)
                button.clicked.connect(lambda checked=False, d=day: self.dayRequested.emit(d))
                self.grid.addWidget(button, row, col)

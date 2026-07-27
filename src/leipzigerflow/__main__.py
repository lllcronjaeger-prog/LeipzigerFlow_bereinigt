import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from leipzigerflow.database.base import Base
from leipzigerflow.database.schema_migrations import (
    migrate_database,
)
from leipzigerflow.database.session import engine

from leipzigerflow.models.customer import Customer
from leipzigerflow.models.driver import Driver
from leipzigerflow.models.location import Location
from leipzigerflow.models.tour import Tour
from leipzigerflow.models.tour_position import TourPosition
from leipzigerflow.models.transport_order import (
    TransportOrder,
)
from leipzigerflow.models.vehicle import Vehicle
from leipzigerflow.models.vehicle_staffing_profile import VehicleStaffingProfile
from leipzigerflow.models.route_cache import GeocodeCacheEntry, RouteCacheEntry
from leipzigerflow.models.resource_absence import VehicleAbsence, TrailerAbsence
from leipzigerflow.models.trailer import Trailer

from leipzigerflow.ui.main_window import MainWindow
from leipzigerflow.ui.theme import application_stylesheet


def create_database_tables() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_database(engine)


def main() -> int:
    create_database_tables()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2563eb"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(application_stylesheet())

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

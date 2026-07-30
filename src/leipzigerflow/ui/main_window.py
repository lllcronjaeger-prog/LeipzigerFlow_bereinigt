from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStatusBar, QToolBar, QWidget

from leipzigerflow.config.settings import APP_NAME, VERSION
from leipzigerflow.database.database import SessionLocal
from leipzigerflow.ui.dialogs.ai_assistant_dialog import AiAssistantDialog
from leipzigerflow.ui.dialogs.ai_settings_dialog import AiSettingsDialog
from leipzigerflow.ui.dialogs.customer_dialog import CustomerDialog
from leipzigerflow.ui.dialogs.database_settings_dialog import DatabaseSettingsDialog
from leipzigerflow.ui.dialogs.driver_dialog import DriverDialog
from leipzigerflow.ui.dialogs.driver_import_dialog import DriverImportDialog
from leipzigerflow.ui.dialogs.vehicle_import_dialog import VehicleImportDialog
from leipzigerflow.ui.dialogs.fleet_utilization_dialog import FleetUtilizationDialog
from leipzigerflow.ui.dialogs.location_dialog import LocationDialog
from leipzigerflow.ui.dialogs.planning_board_dialog import PlanningBoardDialog
from leipzigerflow.ui.dialogs.tour_dialog import TourDialog
from leipzigerflow.ui.dialogs.trailer_dialog import TrailerDialog
from leipzigerflow.ui.dialogs.transport_order_dialog import TransportOrderDialog
from leipzigerflow.ui.dialogs.vehicle_dialog import VehicleDialog
from leipzigerflow.ui.widgets.dashboard_widget import DashboardWidget
from leipzigerflow.ui.windows.window_manager import WindowManager
from leipzigerflow.services.daily_tour_service import DailyTourService
from leipzigerflow.services.user_session import UserSession
from leipzigerflow.services.auth_service import AuthService
from leipzigerflow.models.auth import User
from leipzigerflow.ui.dialogs.password_dialog import ChangePasswordDialog
from leipzigerflow.ui.dialogs.user_management_dialog import UserManagementDialog


class MainWindow(QMainWindow):
    """Zentrale Navigation für den Multi-Monitor-Arbeitsplatz."""

    logout_requested = Signal()

    def __init__(self, user_session: UserSession | None = None):
        super().__init__()
        self.user_session = user_session or UserSession()

        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.resize(1350, 900)

        self.window_manager = WindowManager(self)
        self.window_manager.window_opened.connect(self._on_workspace_changed)
        self.window_manager.window_closed.connect(self._on_workspace_changed)
        self._register_workspace_windows()

        self._create_actions()
        self._create_menu()
        self._create_toolbar()
        self._create_statusbar()
        self._create_central_widget()
        self._apply_permissions()

        self._last_daily_tour_check = None
        self._ensure_daily_tours()
        self._daily_tour_timer = QTimer(self)
        self._daily_tour_timer.setInterval(15 * 60 * 1000)
        self._daily_tour_timer.timeout.connect(self._ensure_daily_tours)
        self._daily_tour_timer.start()

        # Zuletzt geöffnete Arbeitsfenster erst nach dem Aufbau des Hauptfensters laden.
        QTimer.singleShot(0, self.window_manager.restore_workspace)


    def _ensure_daily_tours(self) -> None:
        from datetime import date
        current_day = date.today()
        if self._last_daily_tour_check == current_day:
            return
        session = SessionLocal()
        try:
            created = DailyTourService(session).ensure_for_day(current_day)
            self._last_daily_tour_check = current_day
            if created:
                self.statusBar().showMessage(f"{created} Tagestour(en) automatisch angelegt", 10000)
        except Exception as exc:
            session.rollback()
            self.statusBar().showMessage(f"Automatische Touranlage nicht möglich: {exc}", 15000)
        finally:
            session.close()

    def _session_window_factory(
        self,
        dialog_class: type[QWidget],
    ) -> Callable[[], tuple[QWidget, Callable[[], None]]]:
        def factory() -> tuple[QWidget, Callable[[], None]]:
            session = SessionLocal()
            try:
                content = dialog_class(session=session, parent=None)
            except Exception:
                session.close()
                raise
            return content, session.close

        return factory

    @staticmethod
    def _self_managed_factory(
        dialog_class: type[QWidget],
    ) -> Callable[[], tuple[QWidget, Callable[[], None] | None]]:
        def factory() -> tuple[QWidget, Callable[[], None] | None]:
            content = dialog_class(parent=None)
            session = getattr(content, "session", None)
            cleanup = session.close if session is not None else None
            return content, cleanup

        return factory

    def _register_workspace_windows(self) -> None:
        self.window_manager.register(
            "planning_board",
            "Plantafel · LeipzigerFlow",
            self._session_window_factory(PlanningBoardDialog),
        )
        self.window_manager.register(
            "transport_orders",
            "Transportaufträge · LeipzigerFlow",
            self._session_window_factory(TransportOrderDialog),
        )
        self.window_manager.register(
            "tours",
            "Touren · LeipzigerFlow",
            self._session_window_factory(TourDialog),
        )
        self.window_manager.register(
            "customers",
            "Kunden · LeipzigerFlow",
            self._session_window_factory(CustomerDialog),
        )
        self.window_manager.register(
            "drivers",
            "Fahrer · LeipzigerFlow",
            self._session_window_factory(DriverDialog),
        )
        self.window_manager.register(
            "locations",
            "Standorte · LeipzigerFlow",
            self._self_managed_factory(LocationDialog),
        )
        self.window_manager.register(
            "vehicles",
            "Zugmaschinen · LeipzigerFlow",
            self._self_managed_factory(VehicleDialog),
        )
        self.window_manager.register(
            "trailers",
            "Trailer · LeipzigerFlow",
            self._self_managed_factory(TrailerDialog),
        )
        self.window_manager.register(
            "fleet_utilization",
            "Flottenauswertung · LeipzigerFlow",
            self._session_window_factory(FleetUtilizationDialog),
        )

    def _create_actions(self):
        self.action_change_password = QAction("Passwort ändern", self)
        self.action_change_password.triggered.connect(self.change_password)

        self.action_logout = QAction("Benutzer wechseln / Abmelden", self)
        self.action_logout.triggered.connect(self._request_logout)

        self.action_exit = QAction("Beenden", self)
        self.action_exit.triggered.connect(self.close)

        self.action_dashboard = QAction("Dashboard", self)
        self.action_dashboard.triggered.connect(self.show_dashboard)

        self.action_customers = QAction("Kunden", self)
        self.action_customers.triggered.connect(self.open_customer_dialog)

        self.action_locations = QAction("Standorte", self)
        self.action_locations.triggered.connect(self.open_location_dialog)

        self.action_driver_import = QAction("Fahrer aus Excel importieren", self)
        self.action_driver_import.triggered.connect(self.open_driver_import)

        self.action_vehicle_import = QAction("Fahrzeuge aus Excel importieren", self)
        self.action_vehicle_import.triggered.connect(self.open_vehicle_import)

        self.action_drivers = QAction("Fahrer", self)
        self.action_drivers.triggered.connect(self.open_driver_dialog)

        self.action_vehicles = QAction("Zugmaschinen", self)
        self.action_vehicles.triggered.connect(self.open_vehicle_dialog)

        self.action_trailers = QAction("Trailer", self)
        self.action_trailers.triggered.connect(self.open_trailer_dialog)

        self.action_transport_orders = QAction("Transportaufträge und Archiv", self)
        self.action_transport_orders.triggered.connect(self.open_transport_order_dialog)

        self.action_tours = QAction("Touren und Tourarchiv", self)
        self.action_tours.triggered.connect(self.open_tour_dialog)

        self.action_planning_board = QAction("Plantafel", self)
        self.action_planning_board.triggered.connect(self.open_planning_board)

        self.action_ai_assistant = QAction("LeipzigerAI – Dispositionsassistent", self)
        self.action_ai_assistant.triggered.connect(self.open_ai_assistant)

        self.action_ai_settings = QAction("KI-Einstellungen", self)
        self.action_ai_settings.triggered.connect(self.open_ai_settings)

        self.action_fleet_utilization = QAction("Flottenauswertung", self)
        self.action_fleet_utilization.triggered.connect(self.open_fleet_utilization)

        self.action_user_management = QAction("Benutzer und Rollen", self)
        self.action_user_management.triggered.connect(self.open_user_management)

        self.action_database_settings = QAction("Datenbank und Speicher", self)
        self.action_database_settings.triggered.connect(self.open_database_settings)

        self.action_refresh_windows = QAction("Alle Fenster aktualisieren", self)
        self.action_refresh_windows.triggered.connect(self.window_manager.refresh_all)

        self.action_about = QAction("Über", self)
        self.action_about.triggered.connect(self.show_about)

    def _create_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("Datei")
        file_menu.addAction(self.action_dashboard)
        file_menu.addSeparator()
        file_menu.addAction(self.action_change_password)
        file_menu.addAction(self.action_logout)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

        master_menu = menu.addMenu("Stammdaten")
        master_menu.addAction(self.action_customers)
        master_menu.addAction(self.action_locations)
        master_menu.addSeparator()
        master_menu.addAction(self.action_drivers)
        master_menu.addAction(self.action_vehicles)
        master_menu.addAction(self.action_trailers)

        data_menu = menu.addMenu("Import / Export")
        data_menu.addAction(self.action_driver_import)
        data_menu.addAction(self.action_vehicle_import)

        planning_menu = menu.addMenu("Planung")
        planning_menu.addAction(self.action_transport_orders)
        planning_menu.addAction(self.action_tours)
        planning_menu.addSeparator()
        planning_menu.addAction(self.action_planning_board)

        window_menu = menu.addMenu("Fenster")
        window_menu.addAction(self.action_planning_board)
        window_menu.addAction(self.action_transport_orders)
        window_menu.addAction(self.action_tours)
        window_menu.addSeparator()
        window_menu.addAction(self.action_drivers)
        window_menu.addAction(self.action_vehicles)
        window_menu.addAction(self.action_trailers)
        window_menu.addSeparator()
        window_menu.addAction(self.action_fleet_utilization)
        window_menu.addSeparator()
        window_menu.addAction(self.action_refresh_windows)

        reports_menu = menu.addMenu("Auswertungen")
        reports_menu.addAction(self.action_fleet_utilization)

        ai_menu = menu.addMenu("KI")
        ai_menu.addAction(self.action_ai_assistant)
        ai_menu.addSeparator()
        ai_menu.addAction(self.action_ai_settings)

        extras_menu = menu.addMenu("Extras")
        extras_menu.addAction(self.action_user_management)
        extras_menu.addSeparator()
        extras_menu.addAction(self.action_database_settings)

        help_menu = menu.addMenu("Hilfe")
        help_menu.addAction(self.action_about)

    def _create_toolbar(self):
        toolbar = QToolBar("Hauptwerkzeugleiste", self)
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.action_dashboard)
        toolbar.addSeparator()
        toolbar.addAction(self.action_customers)
        toolbar.addAction(self.action_locations)
        toolbar.addSeparator()
        toolbar.addAction(self.action_drivers)
        toolbar.addAction(self.action_vehicles)
        toolbar.addAction(self.action_trailers)
        toolbar.addSeparator()
        toolbar.addAction(self.action_transport_orders)
        toolbar.addAction(self.action_tours)
        toolbar.addAction(self.action_planning_board)
        self.addToolBar(toolbar)

    def _create_statusbar(self):
        status = QStatusBar()
        status.showMessage(self._status_message())
        self.setStatusBar(status)

    def _create_central_widget(self):
        self.dashboard = DashboardWidget(
            open_orders=self.open_transport_order_dialog,
            open_tours=self.open_tour_dialog,
            open_planning_board=self.open_planning_board,
            open_drivers=self.open_driver_dialog,
            open_vehicles=self.open_vehicle_dialog,
            open_trailers=self.open_trailer_dialog,
            parent=self,
        )
        self.setCentralWidget(self.dashboard)


    def _status_message(self) -> str:
        if self.user_session.is_authenticated:
            return f"Angemeldet als {self.user_session.label} · Multi-Monitor-Arbeitsplatz aktiv"
        return "Bereit · Multi-Monitor-Arbeitsplatz aktiv"

    def _apply_permissions(self) -> None:
        permission_actions = {
            "customers.view": (self.action_customers,),
            "fleet.view": (
                self.action_locations,
                self.action_drivers,
                self.action_vehicles,
                self.action_trailers,
                self.action_fleet_utilization,
                self.action_driver_import,
                self.action_vehicle_import,
            ),
            "orders.view": (self.action_transport_orders, self.action_tours),
            "planning.view": (self.action_planning_board,),
            "ai.use": (self.action_ai_assistant,),
            "users.manage": (self.action_user_management,),
            "api.manage": (self.action_ai_settings,),
            "settings.edit": (self.action_database_settings,),
        }
        if not self.user_session.is_authenticated:
            return
        for permission, actions in permission_actions.items():
            allowed = self.user_session.has_permission(permission)
            for action in actions:
                action.setEnabled(allowed)
                action.setVisible(allowed)

    def _request_logout(self) -> None:
        answer = QMessageBox.question(
            self,
            "Benutzer wechseln",
            "Möchten Sie sich abmelden und einen anderen Benutzer anmelden?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.logout_requested.emit()

    def change_password(self) -> None:
        if not self.user_session.user_id:
            return
        session = SessionLocal()
        try:
            user = session.get(User, self.user_session.user_id)
            if user is None:
                QMessageBox.warning(self, "Passwort ändern", "Der angemeldete Benutzer wurde nicht gefunden.")
                return
            if ChangePasswordDialog(session, user, parent=self).exec():
                self.user_session.must_change_password = False
                QMessageBox.information(self, "Passwort ändern", "Das Passwort wurde geändert.")
        finally:
            session.close()

    def open_fleet_utilization(self):
        self.window_manager.open("fleet_utilization")

    def open_ai_assistant(self):
        AiAssistantDialog(self).exec()

    def open_ai_settings(self):
        AiSettingsDialog(self).exec()

    def open_user_management(self):
        session = SessionLocal()
        try:
            UserManagementDialog(
                session,
                current_user_id=self.user_session.user_id,
                parent=self,
            ).exec()
        finally:
            session.close()

    def open_database_settings(self):
        DatabaseSettingsDialog(self).exec()

    def show_dashboard(self):
        self.dashboard.refresh()
        self.dashboard.setFocus()
        self.raise_()
        self.activateWindow()

    def _refresh_dashboard(self):
        if hasattr(self, "dashboard"):
            self.dashboard.refresh()

    def _on_workspace_changed(self, _key: str) -> None:
        self._refresh_dashboard()

    def open_customer_dialog(self):
        self.window_manager.open("customers")

    def open_location_dialog(self):
        self.window_manager.open("locations")

    def open_driver_dialog(self):
        self.window_manager.open("drivers")

    def open_driver_import(self):
        session = SessionLocal()
        try:
            if DriverImportDialog(session, parent=self).exec():
                self.window_manager.refresh_all()
                self._refresh_dashboard()
        finally:
            session.close()

    def open_vehicle_import(self):
        session = SessionLocal()
        try:
            if VehicleImportDialog(session, parent=self).exec():
                self.window_manager.refresh_all()
                self._refresh_dashboard()
        finally:
            session.close()

    def open_vehicle_dialog(self):
        self.window_manager.open("vehicles")

    def open_trailer_dialog(self):
        self.window_manager.open("trailers")

    def open_transport_order_dialog(self):
        self.window_manager.open("transport_orders")

    def open_tour_dialog(self):
        self.window_manager.open("tours")

    def open_planning_board(self):
        self.window_manager.open("planning_board")

    def show_about(self):
        QMessageBox.about(
            self,
            "Über LeipzigerFlow",
            f"{APP_NAME}\nVersion {VERSION}\n\n"
            "Dispositions- und Tourenplanungssystem\n"
            "Multi-Monitor-Arbeitsplatz",
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        self.window_manager.close_all(preserve_workspace=True)
        super().closeEvent(event)

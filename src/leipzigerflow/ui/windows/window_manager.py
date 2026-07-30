from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QByteArray, QEvent, QObject, QSettings, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget


@dataclass(slots=True)
class WindowDefinition:
    key: str
    title: str
    factory: Callable[[], tuple[QWidget, Callable[[], None] | None]]


class ManagedToolWindow(QMainWindow):
    """Eigenständiges Arbeitsfenster für einen bisherigen Dialoginhalt.

    Das Fenster ist nicht modal, kann auf einen anderen Monitor verschoben werden
    und speichert seine Geometrie. Bestehende QDialog-Oberflächen werden als
    Zentral-Widget eingebettet, sodass ihre Fachlogik unverändert weiterläuft.
    """

    activated = Signal(str)
    closing = Signal(str)

    def __init__(
        self,
        *,
        key: str,
        title: str,
        content: QWidget,
        settings: QSettings,
        cleanup: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(None)
        self._key = key
        self._settings = settings
        self._cleanup = cleanup
        self._cleaned_up = False

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(title)
        self.setObjectName(f"managed_window_{key}")

        if isinstance(content, QDialog):
            content.setModal(False)
            content.setWindowFlags(Qt.WindowType.Widget)
            content.accepted.connect(self.close)
            content.rejected.connect(self.close)

        content.setParent(self)
        self.setCentralWidget(content)
        self._content = content
        self._restore_geometry()

    @property
    def content(self) -> QWidget:
        return self._content

    def _restore_geometry(self) -> None:
        geometry = self._settings.value(f"windows/{self._key}/geometry")
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)
            self._ensure_visible_on_screen()
            return
        preferred = getattr(self._content, "preferred_workspace_size", None)
        if preferred is not None:
            width, height = preferred
        else:
            width = max(1200, self._content.minimumSizeHint().width(), self._content.sizeHint().width())
            height = max(760, self._content.minimumSizeHint().height(), self._content.sizeHint().height())
        self.resize(width, height)

    def _ensure_visible_on_screen(self) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            return
        frame = self.frameGeometry()
        if any(screen.availableGeometry().intersects(frame) for screen in screens):
            return
        target = QGuiApplication.primaryScreen().availableGeometry()
        width = min(max(self.minimumWidth(), self.width()), target.width())
        height = min(max(self.minimumHeight(), self.height()), target.height())
        self.resize(width, height)
        self.move(target.center() - self.rect().center())

    def _refresh_content(self) -> None:
        for method_name in (
            "refresh",
            "_load_tours",
            "_load_orders",
            "_load_drivers",
            "_load_vehicles",
            "_load_trailers",
            "_load_customers",
            "_load_locations",
            "_apply_filters",
        ):
            method = getattr(self._content, method_name, None)
            if callable(method):
                try:
                    method()
                except TypeError:
                    continue
                except RuntimeError:
                    return
                break

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.WindowActivate:
            self._refresh_content()
            self.activated.emit(self._key)
        return super().event(event)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._settings.setValue(f"windows/{self._key}/geometry", self.saveGeometry())
        self._settings.sync()
        self.closing.emit(self._key)
        self._run_cleanup()
        super().closeEvent(event)

    def _run_cleanup(self) -> None:
        if self._cleaned_up:
            return
        self._cleaned_up = True
        if self._cleanup is not None:
            self._cleanup()


class WindowManager(QObject):
    """Verwaltet eigenständige LeipzigerFlow-Fenster zentral.

    Pro Arbeitsbereich existiert höchstens ein Fenster. Bereits geöffnete Fenster
    werden in den Vordergrund geholt. Position, Größe und zuletzt geöffnete
    Arbeitsbereiche werden benutzerbezogen gespeichert.
    """

    window_opened = Signal(str)
    window_closed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = QSettings("LeipzigerFlow", "Workspace")
        self._definitions: dict[str, WindowDefinition] = {}
        self._windows: dict[str, ManagedToolWindow] = {}
        self._shutting_down = False

    def register(
        self,
        key: str,
        title: str,
        factory: Callable[[], tuple[QWidget, Callable[[], None] | None]],
    ) -> None:
        self._definitions[key] = WindowDefinition(key=key, title=title, factory=factory)

    def open(self, key: str) -> ManagedToolWindow:
        existing = self._windows.get(key)
        if existing is not None:
            existing.showNormal() if existing.isMinimized() else None
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return existing

        definition = self._definitions.get(key)
        if definition is None:
            raise KeyError(f"Unbekanntes Fenster: {key}")

        content, cleanup = definition.factory()
        window = ManagedToolWindow(
            key=key,
            title=definition.title,
            content=content,
            settings=self._settings,
            cleanup=cleanup,
        )
        window.closing.connect(self._on_window_closing)
        self._windows[key] = window
        self._remember_open_windows()
        window.show()
        window.raise_()
        window.activateWindow()
        self.window_opened.emit(key)
        return window

    def close(self, key: str) -> None:
        window = self._windows.get(key)
        if window is not None:
            window.close()

    def restore_workspace(self) -> None:
        keys = self._settings.value("workspace/open_windows", [], type=list)
        for key in keys:
            if key in self._definitions:
                self.open(str(key))

    def close_all(self, *, preserve_workspace: bool = False) -> None:
        if preserve_workspace:
            self._settings.setValue("workspace/open_windows", sorted(self._windows))
            self._settings.sync()
            self._shutting_down = True
        for window in list(self._windows.values()):
            window.close()

    def refresh_all(self) -> None:
        for window in list(self._windows.values()):
            window._refresh_content()

    def _on_window_closing(self, key: str) -> None:
        self._windows.pop(key, None)
        if not self._shutting_down:
            self._remember_open_windows()
        self.window_closed.emit(key)

    def _remember_open_windows(self) -> None:
        self._settings.setValue("workspace/open_windows", sorted(self._windows))
        self._settings.sync()

from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog

from api_client import APIClient
from embedded_backend import ensure_local_backend
from runtime_paths import asset_path
from ui.login_window import LoginWindow
from ui.main_window import MainWindow


class DesktopSessionController(QObject):
    def __init__(self, app: QApplication, api_client: APIClient):
        super().__init__()
        self.app = app
        self.api_client = api_client
        self.main_window: MainWindow | None = None

    def start(self) -> int:
        QTimer.singleShot(0, self.show_login)
        return self.app.exec()

    def show_login(self) -> None:
        login_window = LoginWindow(self.api_client)
        if login_window.exec() != QDialog.Accepted:
            self.app.quit()
            return

        self.main_window = MainWindow(self.api_client, login_window.user)
        self.main_window.setAttribute(Qt.WA_DeleteOnClose, True)
        self.main_window.destroyed.connect(self._on_main_window_closed)
        self.main_window.show()

    def _on_main_window_closed(self) -> None:
        self.api_client.clear_session()
        self.main_window = None
        QTimer.singleShot(0, self.show_login)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("CF - Checklist de Frota")
    icon_path = asset_path("app-icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    api_client = APIClient()
    ensure_local_backend(api_client)
    controller = DesktopSessionController(app, api_client)
    return controller.start()


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog

from api_client import APIClient
from embedded_backend import ensure_local_backend
from runtime_paths import asset_path
from ui.login_window import LoginWindow
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CF - Checklist de Frota")
    icon_path = asset_path("app-icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    api_client = APIClient()
    ensure_local_backend(api_client)

    login_window = LoginWindow(api_client)
    if login_window.exec() != QDialog.Accepted:
        return 0

    window = MainWindow(api_client, login_window.user)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

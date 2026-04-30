from __future__ import annotations

import contextlib
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
import uuid
from datetime import datetime, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from werkzeug.serving import make_server


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
WEB_APP_ROOT = PROJECT_ROOT / "web_app"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_PATH = Path(tempfile.gettempdir()) / "checklist_frota_web_mobile_playwright.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["INVENTORY_FILE"] = ""
os.environ["WASH_CONTROL_FILE"] = ""

from app import create_app
from app.extensions import db
from app.models import Checklist, ChecklistItem, User, Vehicle
from playwright.sync_api import expect, sync_playwright


def _free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


class _QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class _StaticServerThread(threading.Thread):
    def __init__(self, directory: Path, host: str, port: int):
        super().__init__(daemon=True)
        handler = partial(_QuietStaticHandler, directory=str(directory))
        self.httpd = ThreadingHTTPServer((host, port), handler)

    def run(self) -> None:
        self.httpd.serve_forever()

    def shutdown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class _BackendServerThread(threading.Thread):
    def __init__(self, app, host: str, port: int):
        super().__init__(daemon=True)
        self.server = make_server(host, port, app, threaded=True)

    def run(self) -> None:
        self.server.serve_forever()

    def shutdown(self) -> None:
        self.server.shutdown()


class WebMobilePlaywrightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.backend_host = "127.0.0.1"
        cls.backend_port = _free_port()
        cls.frontend_port = _free_port()
        cls.backend_url = f"http://{cls.backend_host}:{cls.backend_port}"
        cls.frontend_url = f"http://{cls.backend_host}:{cls.frontend_port}/index.html"

        with cls.app.app_context():
            ChecklistItem.query.delete()
            Checklist.query.delete()
            Vehicle.query.delete()
            db.session.commit()

            admin = User.query.filter_by(login="admin").first()
            assert admin is not None

            suffix = uuid.uuid4().hex[:6].upper()
            vehicle = Vehicle(
                frota=f"E2E-{suffix}",
                tipo="carreta",
                placa=f"TTA-{suffix}",
                ano="2026",
                modelo="CARRETA E2E",
                chassi=f"CHASSI-{suffix}",
                configuracao="PADRAO",
                atividade="OPERACAO",
                status="ON",
                local="PATIO",
                descricao="VEICULO DE TESTE WEB MOBILE",
                ativo=True,
            )
            db.session.add(vehicle)
            db.session.flush()

            for created_at in (
                datetime.utcnow() - timedelta(hours=2),
                datetime.utcnow() - timedelta(days=1, hours=3),
            ):
                checklist = Checklist(
                    vehicle_id=vehicle.id,
                    user_id=admin.id,
                    created_at=created_at,
                )
                db.session.add(checklist)
                db.session.flush()
                db.session.add(
                    ChecklistItem(
                        checklist_id=checklist.id,
                        item_nome="FREIOS",
                        status="OK",
                        created_at=created_at,
                    )
                )

            db.session.commit()
            cls.vehicle_frota = vehicle.frota

        cls.backend_server = _BackendServerThread(cls.app, cls.backend_host, cls.backend_port)
        cls.backend_server.start()

        cls.static_server = _StaticServerThread(WEB_APP_ROOT, cls.backend_host, cls.frontend_port)
        cls.static_server.start()

        time.sleep(0.8)

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.static_server.shutdown()
        cls.backend_server.shutdown()
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()

    def setUp(self):
        self.context = self.browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(15000)

    def tearDown(self):
        self.context.close()

    def _wait_for_screen(self, screen_id: str) -> None:
        self.page.wait_for_function(
            "(id) => !document.getElementById(id).classList.contains('hidden')",
            arg=screen_id,
        )

    def _login(self) -> None:
        self.page.goto(self.frontend_url, wait_until="domcontentloaded")
        self.page.evaluate(
            "(apiUrl) => { document.getElementById('api-base-url').value = apiUrl; localStorage.removeItem('token'); localStorage.removeItem('user'); }",
            self.backend_url,
        )
        self.page.locator("#login").fill("admin")
        self.page.locator("#password").fill("123456")
        self.page.locator("#login-button").click()
        self._wait_for_screen("home-screen")
        expect(self.page.locator("#open-checklist-menu")).to_be_visible()

    def test_admin_can_open_critical_mobile_modules(self):
        self._login()

        self.page.locator("#open-checklist-history-menu").click()
        self._wait_for_screen("checklist-history-screen")
        expect(self.page.locator("#checklist-history-counter")).to_contain_text("FROTAS")
        expect(self.page.locator("#checklist-history-table-wrap")).to_contain_text(self.vehicle_frota)

        self.page.locator("#checklist-history-back-button").click()
        self._wait_for_screen("home-screen")

        self.page.locator("#open-activities-menu").click()
        self._wait_for_screen("activities-screen")
        expect(self.page.locator("#activity-counter")).not_to_have_text("FALHA")

        self.page.locator("#activities-back-button").click()
        self._wait_for_screen("home-screen")

        self.page.locator("#open-washes-menu").click()
        self._wait_for_screen("washes-screen")
        expect(self.page.locator("#wash-counter")).not_to_have_text("FALHA")
        expect(self.page.locator("#wash-calendar")).to_be_visible()

        self.page.locator("#washes-back-button").click()
        self._wait_for_screen("home-screen")

        self.page.locator("#open-non-conformities-menu").click()
        self._wait_for_screen("non-conformities-screen")
        expect(self.page.locator("#non-conformities-counter")).not_to_have_text("FALHA")

        self.page.locator("#non-conformities-back-button").click()
        self._wait_for_screen("home-screen")

        self.page.locator("#open-maintenance-menu").click()
        self._wait_for_screen("maintenance-screen")
        expect(self.page.locator("#maintenance-counter")).not_to_have_text("FALHA")
        expect(self.page.locator("#maintenance-calendar")).to_be_visible()

    def test_checklist_flow_updates_progress_and_blocks_incomplete_submit(self):
        self._login()

        self.page.locator("#open-checklist-menu").click()
        self._wait_for_screen("vehicles-screen")
        expect(self.page.locator("#vehicles-list")).to_contain_text(self.vehicle_frota)

        self.page.locator("#vehicles-list .vehicle-card").first.click()
        self._wait_for_screen("checklist-screen")
        expect(self.page.locator("#checklist-progress")).to_contain_text("0 DE")

        first_ok_button = self.page.locator(".checklist-item-card .status-button.ok").first
        first_ok_button.click()
        expect(self.page.locator("#checklist-progress")).to_contain_text("1 DE")

        self.page.locator("#submit-checklist").click()
        expect(self.page.locator("#toast")).to_be_visible()
        expect(self.page.locator("#toast")).to_contain_text("SELECIONE OK OU NAO CONFORMIDADE")
        self._wait_for_screen("checklist-screen")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import base64
import contextlib
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
import uuid
from datetime import timedelta
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
os.environ["INVENTORY_FILE"] = str(Path(tempfile.gettempdir()) / "checklist_frota_no_inventory.xlsx")
os.environ["WASH_CONTROL_FILE"] = str(Path(tempfile.gettempdir()) / "checklist_frota_no_wash.xlsx")

from app import create_app
from app.extensions import db
from app.models import (
    Checklist, ChecklistItem, EquipmentFamily, EquipmentOperationalState,
    EquipmentProfile, EquipmentStatusEvent, HourmeterReading, User, Vehicle,
    InspectionExecution, InspectionExecutionItem, InspectionTemplate, InspectionTemplateItem,
)
from app.utils.timezone import now_manaus_naive
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
        # The backend intentionally permits the local Web origin on port 5500.
        cls.frontend_port = 5500
        cls.backend_url = f"http://{cls.backend_host}:{cls.backend_port}"
        cls.frontend_url = f"http://{cls.backend_host}:{cls.frontend_port}/index.html"

        with cls.app.app_context():
            ChecklistItem.query.delete()
            Checklist.query.delete()
            HourmeterReading.query.delete()
            EquipmentStatusEvent.query.delete()
            EquipmentOperationalState.query.delete()
            InspectionExecutionItem.query.delete()
            InspectionExecution.query.delete()
            InspectionTemplateItem.query.delete()
            InspectionTemplate.query.delete()
            EquipmentProfile.query.delete()
            Vehicle.query.delete()
            db.session.commit()

            admin = User.query.filter_by(login="admin").first()
            if not admin:
                admin = User(nome="Administrador Teste", login="admin", tipo="admin", ativo=True)
                admin.set_password("teste123")
                db.session.add(admin)
                db.session.flush()
            admin.set_password("123456")

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
            family = EquipmentFamily.query.filter_by(code="carreta").one()
            db.session.add(EquipmentProfile(vehicle_id=vehicle.id, family_id=family.id))
            db.session.add(EquipmentOperationalState(vehicle_id=vehicle.id))
            template = InspectionTemplate(
                family_id=family.id, code="E2E-DIARIA", name="Inspeção diária E2E",
                version=1, status="PUBLICADO", created_by_user_id=admin.id,
                published_at=now_manaus_naive(),
            )
            template.items = [InspectionTemplateItem(
                category="Segurança", label="Freio de serviço", position=1,
                response_type="STATUS", required=True, evidence_on_nc=True,
            )]
            db.session.add(template)

            for created_at in (
                now_manaus_naive() - timedelta(hours=2),
                now_manaus_naive() - timedelta(days=1, hours=3),
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
        self.test_image_path = Path(tempfile.gettempdir()) / "checklist_frota_e2e_camera.jpg"
        self.test_image_path.write_bytes(
            base64.b64decode(
                "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBAQEA8QDw8QDw8PDw8PDw8QDxAQFREWFhURFRUYHSggGBolGxUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OGxAQGy0lHyUtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAQMBEQACEQEDEQH/xAAXAAADAQAAAAAAAAAAAAAAAAAAAQMC/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEAMQAAAB6A//xAAXEAEAAwAAAAAAAAAAAAAAAAABABEh/9oACAEBAAEFAmrf/8QAFBEBAAAAAAAAAAAAAAAAAAAAEP/aAAgBAwEBPwEf/8QAFBEBAAAAAAAAAAAAAAAAAAAAEP/aAAgBAgEBPwEf/8QAFxABAQEBAAAAAAAAAAAAAAAAAREAITFBcf/aAAgBAQAGPwJ1Tj//xAAXEAADAQAAAAAAAAAAAAAAAAABESEx/9oACAEBAAE/IaYw1//aAAwDAQACAAMAAAAQPw//xAAVEQEBAAAAAAAAAAAAAAAAAAABEP/aAAgBAwEBPxBf/8QAFREBAQAAAAAAAAAAAAAAAAAAARD/2gAIAQIBAT8QX//EABgQAQEBAQEAAAAAAAAAAAAAAAERACEx/9oACAEBAAE/EFJpC8R8n//Z"
            )
        )

    def tearDown(self):
        self.context.close()
        if self.test_image_path.exists():
            self.test_image_path.unlink()

    def _wait_for_screen(self, screen_id: str) -> None:
        self.page.wait_for_function(
            "(id) => !document.getElementById(id).classList.contains('hidden')",
            arg=screen_id,
        )

    def _login(self) -> None:
        self.page.goto(self.frontend_url, wait_until="domcontentloaded")
        self.assertEqual(self.page.evaluate("() => window.CHECKLIST_TIME_ZONE"), "America/Manaus")
        self.page.evaluate(
            "(apiUrl) => { document.getElementById('api-base-url').value = apiUrl; localStorage.removeItem('token'); localStorage.removeItem('user'); }",
            self.backend_url,
        )
        self.page.locator("#login").fill("admin")
        self.page.locator("#password").fill("123456")
        self.page.locator("#login-button").tap()
        self._wait_for_screen("home-screen")
        expect(self.page.locator("#open-checklist-menu")).to_be_visible()

    def test_primary_and_dashboard_layouts_do_not_overflow_common_viewports(self):
        pages = [
            self.frontend_url,
            f"http://{self.backend_host}:{self.frontend_port}/dashboard-manutencao/",
        ]
        viewports = [
            {"width": 390, "height": 844},
            {"width": 768, "height": 1024},
            {"width": 1366, "height": 768},
            {"width": 1920, "height": 1080},
        ]
        for viewport in viewports:
            self.page.set_viewport_size(viewport)
            for page_url in pages:
                self.page.goto(page_url, wait_until="domcontentloaded")
                overflow = self.page.evaluate(
                    "() => document.documentElement.scrollWidth > window.innerWidth + 1"
                )
                self.assertFalse(overflow, f"Overflow horizontal em {viewport} para {page_url}")

    def test_web_mobile_adapts_home_layout_to_phone_tablet_and_desktop(self):
        self._login()
        device_layouts = [
            ({"width": 390, "height": 844}, 1),
            ({"width": 768, "height": 1024}, 2),
            ({"width": 1366, "height": 768}, 4),
            ({"width": 1920, "height": 1080}, 4),
        ]
        for viewport, expected_columns in device_layouts:
            with self.subTest(viewport=viewport):
                self.page.set_viewport_size(viewport)
                layout = self.page.evaluate(
                    """() => {
                        const shell = document.querySelector('.mobile-shell').getBoundingClientRect();
                        const menu = getComputedStyle(document.querySelector('.menu-grid'));
                        return {
                            shellWidth: shell.width,
                            viewportWidth: window.innerWidth,
                            menuColumns: menu.gridTemplateColumns.split(' ').filter(Boolean).length,
                        };
                    }"""
                )
                self.assertGreaterEqual(layout["shellWidth"], layout["viewportWidth"] - 1)
                self.assertEqual(layout["menuColumns"], expected_columns)

    def test_admin_can_open_critical_mobile_modules(self):
        self._login()

        scroll_probe = self.page.evaluate(
            """() => {
                const root = document.querySelector(".mobile-shell");
                const before = root.scrollTop;
                root.scrollTo({ top: 480, behavior: "auto" });
                return {
                    before,
                    after: root.scrollTop,
                    scrollHeight: root.scrollHeight,
                    clientHeight: root.clientHeight,
                };
            }"""
        )
        self.assertGreater(scroll_probe["scrollHeight"], scroll_probe["clientHeight"])
        self.assertGreater(scroll_probe["after"], scroll_probe["before"])

        self.page.locator("#open-checklist-history-menu").tap()
        self._wait_for_screen("checklist-history-screen")
        expect(self.page.locator("#checklist-history-counter")).to_contain_text("FROTAS")
        expect(self.page.locator("#checklist-history-table-wrap")).to_contain_text(self.vehicle_frota)
        expect(self.page.locator("#checklist-history-apply-filter")).to_have_count(0)
        self.page.locator("#checklist-history-equipment-search").fill("sem resultado")
        expect(self.page.locator("#checklist-history-counter")).to_contain_text("0 FROTAS")
        self.page.locator("#checklist-history-equipment-search").fill(self.vehicle_frota)
        expect(self.page.locator("#checklist-history-counter")).to_contain_text("1 FROTAS")
        self.page.locator(".history-frota-header").tap()
        expect(self.page.locator(".history-frota-header")).to_contain_text("▼")

        self.page.locator("#checklist-history-back-button").tap()
        self._wait_for_screen("home-screen")

        self.page.locator("#open-activities-menu").tap()
        self._wait_for_screen("activities-screen")
        expect(self.page.locator("#activity-counter")).not_to_have_text("FALHA")

        self.page.locator("#activities-back-button").tap()
        self._wait_for_screen("home-screen")

        self.page.locator("#open-washes-menu").tap()
        self._wait_for_screen("washes-screen")
        expect(self.page.locator("#wash-counter")).not_to_have_text("FALHA")
        expect(self.page.locator("#wash-calendar")).to_be_visible()

        self.page.locator("#washes-back-button").tap()
        self._wait_for_screen("home-screen")

        self.page.locator("#open-non-conformities-menu").tap()
        self._wait_for_screen("non-conformities-screen")
        expect(self.page.locator("#non-conformities-counter")).not_to_have_text("FALHA")

        self.page.locator("#non-conformities-back-button").tap()
        self._wait_for_screen("home-screen")

        self.page.locator("#open-maintenance-menu").tap()
        self._wait_for_screen("maintenance-screen")
        expect(self.page.locator("#maintenance-counter")).not_to_have_text("FALHA")
        expect(self.page.locator("#maintenance-calendar")).to_be_visible()

        self.page.locator("#maintenance-back-button").tap()
        self._wait_for_screen("home-screen")

        self.page.locator("#open-availability-menu").tap()
        self._wait_for_screen("availability-screen")
        expect(self.page.locator("#availability-counter")).to_contain_text("1 EQUIPAMENTO")
        card = self.page.locator(".availability-card")
        expect(card).to_contain_text(self.vehicle_frota)
        card.locator(".availability-status").select_option("DISPONIVEL")
        card.locator(".availability-status-save").tap()
        expect(self.page.locator(".availability-card header b")).to_have_text("DISPONÍVEL")
        self.page.locator(".availability-hourmeter").fill("1250.50")
        self.page.locator(".availability-hourmeter-save").tap()
        expect(self.page.locator(".availability-reading strong")).to_contain_text("1250.50 h")

        self.page.locator("#availability-back-button").tap()
        self._wait_for_screen("home-screen")
        self.page.locator("#open-technical-inspections-menu").tap()
        self._wait_for_screen("technical-inspections-screen")
        expect(self.page.locator(".technical-inspection-item")).to_have_count(1)
        self.page.locator(".technical-response").select_option("OK")
        self.page.locator("#technical-inspection-submit").tap()
        self._wait_for_screen("home-screen")

    def test_technical_inspection_queues_offline_and_syncs_when_online(self):
        self._login()
        self.page.locator("#open-technical-inspections-menu").tap()
        self._wait_for_screen("technical-inspections-screen")
        expect(self.page.locator(".technical-inspection-item")).to_have_count(1)
        self.context.set_offline(True)
        self.page.locator(".technical-response").select_option("OK")
        self.page.locator("#technical-inspection-submit").tap()
        self._wait_for_screen("home-screen")
        queued = self.page.evaluate("""async () => {
            const db = await openOfflineDb();
            return await new Promise((resolve, reject) => {
                const request = db.transaction(INSPECTION_QUEUE_STORE, 'readonly').objectStore(INSPECTION_QUEUE_STORE).count();
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
        }""")
        self.assertEqual(queued, 1)
        self.context.set_offline(False)
        self.page.wait_for_function("""async () => {
            const db = await openOfflineDb();
            return await new Promise((resolve) => {
                const request = db.transaction(INSPECTION_QUEUE_STORE, 'readonly').objectStore(INSPECTION_QUEUE_STORE).count();
                request.onsuccess = () => resolve(request.result === 0);
                request.onerror = () => resolve(false);
            });
        }""", timeout=15000)

    def test_session_requires_login_after_30_minutes_without_activity(self):
        self._login()

        self.page.evaluate(
            """() => {
                localStorage.setItem("sessionLastActivityAt", String(Date.now() - (31 * 60 * 1000)));
            }"""
        )
        self.page.reload(wait_until="domcontentloaded")
        self._wait_for_screen("login-screen")

        expect(self.page.locator("#login-status")).to_contain_text("30 minutos de inatividade")
        self.assertFalse(self.page.evaluate("""() => Boolean(localStorage.getItem("token"))"""))

    def test_checklist_flow_updates_progress_and_blocks_incomplete_submit(self):
        self._login()

        self.page.locator("#open-checklist-menu").tap()
        self._wait_for_screen("vehicles-screen")
        expect(self.page.locator("#vehicles-list")).to_contain_text(self.vehicle_frota)

        self.page.locator("#vehicles-list .vehicle-card").first.tap()
        self._wait_for_screen("checklist-screen")
        expect(self.page.locator("#checklist-progress")).to_contain_text("0 DE")

        first_card = self.page.locator(".checklist-item-card").first
        first_card.locator(".status-button.nc").tap()
        first_card.locator("textarea").fill("LENTE TRINCADA NA INSPEÇÃO E2E")
        expect(first_card.locator(".camera-trigger")).to_contain_text("CÂMERA")
        expect(first_card).not_to_contain_text("Escolher arquivo")
        first_card.locator("input[type='file']").set_input_files(str(self.test_image_path))
        expect(first_card.locator("em.ok")).to_contain_text("EVIDÊNCIA ANEXADA")
        expect(first_card).not_to_contain_text(self.test_image_path.name)
        preview = first_card.locator(".photo-preview")
        expect(preview).to_be_visible()
        preview.tap()
        expect(self.page.locator("#photo-viewer-modal")).to_be_visible()
        self.assertTrue(self.page.locator("#photo-viewer-image").get_attribute("src"))
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#photo-viewer-modal")).to_be_hidden()
        expect(self.page.locator("#checklist-progress")).to_contain_text("1 DE")

        self.page.locator("#submit-checklist").tap()
        expect(self.page.locator("#toast")).to_be_visible()
        expect(self.page.locator("#toast")).to_contain_text("SELECIONE OK OU NÃO CONFORMIDADE")
        self._wait_for_screen("checklist-screen")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = PROJECT_ROOT / "desktop"
WEB_ROOT = PROJECT_ROOT / "web_app"
OUTPUT_PDF = PROJECT_ROOT / "MANUAL_FLUXO_NAO_CONFORMIDADE.pdf"
OUTPUT_MD = DESKTOP_ROOT / "docs" / "MANUAL_FLUXO_NAO_CONFORMIDADE.md"
ASSET_DIR = DESKTOP_ROOT / "docs" / "manual_assets"


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _wait_for_port(host: str, port: int, timeout_seconds: float = 15.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError(f"Servidor local não respondeu em {host}:{port}.")


class ManualFakeAPIClient:
    def __init__(self):
        self.user = {"id": 1, "nome": "Administrador", "tipo": "admin", "login": "admin"}
        self.login_started_at = None

        self.non_conformities = [
            {
                "id": 101,
                "item_nome": "Lanterna traseira",
                "item_principal": "Lanterna traseira",
                "created_at": "2026-05-10T08:14:00",
                "resolvido": False,
                "codigo_peca": "",
                "foto_antes": "/uploads/nc_101_antes.jpg",
                "foto_depois": None,
                "usuario": {"id": 31, "nome": "Motorista João", "login": "joao"},
                "veiculo": {"id": 11, "frota": "CV801", "placa": "TAA-1001", "tipo": "cavalo"},
                "resolution_package": {},
            },
            {
                "id": 102,
                "item_nome": "Lanterna traseira",
                "item_principal": "Lanterna traseira",
                "created_at": "2026-05-10T08:18:00",
                "resolvido": False,
                "codigo_peca": "",
                "foto_antes": "/uploads/nc_102_antes.jpg",
                "foto_depois": None,
                "usuario": {"id": 32, "nome": "Motorista Ana", "login": "ana"},
                "veiculo": {"id": 12, "frota": "CV802", "placa": "TAA-1002", "tipo": "cavalo"},
                "resolution_package": {},
            },
            {
                "id": 103,
                "item_nome": "Paralama direito",
                "item_principal": "Paralama direito",
                "created_at": "2026-05-09T17:32:00",
                "resolvido": False,
                "codigo_peca": "",
                "foto_antes": "/uploads/nc_103_antes.jpg",
                "foto_depois": None,
                "usuario": {"id": 33, "nome": "Motorista Carlos", "login": "carlos"},
                "veiculo": {"id": 11, "frota": "CV801", "placa": "TAA-1001", "tipo": "cavalo"},
                "resolution_package": {
                    "id": 8801,
                    "critical_recurrence": True,
                },
            },
        ]

        self.packages = [
            {
                "id": 8801,
                "title": "Pacote por equipamento - CV801",
                "grouping_mode": "POR_EQUIPAMENTO",
                "reference_label": "CV801",
                "status": "EM_MANUTENCAO",
                "priority_score": 19,
                "recurrence_hits": 4,
                "critical_recurrence": True,
                "resumo": {"abertas": 2, "resolvidas": 0},
            },
            {
                "id": 8802,
                "title": "Pacote por item - LANTERNA TRASEIRA",
                "grouping_mode": "POR_ITEM",
                "reference_label": "LANTERNA TRASEIRA",
                "status": "ABERTO",
                "priority_score": 13,
                "recurrence_hits": 2,
                "critical_recurrence": False,
                "resumo": {"abertas": 2, "resolvidas": 0},
            },
        ]

        self.mechanics = [
            {"id": 4, "nome": "Mecânico Paulo", "login": "paulo", "tipo": "mecanico", "ativo": True},
            {"id": 5, "nome": "Mecânico Davi", "login": "davi", "tipo": "mecanico", "ativo": True},
        ]

        self.materials = [
            {"id": 41, "referencia": "LT-24V", "descricao": "Lanterna traseira 24V", "quantidade_estoque": 12},
            {"id": 42, "referencia": "PR-DIR", "descricao": "Paralama direito", "quantidade_estoque": 1},
        ]

        self.equipment = [
            {"id": 11, "frota": "CV801", "placa": "TAA-1001", "modelo": "Actros", "tipo": "cavalo"},
            {"id": 12, "frota": "CV802", "placa": "TAA-1002", "modelo": "Actros", "tipo": "cavalo"},
            {"id": 21, "frota": "CR901", "placa": "TBB-2001", "modelo": "Randon", "tipo": "carreta"},
        ]

        self.maintenance_schedule = {
            "id": 710,
            "title": "Programação corretiva - Pacote 8801",
            "source_type": "PACOTE_RESOLUCAO",
            "source_origin_type": "PACOTE_RESOLUCAO",
            "status": "PROGRAMADA",
            "start_date": "2026-05-11",
            "end_date": "2026-05-12",
            "daily_capacity": 2,
            "assigned_mechanic_user_id": 4,
            "package_reference_label": "Pacote #8801 - CV801",
            "vehicle_family": "cavalo",
            "resumo": {"total": 2, "pendentes": 1, "instalados": 1},
            "materiais_resumo": {"total": 1, "reservados": 1},
            "bloqueios_resumo": {"materiais_bloqueados": 1, "os_bloqueadas": 1},
            "materiais": [
                {
                    "id": 9001,
                    "material_id": 41,
                    "quantity_per_vehicle": 1,
                    "quantity_required": 2,
                    "quantity_reserved": 1,
                    "status": "RESERVADO",
                    "observation": "Peça principal do pacote.",
                    "material": self.materials[0],
                }
            ],
            "itens": [
                {
                    "id": 501,
                    "vehicle": self.equipment[0],
                    "source_type": "PACOTE_RESOLUCAO",
                    "source_label": "Pacote",
                    "item_name": "Lanterna traseira",
                    "scheduled_date": "2026-05-11",
                    "status": "PROGRAMADO",
                    "execution_label": "Aguardando execução",
                    "observation": "Trocar e fotografar depois.",
                    "work_order": {"id": 3001, "order_number": "OS-003001"},
                },
                {
                    "id": 502,
                    "vehicle": self.equipment[1],
                    "source_type": "PACOTE_RESOLUCAO",
                    "source_label": "Pacote",
                    "item_name": "Lanterna traseira",
                    "scheduled_date": "2026-05-11",
                    "status": "AGUARDANDO_MATERIAL",
                    "execution_label": "Bloqueado por peça",
                    "observation": "Aguardando completar reserva.",
                    "work_order": {"id": 3002, "order_number": "OS-003002"},
                },
            ],
        }

    def get_dashboard(self):
        return {
            "total_nc": 3,
            "nc_abertas": 3,
            "veiculos_com_falha": 2,
            "itens_criticos": [{"item_nome": "Lanterna traseira", "total_nc": 2, "abertas": 2, "resolvidas": 0}],
        }

    def get_productivity_report(self):
        return {"resumo": {}, "usuarios": []}

    def get_macro_report(self):
        return []

    def get_micro_report(self):
        return []

    def get_item_report(self, *args, **kwargs):
        return []

    def get_checklist_history_matrix(self, *args, **kwargs):
        return {"columns": [], "rows": [], "periodo": {}}

    def get_users(self):
        return [self.user]

    def get_activities(self, **_kwargs):
        return []

    def get_non_conformities(self, **_kwargs):
        return list(self.non_conformities)

    def get_mechanic_non_conformities(self, status=None):
        rows = [
            {
                "id": 401,
                "veiculo_referencia": "CV801",
                "item_nome": "Vazamento no eixo",
                "resolvido": False,
                "created_by": {"nome": "Mecânico Paulo"},
                "resolved_by": {},
                "created_at": "2026-05-09T10:00:00",
                "data_resolucao": None,
                "codigo_peca": "",
            }
        ]
        if status == "resolvidas":
            return []
        return rows

    def get_resolution_packages(self, status=None):
        if status:
            return [row for row in self.packages if str(row.get("status") or "").upper() == str(status).upper()]
        return list(self.packages)

    def get_resolution_package_suggestions(self, _checklist_item_ids):
        return {
            "suggestions": [
                {
                    "id": 8802,
                    "reason": "MESMO_ITEM",
                    "reason_label": "Mesmo item distinto já em pacote aberto",
                }
            ]
        }

    def get_intelligent_rules(self):
        return {
            "rules": {
                "recurrence_window_days": 15,
                "recurrence_weight": 5,
            }
        }

    def get_maintenance_overview(self, **_kwargs):
        return {
            "resumo": {
                "programacoes": 1,
                "itens": 2,
                "pendentes": 1,
                "instalados": 1,
                "aguardando_material": 1,
                "os_bloqueadas": 1,
                "nao_executados": 0,
            },
            "programacoes": [self.maintenance_schedule],
            "cronograma": {
                "days": [
                    {
                        "date": "2026-05-11",
                        "total": 2,
                        "pendentes": 1,
                        "instalados": 1,
                        "nao_executados": 0,
                        "aguardando_material": 1,
                    }
                ]
            },
            "bloqueios": [
                {
                    "type": "Material bloqueando",
                    "reference": "OS-003002",
                    "quantity": 1,
                    "reading": "Lanterna traseira reservada parcialmente; falta completar a peça para liberar execução.",
                    "critical": True,
                }
            ],
        }

    def get_mechanics(self):
        return list(self.mechanics)

    def get_materials(self, **_kwargs):
        return list(self.materials)

    def get_equipment(self, **_kwargs):
        return list(self.equipment)

    def get_maintenance_mechanic_suggestion(self, _payload):
        return {
            "user_id": 4,
            "user": self.mechanics[0],
            "reason": "Histórico mais frequente para lanterna traseira em cavalo.",
        }

    def get_maintenance_schedule_suggestion(self, payload):
        user_id = payload.get("assigned_mechanic_user_id") or 4
        user = next((row for row in self.mechanics if row["id"] == user_id), self.mechanics[0])
        total_items = payload.get("selected_total") or 2
        return {
            "suggested_start_date": "2026-05-11",
            "suggested_end_date": "2026-05-12",
            "total_items": total_items,
            "reason": "Janela livre considerando capacidade diária e carga do mecânico.",
            "mechanic_load": {
                "user_id": user["id"],
                "user": user,
                "open_work_orders": 3,
                "overdue_work_orders": 1,
                "scheduled_in_window": 2,
            },
        }

    def get_maintenance_material_suggestion(self, _schedule_id):
        return {
            "material": self.materials[0],
            "quantity_per_vehicle": 1,
            "status": "RESERVADO",
            "reason": "Peça mais usada para lanterna traseira em cavalo.",
        }

    def create_maintenance_schedule(self, payload):
        return {"id": 711, **payload}

    def fetch_image(self, _relative_path):
        return None


def capture_desktop_screenshots() -> dict[str, Path]:
    os.environ["QT_QPA_PLATFORM"] = "windows"
    _safe_mkdir(ASSET_DIR)

    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(DESKTOP_ROOT))

    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from api_client import APIClient
    from ui.login_window import LoginWindow
    from ui.main_window import MainWindow
    from ui.maintenance_page import MaintenanceScheduleCreateDialog
    from ui.non_conformities_page import CreateResolutionPackageDialog

    app = QApplication.instance() or QApplication([])
    fake_api = ManualFakeAPIClient()

    login_path = ASSET_DIR / "manual_nc_desktop_login.png"
    central_path = ASSET_DIR / "manual_nc_desktop_central.png"
    package_dialog_path = ASSET_DIR / "manual_nc_desktop_package_dialog.png"
    maintenance_path = ASSET_DIR / "manual_nc_desktop_maintenance.png"
    schedule_dialog_path = ASSET_DIR / "manual_nc_desktop_schedule_dialog.png"

    login_window = LoginWindow(APIClient())
    login_window.login_input.setText("admin")
    login_window.password_input.setText("123456")
    login_window.show()
    QTest.qWait(250)
    app.processEvents()
    login_window.grab().save(str(login_path))
    login_window.close()

    central_window = MainWindow(fake_api, fake_api.user)
    central_window.resize(1460, 920)
    central_window.showNormal()
    QTest.qWait(450)
    app.processEvents()
    central_window.switch_page("nc")
    QTest.qWait(700)
    app.processEvents()
    central_window.grab().save(str(central_path))

    selected_items = fake_api.non_conformities[:2]
    package_dialog = CreateResolutionPackageDialog(fake_api, selected_items, central_window)
    package_dialog.show()
    QTest.qWait(250)
    app.processEvents()
    package_dialog.grab().save(str(package_dialog_path))
    package_dialog.close()
    central_window.close()

    maintenance_window = MainWindow(fake_api, fake_api.user)
    maintenance_window.resize(1460, 940)
    maintenance_window.showNormal()
    QTest.qWait(450)
    app.processEvents()
    maintenance_window.switch_page("maintenance")
    QTest.qWait(850)
    app.processEvents()
    maintenance_window.grab().save(str(maintenance_path))

    schedule_dialog = MaintenanceScheduleCreateDialog(fake_api, maintenance_window)
    schedule_dialog.show()
    QTest.qWait(250)
    app.processEvents()
    schedule_dialog._format_date = lambda value: str(value or "-")[8:10] + "/" + str(value or "-")[5:7] + "/" + str(value or "-")[:4] if value and len(str(value)) >= 10 else "-"
    if schedule_dialog.source_table.rowCount() > 0:
        schedule_dialog.source_table.selectRow(0)
        schedule_dialog._update_selection_summary()
        QTest.qWait(200)
        app.processEvents()
    schedule_dialog.grab().save(str(schedule_dialog_path))
    schedule_dialog.close()
    maintenance_window.close()

    app.processEvents()
    return {
        "desktop_login": login_path,
        "desktop_central": central_path,
        "desktop_package_dialog": package_dialog_path,
        "desktop_maintenance": maintenance_path,
        "desktop_schedule_dialog": schedule_dialog_path,
    }


def capture_web_mobile_screenshots() -> dict[str, Path]:
    _safe_mkdir(ASSET_DIR)
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8766", "--bind", "127.0.0.1"],
        cwd=WEB_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    login_path = ASSET_DIR / "manual_nc_web_login.png"
    checklist_path = ASSET_DIR / "manual_nc_web_checklist.png"
    central_path = ASSET_DIR / "manual_nc_web_central.png"
    maintenance_path = ASSET_DIR / "manual_nc_web_maintenance.png"

    try:
        _wait_for_port("127.0.0.1", 8766)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(
                viewport={"width": 390, "height": 844},
                device_scale_factor=1,
                is_mobile=True,
            )
            page.goto("http://127.0.0.1:8766/index.html", wait_until="networkidle")
            page.screenshot(path=str(login_path), full_page=True)

            page.evaluate(
                """
                () => {
                    const showOnly = (id) => {
                        document.querySelectorAll('.screen').forEach((screen) => {
                            screen.classList.add('hidden');
                            screen.classList.remove('active');
                        });
                        const target = document.getElementById(id);
                        if (target) {
                            target.classList.remove('hidden');
                            target.classList.add('active');
                        }
                    };

                    showOnly('checklist-screen');
                    document.getElementById('checklist-title').textContent = 'CHECKLIST - CV801';
                    document.getElementById('checklist-subtitle').textContent = 'ITEM EM ABERTURA DE NÃO CONFORMIDADE';
                    document.getElementById('checklist-progress').textContent = '12 DE 19 ITENS AVALIADOS';
                    document.getElementById('checklist-screen').insertAdjacentHTML('beforeend', `
                        <div class="checklist-card checklist-card-highlight" style="margin-top:12px;">
                            <div class="checklist-card-header">
                                <strong>LANTERNA TRASEIRA</strong>
                                <span class="status-chip status-chip-danger">NÃO CONFORME</span>
                            </div>
                            <p style="margin:8px 0 12px 0;">Motorista marca o item como não conforme, escreve a observação e anexa a foto antes.</p>
                            <label class="search-box" style="margin-bottom:10px;">
                                <span>OBSERVAÇÃO</span>
                                <textarea style="min-height:84px;">Lanterna traseira sem funcionamento no lado direito.</textarea>
                            </label>
                            <div class="summary-card" style="padding:12px;">
                                <strong>FOTO ANTES</strong>
                                <span>Evidência anexada e pronta para envio.</span>
                            </div>
                            <button class="primary-button" type="button" style="margin-top:12px;">ENVIAR CHECKLIST COM NÃO CONFORMIDADE</button>
                        </div>
                    `);
                }
                """
            )
            page.screenshot(path=str(checklist_path), full_page=True)

            page.evaluate(
                """
                () => {
                    const showOnly = (id) => {
                        document.querySelectorAll('.screen').forEach((screen) => {
                            screen.classList.add('hidden');
                            screen.classList.remove('active');
                        });
                        const target = document.getElementById(id);
                        if (target) {
                            target.classList.remove('hidden');
                            target.classList.add('active');
                        }
                    };

                    showOnly('non-conformities-screen');
                    document.getElementById('non-conformities-summary').innerHTML = `
                        <div class="summary-grid">
                            <div class="summary-item"><span>ABERTAS</span><strong>3</strong></div>
                            <div class="summary-item"><span>EM PACOTE</span><strong>2</strong></div>
                            <div class="summary-item"><span>EM MANUTENÇÃO</span><strong>1</strong></div>
                            <div class="summary-item"><span>CRÍTICAS</span><strong>1</strong></div>
                        </div>
                    `;
                    document.getElementById('non-conformities-counter').textContent = '3 ABERTAS';
                    document.getElementById('non-conformities-macro-counter').textContent = '2 ITENS';
                    document.getElementById('non-conformities-macro-list').innerHTML = `
                        <article class="menu-card">
                            <span>ITEM</span>
                            <strong>LANTERNA TRASEIRA</strong>
                            <em>2 veículos aguardando triagem por item distinto.</em>
                        </article>
                    `;
                    document.getElementById('non-conformities-micro-list').innerHTML = `
                        <article class="menu-card">
                            <span>EQUIPAMENTO</span>
                            <strong>CV801</strong>
                            <em>2 não conformidades já agrupadas no pacote #8801.</em>
                        </article>
                    `;
                    document.getElementById('non-conformities-checklist-counter').textContent = '2 REGISTROS';
                    document.getElementById('non-conformities-checklist-list').innerHTML = `
                        <article class="checklist-card">
                            <div class="checklist-card-header">
                                <strong>CV801 • LANTERNA TRASEIRA</strong>
                                <span class="status-chip status-chip-danger">ABERTA</span>
                            </div>
                            <p>Observação: lanterna sem funcionamento.</p>
                            <small>Fluxo: Central -> Pacote -> Manutenção</small>
                        </article>
                        <article class="checklist-card">
                            <div class="checklist-card-header">
                                <strong>CV802 • LANTERNA TRASEIRA</strong>
                                <span class="status-chip status-chip-warning">EM PACOTE</span>
                            </div>
                            <p>Pacote sugerido por item distinto.</p>
                            <small>Pacote #8802 aguardando envio para manutenção.</small>
                        </article>
                    `;
                    document.getElementById('non-conformities-mechanic-counter').textContent = '1 REGISTRO';
                    document.getElementById('non-conformities-mechanic-list').innerHTML = `
                        <article class="checklist-card">
                            <div class="checklist-card-header">
                                <strong>CV801 • VAZAMENTO NO EIXO</strong>
                                <span class="status-chip status-chip-danger">ABERTA</span>
                            </div>
                            <p>Não conformidade interna aberta pelo mecânico.</p>
                        </article>
                    `;
                }
                """
            )
            page.screenshot(path=str(central_path), full_page=True)

            page.evaluate(
                """
                () => {
                    const showOnly = (id) => {
                        document.querySelectorAll('.screen').forEach((screen) => {
                            screen.classList.add('hidden');
                            screen.classList.remove('active');
                        });
                        const target = document.getElementById(id);
                        if (target) {
                            target.classList.remove('hidden');
                            target.classList.add('active');
                        }
                    };

                    showOnly('maintenance-screen');
                    document.getElementById('maintenance-counter').textContent = '2 SERVIÇOS';
                    document.getElementById('maintenance-summary').innerHTML = `
                        <div class="summary-grid">
                            <div class="summary-item"><span>OS ABERTAS</span><strong>2</strong></div>
                            <div class="summary-item"><span>ATRASADAS</span><strong>1</strong></div>
                            <div class="summary-item"><span>BLOQUEADAS</span><strong>1</strong></div>
                            <div class="summary-item"><span>CONCLUÍDAS</span><strong>0</strong></div>
                        </div>
                    `;
                    document.getElementById('maintenance-day-panel').innerHTML = `
                        <div class="summary-card">
                            <strong>11/05/2026</strong>
                            <span>Pacote #8801 | Mecânico Paulo | 2 serviços no dia</span>
                        </div>
                    `;
                    document.getElementById('maintenance-list').innerHTML = `
                        <article class="menu-card">
                            <span>OS-003001</span>
                            <strong>CV801 • LANTERNA TRASEIRA</strong>
                            <em>Status: PROGRAMADO | Peça: LT-24V | Botões: Exportar PDF / Concluir</em>
                        </article>
                        <article class="menu-card">
                            <span>OS-003002</span>
                            <strong>CV802 • LANTERNA TRASEIRA</strong>
                            <em>Status: AGUARDANDO MATERIAL | Bloqueio de peça visível ao mecânico.</em>
                        </article>
                    `;
                }
                """
            )
            page.screenshot(path=str(maintenance_path), full_page=True)
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()

    return {
        "web_login": login_path,
        "web_checklist": checklist_path,
        "web_central": central_path,
        "web_maintenance": maintenance_path,
    }


class ManualDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str | Path, **kwargs):
        super().__init__(str(filename), **kwargs)
        frame = Frame(2 * cm, 2 * cm, A4[0] - 4 * cm, A4[1] - 4 * cm, id="normal")
        template = PageTemplate(id="manual", frames=[frame], onPage=self._draw_page_chrome)
        self.addPageTemplates([template])

    def _draw_page_chrome(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#0F3A68"))
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(2 * cm, A4[1] - 1.2 * cm, "Almanaque do Fluxo de Não Conformidade")
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.restoreState()


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleCustom",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0F3A68"),
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "SubtitleCustom",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=12,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#475569"),
            spaceAfter=10,
        ),
        "heading1": ParagraphStyle(
            "Heading1Custom",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=24,
            textColor=colors.HexColor("#0F3A68"),
            spaceBefore=14,
            spaceAfter=8,
        ),
        "heading2": ParagraphStyle(
            "Heading2Custom",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#1E5E98"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "BodyCustom",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "CaptionCustom",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "BulletCustom",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10.3,
            leading=15,
            leftIndent=14,
            bulletIndent=0,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=4,
        ),
    }


def _image_block(path: Path, caption: str, width_cm: float, styles: dict) -> list:
    image = Image(str(path))
    image.drawWidth = width_cm * cm
    scale = image.drawWidth / image.imageWidth
    image.drawHeight = image.imageHeight * scale
    return [image, Spacer(1, 0.18 * cm), Paragraph(caption, styles["caption"]), Spacer(1, 0.2 * cm)]


def _step_table(step_number: str, goal: str, where: str, click_path: str):
    table = Table(
        [
            ["Passo", "Objetivo", "Tela", "Botões e cliques"],
            [step_number, goal, where, click_path],
        ],
        colWidths=[2.0 * cm, 4.2 * cm, 4.0 * cm, 6.2 * cm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F3A68")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.2),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def build_pdf(screenshots: dict[str, Path]) -> Path:
    styles = _styles()
    doc = ManualDocTemplate(
        OUTPUT_PDF,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    story: list = []
    story.append(Paragraph("Manual do Fluxo de Não Conformidade", styles["title"]))
    story.append(
        Paragraph(
            "Guia prático, visual e objetivo para acompanhar a não conformidade desde a abertura no checklist até a execução final da ordem de serviço.",
            styles["subtitle"],
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("1. Visão geral do caminho", styles["heading1"]))
    story.append(
        Paragraph(
            "Pense no fluxo como uma esteira de oficina. O motorista encontra o problema, a Central organiza, a Manutenção programa e o mecânico executa pela OS.",
            styles["body"],
        )
    )
    flow = ListFlowable(
        [
            ListItem(Paragraph("1. Motorista abre a não conformidade no checklist do Web/Mobile.", styles["bullet"])),
            ListItem(Paragraph("2. Gestor triage na Central de Resolução no Desktop.", styles["bullet"])),
            ListItem(Paragraph("3. Gestor agrupa em Pacote de Resolução.", styles["bullet"])),
            ListItem(Paragraph("4. Gestor envia o pacote para Manutenção.", styles["bullet"])),
            ListItem(Paragraph("5. Gestor cria a programação e libera a OS.", styles["bullet"])),
            ListItem(Paragraph("6. Mecânico executa e evidencia a resolução no Web/Mobile.", styles["bullet"])),
        ],
        bulletType="1",
    )
    story.append(flow)
    story.append(Spacer(1, 0.2 * cm))

    story.append(Paragraph("2. Abertura da não conformidade no Web/Mobile", styles["heading1"]))
    story.append(_step_table("1", "Entrar no sistema", "Web/Mobile", "Abrir o sistema -> preencher LOGIN e SENHA -> clicar em ENTRAR"))
    story.append(Spacer(1, 0.15 * cm))
    story.extend(_image_block(screenshots["web_login"], "Tela real de entrada do Web/Mobile.", 7.1, styles))
    story.append(
        Paragraph(
            "Use o perfil do motorista quando a abertura vier do checklist de campo. O objetivo aqui é só registrar o problema, não resolver.",
            styles["body"],
        )
    )
    story.append(_step_table("2", "Abrir o checklist do equipamento", "Web/Mobile", "Tela inicial -> botão REALIZAR CHECKLIST -> escolher a frota"))
    story.append(Spacer(1, 0.15 * cm))
    story.append(_step_table("3", "Marcar a falha como não conformidade", "Web/Mobile", "No item com problema -> marcar NÃO CONFORME -> preencher OBSERVAÇÃO -> anexar FOTO ANTES -> enviar checklist"))
    story.append(Spacer(1, 0.15 * cm))
    story.extend(_image_block(screenshots["web_checklist"], "Exemplo real do item sendo aberto como não conformidade no checklist.", 7.1, styles))

    story.append(Paragraph("3. Triagem na Central de Resolução", styles["heading1"]))
    story.append(
        Paragraph(
            "Depois que o checklist é enviado, a não conformidade não vai direto para a oficina. Ela passa primeiro pela Central de Resolução, que funciona como a recepção oficial do problema.",
            styles["body"],
        )
    )
    story.append(_step_table("4", "Abrir a Central de Resolução", "Desktop", "Menu lateral -> Utilitários -> Central de Resolução"))
    story.append(Spacer(1, 0.15 * cm))
    story.extend(_image_block(screenshots["desktop_central"], "Tela real da Central de Resolução no Desktop.", 15.5, styles))
    story.append(_step_table("5", "Ler a fila e selecionar os registros", "Desktop", "Conferir cards do topo -> localizar a NC na grade -> selecionar uma ou mais linhas"))
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        Paragraph(
            "Na Central, use as abas <b>Por item</b>, <b>Por equipamento</b>, <b>Fila</b> e <b>Bloqueios</b> para entender o tamanho do problema antes de decidir o pacote.",
            styles["body"],
        )
    )
    story.append(_step_table("6", "Criar o Pacote de Resolução", "Desktop", "Selecionar as NCs -> clicar em CRIAR PACOTE -> confirmar agrupamento e título"))
    story.append(Spacer(1, 0.15 * cm))
    story.extend(_image_block(screenshots["desktop_package_dialog"], "Diálogo real de criação do Pacote de Resolução.", 14.2, styles))
    story.append(
        Paragraph(
            "Regra simples para leigo: se o mesmo item apareceu em vários veículos, agrupe por item distinto. Se o mesmo veículo está com vários problemas ligados, agrupe por equipamento.",
            styles["body"],
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("4. Acompanhamento rápido no Web/Mobile", styles["heading1"]))
    story.append(_step_table("7", "Conferir a Central no celular", "Web/Mobile", "Tela inicial -> botão CENTRAL DE RESOLUÇÃO"))
    story.append(Spacer(1, 0.15 * cm))
    story.extend(_image_block(screenshots["web_central"], "Visão real da Central de Resolução no Web/Mobile.", 7.1, styles))
    story.append(
        Paragraph(
            "Essa tela ajuda o gestor e o mecânico a enxergarem o volume, os registros abertos e o que já entrou em pacote ou manutenção.",
            styles["body"],
        )
    )

    story.append(Paragraph("5. Envio do pacote para Manutenção", styles["heading1"]))
    story.append(_step_table("8", "Abrir o módulo de Manutenção", "Desktop", "Menu lateral -> Movimento -> Manutenção"))
    story.append(Spacer(1, 0.15 * cm))
    story.extend(_image_block(screenshots["desktop_maintenance"], "Tela real da Manutenção no Desktop.", 15.5, styles))
    story.append(_step_table("9", "Criar a programação da manutenção", "Desktop", "Na Manutenção -> clicar em NOVA PROGRAMAÇÃO -> origem Pacotes de resolução -> selecionar o pacote"))
    story.append(Spacer(1, 0.15 * cm))
    story.extend(_image_block(screenshots["desktop_schedule_dialog"], "Diálogo real de criação da programação a partir do pacote.", 14.6, styles))
    story.append(
        Paragraph(
            "Aqui o sistema já ajuda como um encarregado experiente: sugere responsável, janela de agenda e depois permite definir a peça que libera a execução.",
            styles["body"],
        )
    )
    story.append(_step_table("10", "Salvar agenda, responsável e peça", "Desktop", "Conferir responsável sugerido -> usar data sugerida se fizer sentido -> criar programação -> na aba Responsável e Peças salvar o material"))

    story.append(Paragraph("6. Execução da OS pelo mecânico", styles["heading1"]))
    story.append(_step_table("11", "Abrir a fila do mecânico", "Web/Mobile", "Tela inicial -> botão MANUTENÇÃO"))
    story.append(Spacer(1, 0.15 * cm))
    story.extend(_image_block(screenshots["web_maintenance"], "Tela real da fila de manutenção e OS no Web/Mobile.", 7.1, styles))
    story.append(_step_table("12", "Executar a OS", "Web/Mobile", "Abrir o card da OS -> conferir veículo, peça e prazo -> registrar foto depois e observação -> concluir"))
    story.append(
        Paragraph(
            "Para o mecânico, a OS é a comanda do serviço. Em vez de pensar em pacote ou regra interna, ele só precisa enxergar: o que fazer, em qual veículo, com qual peça e como concluir.",
            styles["body"],
        )
    )

    story.append(Paragraph("7. Como saber que a não conformidade fechou", styles["heading1"]))
    closing_list = ListFlowable(
        [
            ListItem(Paragraph("Na Manutenção, a OS muda para concluída.", styles["bullet"])),
            ListItem(Paragraph("A peça deixa de aparecer como bloqueio da execução.", styles["bullet"])),
            ListItem(Paragraph("Na Central de Resolução, o registro sai da fila aberta e passa a refletir a tratativa concluída.", styles["bullet"])),
            ListItem(Paragraph("Se necessário, o gestor pode exportar o PDF da OS pelo Desktop e o mecânico também pode exportar pelo Web/Mobile.", styles["bullet"])),
        ],
        bulletType="bullet",
    )
    story.append(closing_list)

    story.append(Paragraph("8. Resumo do botão a botão", styles["heading1"]))
    summary_table = Table(
        [
            ["Etapa", "Onde clicar"],
            ["Abrir checklist", "Web/Mobile -> REALIZAR CHECKLIST"],
            ["Abrir NC", "No item com falha -> NÃO CONFORME -> observação -> foto antes"],
            ["Ver fila da NC", "Desktop -> Central de Resolução"],
            ["Criar pacote", "Desktop -> selecionar NCs -> CRIAR PACOTE"],
            ["Mandar para execução", "Desktop -> Manutenção -> NOVA PROGRAMAÇÃO"],
            ["Liberar execução", "Desktop -> aba Responsável e Peças"],
            ["Executar", "Web/Mobile -> MANUTENÇÃO -> abrir OS -> concluir"],
        ],
        colWidths=[5.0 * cm, 10.2 * cm],
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F3A68")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(summary_table)

    doc.build(story)
    return OUTPUT_PDF


def build_markdown(screenshots: dict[str, Path]) -> Path:
    relative = lambda path: path.relative_to(DESKTOP_ROOT / "docs")
    content = f"""# Manual do Fluxo de Não Conformidade

## Objetivo
Explicar, em linguagem simples, como a não conformidade nasce no checklist, passa pela Central de Resolução, vira Pacote de Resolução, entra na Manutenção e termina em OS concluída.

## Fluxo resumido
1. Web/Mobile: motorista abre a não conformidade no checklist.
2. Desktop: gestor organiza o registro na Central de Resolução.
3. Desktop: gestor cria o Pacote de Resolução.
4. Desktop: gestor cria a programação da Manutenção.
5. Web/Mobile: mecânico executa a OS.

## 1. Entrada no sistema
### Desktop
![Login Desktop]({relative(screenshots["desktop_login"]).as_posix()})

### Web/Mobile
![Login Web/Mobile]({relative(screenshots["web_login"]).as_posix()})

## 2. Abertura da não conformidade no checklist
Botões:
- `REALIZAR CHECKLIST`
- marcar item como `NÃO CONFORME`
- preencher observação
- anexar `FOTO ANTES`
- enviar checklist

![Checklist com NC]({relative(screenshots["web_checklist"]).as_posix()})

## 3. Central de Resolução no Desktop
Botões:
- menu lateral `Central de Resolução`
- selecionar linhas
- `CRIAR PACOTE`
- opcional `ABRIR INSPEÇÃO DE APOIO`

![Central de Resolução]({relative(screenshots["desktop_central"]).as_posix()})

## 4. Criação do pacote
Botões:
- `CRIAR PACOTE`
- escolher `Por item distinto` ou `Por equipamento`
- confirmar título

![Criar Pacote]({relative(screenshots["desktop_package_dialog"]).as_posix()})

## 5. Visão mobile da Central
![Central no mobile]({relative(screenshots["web_central"]).as_posix()})

## 6. Envio para manutenção
Botões:
- menu lateral `Manutenção`
- `NOVA PROGRAMAÇÃO`
- origem `Pacotes de resolução`
- selecionar pacote
- usar responsável sugerido
- usar data sugerida, se fizer sentido

![Manutenção Desktop]({relative(screenshots["desktop_maintenance"]).as_posix()})

![Nova programação]({relative(screenshots["desktop_schedule_dialog"]).as_posix()})

## 7. Execução da OS no Web/Mobile
Botões:
- `MANUTENÇÃO`
- abrir card da OS
- registrar evidência depois
- concluir
- exportar PDF se necessário

![Manutenção Web/Mobile]({relative(screenshots["web_maintenance"]).as_posix()})

## Fechamento
Quando a OS é concluída:
- a execução fica registrada na Manutenção
- a peça deixa de ser bloqueio
- a Central passa a refletir a tratativa concluída
- o PDF da OS pode ser exportado pelo Desktop e pelo Web/Mobile
"""
    OUTPUT_MD.write_text(content, encoding="utf-8")
    return OUTPUT_MD


def main():
    screenshots = {}
    screenshots.update(capture_desktop_screenshots())
    screenshots.update(capture_web_mobile_screenshots())
    pdf_path = build_pdf(screenshots)
    md_path = build_markdown(screenshots)
    print(f"PDF gerado em: {pdf_path}")
    print(f"Markdown gerado em: {md_path}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
import socket
import subprocess
import sys
import textwrap
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
from reportlab.platypus.tableofcontents import TableOfContents


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = PROJECT_ROOT / "desktop"
WEB_ROOT = PROJECT_ROOT / "web_app"
OUTPUT_PDF = PROJECT_ROOT / "MANUAL_DE_INSTRUCAO_SISTEMA_CHECKLIST_FROTA.pdf"
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


def capture_desktop_screenshots() -> dict[str, Path]:
    os.environ["QT_QPA_PLATFORM"] = "windows"

    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(DESKTOP_ROOT))

    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from api_client import APIClient
    from ui.login_window import LoginWindow
    from ui.main_window import MainWindow
    from tests.test_desktop_navigation import FakeAPIClient

    app = QApplication.instance() or QApplication([])

    login_path = ASSET_DIR / "desktop_login.png"
    dashboard_path = ASSET_DIR / "desktop_dashboard.png"

    login_window = LoginWindow(APIClient())
    login_window.login_input.setText("admin")
    login_window.password_input.setText("123456")
    login_window.show()
    QTest.qWait(250)
    app.processEvents()
    login_window.grab().save(str(login_path))
    login_window.close()

    fake_api = FakeAPIClient()
    dashboard_window = MainWindow(
        fake_api,
        {"nome": "Administrador", "tipo": "admin", "login": "admin"},
    )
    dashboard_window.resize(1460, 920)
    dashboard_window.showNormal()
    dashboard_window.switch_page("dashboard")
    QTest.qWait(450)
    app.processEvents()
    dashboard_window.grab().save(str(dashboard_path))
    dashboard_window.close()

    app.processEvents()
    return {
        "desktop_login": login_path,
        "desktop_dashboard": dashboard_path,
    }


def capture_web_mobile_screenshots() -> dict[str, Path]:
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8765", "--bind", "127.0.0.1"],
        cwd=WEB_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    login_path = ASSET_DIR / "web_mobile_login.png"
    home_path = ASSET_DIR / "web_mobile_home.png"

    try:
        _wait_for_port("127.0.0.1", 8765)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(
                viewport={"width": 390, "height": 844},
                device_scale_factor=1,
                is_mobile=True,
            )
            page.goto("http://127.0.0.1:8765/index.html", wait_until="networkidle")
            page.screenshot(path=str(login_path), full_page=True)

            page.evaluate(
                """
                () => {
                    const hide = (id) => document.getElementById(id)?.classList.add('hidden');
                    hide('login-screen');
                    const home = document.getElementById('home-screen');
                    if (home) {
                        home.classList.remove('hidden');
                        home.classList.add('active');
                    }
                    const summary = document.getElementById('home-summary');
                    if (summary) {
                        summary.innerHTML = `
                            <div class="summary-grid">
                                <div class="summary-item"><span>USUÁRIO</span><strong>GESTOR</strong></div>
                                <div class="summary-item"><span>EQUIPAMENTOS</span><strong>247 ATIVOS</strong></div>
                                <div class="summary-item"><span>ATIVIDADES</span><strong>12 ABERTAS</strong></div>
                                <div class="summary-item"><span>LAVAGENS</span><strong>9 PROGRAMADAS</strong></div>
                            </div>
                        `;
                    }
                    const cloudPanel = document.getElementById('cloud-admin-panel');
                    if (cloudPanel) {
                        cloudPanel.classList.remove('hidden');
                    }
                }
                """
            )
            page.screenshot(path=str(home_path), full_page=True)
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()

    return {
        "web_mobile_login": login_path,
        "web_mobile_home": home_path,
    }


class ManualDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str | Path, **kwargs):
        super().__init__(str(filename), **kwargs)
        frame = Frame(2 * cm, 2 * cm, A4[0] - 4 * cm, A4[1] - 4 * cm, id="normal")
        template = PageTemplate(id="manual", frames=[frame], onPage=self._draw_page_chrome)
        self.addPageTemplates([template])
        self._heading_count = 0

    def _draw_page_chrome(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#0F3A68"))
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(2 * cm, A4[1] - 1.2 * cm, "Manual do Sistema de Checklist de Frota")
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        style_name = flowable.style.name
        if style_name not in {"ManualHeading1", "ManualHeading2"}:
            return
        level = 0 if style_name == "ManualHeading1" else 1
        text = flowable.getPlainText()
        key = f"section-{self._heading_count}"
        self._heading_count += 1
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=False)
        self.notify("TOCEntry", (level, text, self.page, key))


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ManualTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0F3A68"),
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "ManualSubtitle",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=12,
            leading=17,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#475569"),
            spaceAfter=8,
        ),
        "heading1": ParagraphStyle(
            "ManualHeading1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=24,
            textColor=colors.HexColor("#0F3A68"),
            spaceBefore=16,
            spaceAfter=8,
        ),
        "heading2": ParagraphStyle(
            "ManualHeading2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=19,
            textColor=colors.HexColor("#1E5E98"),
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "ManualBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "ManualCaption",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#64748B"),
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "small": ParagraphStyle(
            "ManualSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#475569"),
            spaceAfter=6,
        ),
    }


def _module_table(title: str, rows: list[tuple[str, str]], styles: dict[str, ParagraphStyle]):
    data = [
        [
            Paragraph("<b>Módulo</b>", styles["small"]),
            Paragraph("<b>Para que serve</b>", styles["small"]),
        ]
    ]
    for name, description in rows:
        data.append(
            [
                Paragraph(f"<b>{name}</b>", styles["body"]),
                Paragraph(description, styles["body"]),
            ]
        )

    table = Table(data, colWidths=[5.0 * cm, 10.5 * cm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F1FC")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F3A68")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#C7D7EA")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D8E4F2")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FBFF")]),
            ]
        )
    )
    return [Paragraph(title, styles["heading2"]), table, Spacer(1, 0.25 * cm)]


def _image_block(path: Path, caption: str, width_cm: float, styles: dict[str, ParagraphStyle]):
    image = Image(str(path))
    image.drawWidth = width_cm * cm
    image.drawHeight = image.drawWidth * 0.62
    return [image, Spacer(1, 0.12 * cm), Paragraph(caption, styles["caption"])]


def build_manual(screenshots: dict[str, Path]) -> Path:
    styles = _styles()
    logo_path = DESKTOP_ROOT / "assets" / "app-logo-cover.png"
    story = []

    if logo_path.exists():
        logo = Image(str(logo_path))
        logo.drawWidth = 8.2 * cm
        logo.drawHeight = logo.drawWidth * 0.34
        story.extend([Spacer(1, 1.4 * cm), logo, Spacer(1, 0.4 * cm)])

    story.append(Paragraph("Manual de Instrução", styles["title"]))
    story.append(Paragraph("Sistema de Checklist de Frota", styles["title"]))
    story.append(
        Paragraph(
            "Guia simples do Desktop e do Web Mobile, feito para quem precisa usar o sistema no dia a dia sem linguagem técnica.",
            styles["subtitle"],
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    intro_table = Table(
        [
            [
                Paragraph("<b>Para que serve</b>", styles["small"]),
                Paragraph(
                    "O sistema organiza checklist, atividades, lavagens, não conformidades, manutenção e relatórios da frota em um único lugar.",
                    styles["body"],
                ),
            ],
            [
                Paragraph("<b>Por que foi criado</b>", styles["small"]),
                Paragraph(
                    "Ele foi criado para dar mais controle, rastreabilidade e rapidez na operação, evitando papel solto, perda de evidência e informação espalhada.",
                    styles["body"],
                ),
            ],
            [
                Paragraph("<b>Quem usa</b>", styles["small"]),
                Paragraph(
                    "Gestor, administrador, mecânico e motorista, cada um com seu nível de acesso e sua tela de trabalho.",
                    styles["body"],
                ),
            ],
        ],
        colWidths=[4.2 * cm, 11.3 * cm],
    )
    intro_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#C7D7EA")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8E4F2")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([intro_table, PageBreak()])

    story.append(Paragraph("Sumário", styles["heading1"]))
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            name="TOCHeading1",
            fontName="Helvetica",
            fontSize=11,
            leftIndent=16,
            firstLineIndent=-10,
            spaceBefore=6,
            leading=14,
            textColor=colors.HexColor("#0F3A68"),
        ),
        ParagraphStyle(
            name="TOCHeading2",
            fontName="Helvetica",
            fontSize=10,
            leftIndent=28,
            firstLineIndent=-10,
            spaceBefore=2,
            leading=12,
            textColor=colors.HexColor("#475569"),
        ),
    ]
    story.extend([toc, PageBreak()])

    story.append(Paragraph("1. Visão Geral do Sistema", styles["heading1"]))
    story.append(
        Paragraph(
            "Pense no sistema como uma central de controle da frota. Em vez de cada informação ficar separada em papel, mensagem ou memória de quem executou, tudo passa a ficar registrado com data, hora, usuário e evidência.",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "O Desktop é a área de gestão e cadastro. O Web Mobile é a área prática para quem executa o trabalho no celular.",
            styles["body"],
        )
    )

    story.append(Paragraph("2. Como o Sistema é Dividido", styles["heading1"]))
    overview_bullets = [
        "Desktop: usado principalmente para administração, acompanhamento, planejamento e relatórios.",
        "Web Mobile: usado para checklist, execução de atividades, lavagens e manutenção em campo.",
        "Banco de dados: guarda tudo o que foi feito, como uma memória oficial do sistema.",
        "API: faz a ponte entre as telas e os dados, para que tudo converse corretamente.",
    ]
    story.append(
        ListFlowable(
            [ListItem(Paragraph(item, styles["body"])) for item in overview_bullets],
            bulletType="bullet",
            start="circle",
            leftPadding=18,
        )
    )

    story.append(Paragraph("3. Desktop", styles["heading1"]))
    story.append(
        Paragraph(
            "O Desktop é o painel mais completo. É onde normalmente ficam as telas de cadastro, relatórios, gestão de usuários e visão geral da operação.",
            styles["body"],
        )
    )
    story.extend(_image_block(screenshots["desktop_login"], "Tela de entrada do Desktop.", 15.4, styles))
    story.extend(
        _image_block(
            screenshots["desktop_dashboard"],
            "Exemplo do Desktop já aberto no painel principal.",
            15.4,
            styles,
        )
    )

    desktop_modules = [
        ("Equipamentos", "Cadastrar, editar e consultar os veículos e equipamentos da frota."),
        ("Checklist", "Configurar itens que serão usados nos checklists."),
        ("Materiais", "Controlar peças, estoque e movimentos de entrada e saída."),
        ("Atividades", "Abrir atividades em massa, acompanhar execução e evidências."),
        ("Lavagens", "Gerenciar fila, cronograma, histórico e relatórios de lavagem."),
        ("Manutenção", "Planejar, acompanhar e concluir serviços."),
        ("Relatórios", "Consultar dados consolidados para análise e decisão."),
        ("Produtividade", "Acompanhar indicadores de execução por usuário ou operação."),
        ("Histórico Checklist", "Ver a matriz histórica por frota e por data."),
        ("Ocorrências", "Controlar não conformidades e tratativas."),
        ("Logins", "Gerenciar usuários e perfis de acesso."),
    ]
    story.extend(_module_table("Módulos principais do Desktop", desktop_modules, styles))

    story.append(Paragraph("4. Como usar o Desktop no dia a dia", styles["heading1"]))
    desktop_flow = [
        "Entrar com login e senha.",
        "Abrir o módulo desejado no menu lateral ou superior.",
        "Cadastrar ou consultar informações.",
        "Exportar PDF, Excel ou CSV quando precisar compartilhar.",
        "Encerrar a sessão ao terminar o uso.",
    ]
    story.append(
        ListFlowable(
            [ListItem(Paragraph(item, styles["body"])) for item in desktop_flow],
            bulletType="1",
            leftPadding=18,
        )
    )

    story.append(Paragraph("5. Web Mobile", styles["heading1"]))
    story.append(
        Paragraph(
            "O Web Mobile foi feito para uso rápido no celular. Ele serve para quem está executando o trabalho, registrando o que foi feito e anexando evidências no mesmo momento.",
            styles["body"],
        )
    )
    story.extend(_image_block(screenshots["web_mobile_login"], "Tela de entrada do Web Mobile.", 7.1, styles))
    story.extend(_image_block(screenshots["web_mobile_home"], "Tela inicial do Web Mobile com os atalhos principais.", 7.1, styles))

    mobile_modules = [
        ("Realizar Checklist", "Selecionar um equipamento e marcar item por item como OK ou não conformidade."),
        ("Histórico de Checklist", "Consultar o que já foi feito por frota e período."),
        ("Atividades", "Executar tarefas abertas pelo Desktop e registrar evidências."),
        ("Lavagens", "Confirmar lavagens do cronograma e acompanhar o calendário."),
        ("Não Conformidades", "Resolver problemas pendentes com observação, peça e foto."),
        ("Manutenção", "Acompanhar serviços programados e executar apontamentos."),
    ]
    story.extend(_module_table("Módulos principais do Web Mobile", mobile_modules, styles))

    story.append(Paragraph("6. Como usar o Web Mobile no dia a dia", styles["heading1"]))
    mobile_flow = [
        "Entrar com login e senha.",
        "Tocar no módulo desejado.",
        "Executar a atividade do momento, como checklist, lavagem ou manutenção.",
        "Anexar foto e observação quando o sistema pedir.",
        "Salvar ou enviar para registrar oficialmente o que foi feito.",
    ]
    story.append(
        ListFlowable(
            [ListItem(Paragraph(item, styles["body"])) for item in mobile_flow],
            bulletType="1",
            leftPadding=18,
        )
    )

    story.append(Paragraph("7. Perfis de acesso", styles["heading1"]))
    story.append(
        Paragraph(
            "Nem todo usuário vê as mesmas telas. Isso existe para organizar o trabalho e evitar acesso ao que não faz parte da função de cada pessoa.",
            styles["body"],
        )
    )
    access_rows = [
        ("Admin", "Tem a visão mais completa, incluindo usuários e configurações administrativas."),
        ("Gestor", "Acompanha a operação, consulta relatórios e gerencia o fluxo do trabalho."),
        ("Mecânico", "Atua mais nas áreas ligadas a atividades, manutenção e tratativas operacionais."),
        ("Motorista", "Usa principalmente as funções necessárias para execução prática no mobile."),
    ]
    story.extend(_module_table("Perfis do sistema", access_rows, styles))

    story.append(Paragraph("8. O que o sistema ajuda a evitar", styles["heading1"]))
    help_bullets = [
        "Perda de informação sobre o que foi feito.",
        "Esquecimento de evidência fotográfica.",
        "Dúvida sobre quem executou cada ação.",
        "Planilhas soltas e controles paralelos.",
        "Falta de histórico para auditoria e tomada de decisão.",
    ]
    story.append(
        ListFlowable(
            [ListItem(Paragraph(item, styles["body"])) for item in help_bullets],
            bulletType="bullet",
            start="circle",
            leftPadding=18,
        )
    )

    story.append(Paragraph("9. Dicas simples para o usuário", styles["heading1"]))
    story.append(
        Paragraph(
            textwrap.fill(
                "Sempre confira se está no equipamento certo antes de registrar informações. "
                "Quando houver não conformidade, escreva a observação de forma simples e objetiva. "
                "Se o sistema pedir foto, tente anexar uma imagem clara. "
                "E sempre finalize a ação para que ela fique salva no histórico.",
                115,
            ),
            styles["body"],
        )
    )

    story.append(Paragraph("10. Fechamento", styles["heading1"]))
    story.append(
        Paragraph(
            "Em resumo: o Sistema de Checklist de Frota foi criado para transformar operação em registro confiável. O Desktop ajuda a gerir. O Web Mobile ajuda a executar. Juntos, eles organizam a rotina da frota de forma clara, rastreável e prática.",
            styles["body"],
        )
    )

    doc = ManualDocTemplate(
        OUTPUT_PDF,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2 * cm,
        title="Manual de Instrução - Sistema de Checklist de Frota",
        author="OpenAI Codex",
        subject="Manual de uso do Desktop e Web Mobile",
    )
    doc.build(story)
    return OUTPUT_PDF


def main() -> int:
    _safe_mkdir(ASSET_DIR)
    screenshots = {}
    screenshots.update(capture_desktop_screenshots())
    screenshots.update(capture_web_mobile_screenshots())
    output = build_manual(screenshots)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

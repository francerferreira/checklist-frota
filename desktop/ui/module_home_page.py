from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QTimer, QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from components import StatCard, make_icon
from theme import style_card


class ModuleLandingPage(QFrame):
    """Tela inicial de um módulo com indicadores de navegação e atalhos da área."""

    open_page_requested = Signal(str)

    def __init__(
        self,
        title: str,
        subtitle: str,
        module_label: str,
        shortcuts: list[tuple[str, str, str, str]],
        allowed_pages: set[str],
        user_role: str,
        api_client=None,
        module_key: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("ContentSurface")
        self.title = title
        self.api_client = api_client
        self.module_key = module_key
        self.shortcut_rows = [row for row in shortcuts if row[2] in allowed_pages]
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.setInterval(60_000)
        self.auto_refresh_timer.timeout.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        heading = QLabel(title)
        heading.setObjectName("PageTitle")
        description = QLabel(subtitle)
        description.setObjectName("PageSubtitle")
        description.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(description)

        hero = QFrame()
        style_card(hero)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(14)

        badge = QLabel(module_label.upper())
        badge.setObjectName("BadgeStrong")
        badge.setMinimumWidth(140)
        badge.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(badge, 0)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(3)
        scope_title = QLabel("Central do módulo")
        scope_title.setObjectName("SectionTitle")
        scope_caption = QLabel(
            "Use esta tela como ponto de partida. Cada botão abre somente uma subtela desta área."
        )
        scope_caption.setObjectName("SectionCaption")
        scope_caption.setWordWrap(True)
        hero_text.addWidget(scope_title)
        hero_text.addWidget(scope_caption)
        hero_layout.addLayout(hero_text, 1)
        self.last_updated_label = QLabel("Atualização automática: aguardando dados")
        self.last_updated_label.setObjectName("MutedText")
        self.last_updated_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.last_updated_label.setWordWrap(True)
        hero_layout.addWidget(self.last_updated_label, 0)
        layout.addWidget(hero)

        stats = QGridLayout()
        stats.setSpacing(14)
        for column in range(3):
            stats.setColumnStretch(column, 1)
        self.subscreens_card = StatCard(
            "Subtelas disponíveis",
            str(len(self.shortcut_rows)),
            "Telas liberadas para este módulo",
            icon_name="reports",
        )
        self.shortcuts_card = StatCard(
            "Atalhos operacionais",
            str(len(self.shortcut_rows)),
            "Acesso direto às rotinas da área",
            icon_name="dashboard",
        )
        self.access_card = StatCard(
            "Perfil conectado",
            str(user_role or "usuário").upper(),
            "Permissões aplicadas automaticamente",
            icon_name="users",
        )
        stats.addWidget(self.subscreens_card, 0, 0)
        stats.addWidget(self.shortcuts_card, 0, 1)
        stats.addWidget(self.access_card, 0, 2)
        layout.addLayout(stats)

        shortcuts_card = QFrame()
        style_card(shortcuts_card)
        shortcuts_layout = QVBoxLayout(shortcuts_card)
        shortcuts_layout.setContentsMargins(14, 14, 14, 14)
        shortcuts_layout.setSpacing(10)

        shortcuts_title = QLabel("Atalhos do módulo")
        shortcuts_title.setObjectName("SectionTitle")
        shortcuts_caption = QLabel("Selecione uma rotina para abrir a tela correspondente.")
        shortcuts_caption.setObjectName("SectionCaption")
        shortcuts_layout.addWidget(shortcuts_title)
        shortcuts_layout.addWidget(shortcuts_caption)

        grid = QGridLayout()
        grid.setSpacing(12)
        for index, (label, detail, page_key, icon_name) in enumerate(self.shortcut_rows):
            shortcut = QFrame()
            style_card(shortcut)
            shortcut_layout = QVBoxLayout(shortcut)
            shortcut_layout.setContentsMargins(12, 12, 12, 12)
            shortcut_layout.setSpacing(7)

            button = QPushButton(label)
            button.setObjectName("ModuleShortcut")
            button.setProperty("variant", "secondary")
            button.setIcon(make_icon(icon_name, "#FFFFFF", "#115FC0", 18))
            button.setIconSize(QSize(18, 18))
            button.setMinimumHeight(42)
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(detail)
            button.clicked.connect(lambda checked=False, key=page_key: self.open_page_requested.emit(key))

            caption = QLabel(detail)
            caption.setObjectName("CardSubtitle")
            caption.setWordWrap(True)
            shortcut_layout.addWidget(button)
            shortcut_layout.addWidget(caption)
            grid.addWidget(shortcut, index // 3, index % 3)

        if not self.shortcut_rows:
            empty = QLabel("Nenhuma subtela foi liberada para este perfil.")
            empty.setObjectName("MutedText")
            grid.addWidget(empty, 0, 0)
        shortcuts_layout.addLayout(grid)
        layout.addWidget(shortcuts_card, 1)

    def refresh(self) -> None:
        """Atualiza os indicadores da central sem alterar dados operacionais."""
        if self.api_client is None or not self.module_key:
            return
        try:
            if self.module_key == "equipment_home":
                overview = self.api_client.get_availability_overview() or {}
                rows = list(overview.get("rows") or [])
                counts = overview.get("summary") or {}
                status_counts = counts.get("status_counts") or {}
                available = int(status_counts.get("DISPONIVEL", 0)) + int(status_counts.get("RESTRICAO", 0))
                attention = len(rows) - available
                self.subscreens_card.set_content("Ativos cadastrados", str(len(rows)), "Equipamentos retornados pela API")
                self.shortcuts_card.set_content("Disponíveis", str(available), "Disponíveis ou em restrição operacional")
                self.access_card.set_content("Em atenção", str(max(0, attention)), "Indisponíveis ou em manutenção")
            elif self.module_key == "rh_home":
                employees = list(self.api_client.get_employees(status="ATIVO") or [])
                self.subscreens_card.set_content("Colaboradores ativos", str(len(employees)), "Cadastro ativo no RH")
                self.shortcuts_card.set_content("Turnos", str(len({row.get('shift_name') for row in employees if row.get('shift_name')})), "Turnos com colaboradores ativos")
                self.access_card.set_content("Áreas", str(len({row.get('team_name') for row in employees if row.get('team_name')})), "Áreas com efetivo cadastrado")
            elif self.module_key == "attendance_home":
                payload = self.api_client.get_mobile_absenteeism(reference_date=date.today().isoformat()) or {}
                summary = payload.get("summary") or {}
                by_type = summary.get("by_type") or {}
                self.subscreens_card.set_content("Colaboradores", str(summary.get("total", sum(by_type.values()))), "Total da apuração de hoje")
                self.shortcuts_card.set_content("Presentes", str(by_type.get("PRESENTE", 0)), "Presença registrada no dia")
                absences = sum(int(by_type.get(key, 0)) for key in ("FALTA", "ATESTADO", "AFASTADO"))
                self.access_card.set_content("Ausências", str(absences), "Faltas, atestados e afastamentos")
            elif self.module_key == "schedule_home":
                schedules = list(self.api_client.get_special_schedules() or [])
                self.subscreens_card.set_content("Escalas registradas", str(len(schedules)), "Domingos e feriados cadastrados")
                self.shortcuts_card.set_content("Confirmados", str(sum(1 for row in schedules if row.get("status") == "CONFIRMADA")), "Presenças confirmadas")
                self.access_card.set_content("DSR lançadas", str(sum(1 for row in schedules if row.get("dsr_date"))), "Registros com data de DSR")
            elif self.module_key == "maintenance_home":
                dashboard = self.api_client.get_dashboard() or {}
                intelligence = dashboard.get("manutencao_portuaria") or {}
                backlog = intelligence.get("backlog") or {}
                self.subscreens_card.set_content("OS abertas", str(backlog.get("total", 0)), "Itens no backlog operacional")
                self.shortcuts_card.set_content("OS vencidas", str(backlog.get("vencidas", 0)), "Itens que exigem prioridade")
                pcm = intelligence.get("pcm") or {}
                self.access_card.set_content("Preventivas vencidas", str(pcm.get("preventivas_vencendo_ou_vencidas", 0)), "Planos preventivos em atraso")
            self.last_updated_label.setText(
                f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')} · próxima atualização em 1 min"
            )
        except Exception:
            self.last_updated_label.setText("Atualização automática: falha de conexão")
            self.access_card.set_content("Conexão", "INDISPONÍVEL", "Não foi possível atualizar os indicadores")

    def showEvent(self, event):
        self.auto_refresh_timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.auto_refresh_timer.stop()
        super().hideEvent(event)

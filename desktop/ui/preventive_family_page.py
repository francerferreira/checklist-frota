from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QDoubleSpinBox,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from components import StatCard, show_notice
from theme import configure_table, make_table_item, style_filter_bar, style_table_card


STATUS_LABELS = {
    "NO_PRAZO": "No prazo",
    "ATENCAO": "Atenção",
    "PROXIMA": "Próxima",
    "CRITICA": "Crítica",
    "VENCIDA": "Vencida",
    "LEITURA_DESATUALIZADA": "Leitura desatualizada",
    "SEM_DADOS": "Sem dados",
}
STATUS_COLORS = {
    "NO_PRAZO": ("#DCFCE7", "#166534"),
    "ATENCAO": ("#FEF3C7", "#92400E"),
    "PROXIMA": ("#FFEDD5", "#9A3412"),
    "CRITICA": ("#FEE2E2", "#B91C1C"),
    "VENCIDA": ("#FECACA", "#991B1B"),
    "LEITURA_DESATUALIZADA": ("#E2E8F0", "#475569"),
    "SEM_DADOS": ("#F1F5F9", "#64748B"),
}


class HourmeterEntryDialog(QDialog):
    """Lançamento auditável de horímetro para uma família de equipamentos."""

    def __init__(self, api_client, family: str, rows: list[dict], parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.family = family.upper()
        self.rows = list(rows or [])
        self.selected_row: dict | None = None
        self.photo_path: str | None = None
        self.setWindowTitle(f"Registrar horímetro {self.family}")
        self.setMinimumSize(620, 610)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel(f"REGISTRAR HORÍMETRO — {self.family}")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        subtitle = QLabel("Registre uma nova leitura sem apagar o histórico anterior.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addWidget(QLabel("Pesquisar equipamento"))
        self.search = QLineEdit()
        self.search.setPlaceholderText(f"Buscar equipamento {self.family}")
        self.search.textChanged.connect(self._render_equipment_list)
        layout.addWidget(self.search)

        layout.addWidget(QLabel("Equipamento"))
        self.equipment_list = QListWidget()
        self.equipment_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.equipment_list.setMinimumHeight(100)
        self.equipment_list.setMaximumHeight(145)
        self.equipment_list.itemSelectionChanged.connect(self._select_equipment)
        layout.addWidget(self.equipment_list)

        self.last_reading_label = QLabel("Último horímetro: Sem leitura")
        self.last_reading_label.setObjectName("SectionCaption")
        layout.addWidget(self.last_reading_label)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.addWidget(QLabel("Novo horímetro"), 0, 0)
        self.reading_spin = QDoubleSpinBox()
        self.reading_spin.setRange(0, 10_000_000)
        self.reading_spin.setDecimals(2)
        self.reading_spin.setSingleStep(1)
        self.reading_spin.valueChanged.connect(self._update_difference)
        form.addWidget(self.reading_spin, 1, 0)
        form.addWidget(QLabel("Diferença da leitura anterior"), 0, 1)
        self.difference_label = QLabel("-")
        form.addWidget(self.difference_label, 1, 1)

        form.addWidget(QLabel("Data e hora da leitura"), 2, 0)
        self.recorded_at = QDateTimeEdit()
        self.recorded_at.setDateTime(QDateTime.currentDateTime())
        self.recorded_at.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.recorded_at.setCalendarPopup(True)
        can_edit_date = str((self.api_client.user or {}).get("tipo") or "").lower() in {"admin", "gestor"}
        self.recorded_at.setEnabled(can_edit_date)
        self.recorded_at.setToolTip("Somente ADMIN e GESTOR podem alterar a data e hora.")
        form.addWidget(self.recorded_at, 3, 0)
        form.addWidget(QLabel("Origem"), 2, 1)
        form.addWidget(QLabel("Desktop"), 3, 1)
        layout.addLayout(form)

        user = self.api_client.user or {}
        layout.addWidget(QLabel(f"Usuário responsável: {user.get('nome') or user.get('login') or 'Usuário autenticado'}"))
        layout.addWidget(QLabel("Observação (opcional)"))
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Informe uma observação sobre a leitura, se necessário.")
        self.notes.setMaximumHeight(70)
        layout.addWidget(self.notes)

        photo_row = QHBoxLayout()
        self.photo_label = QLabel("Nenhuma foto selecionada")
        photo_button = QPushButton("Anexar foto do painel")
        photo_button.clicked.connect(self._select_photo)
        photo_row.addWidget(photo_button)
        photo_row.addWidget(self.photo_label, 1)
        layout.addLayout(photo_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.button(QDialogButtonBox.Save).setText("Salvar leitura")
        buttons.button(QDialogButtonBox.Save).setProperty("variant", "primary")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._save)
        layout.addWidget(buttons)

        self._render_equipment_list()

    def _render_equipment_list(self):
        query = self.search.text().strip().casefold()
        self.equipment_list.clear()
        for row in self.rows:
            vehicle = row.get("vehicle") or {}
            label = str(vehicle.get("frota") or vehicle.get("placa") or vehicle.get("modelo") or "Equipamento")
            local = (vehicle.get("operational_location") or {}).get("full_name") or "Sem local"
            if query and query not in f"{label} {local}".casefold():
                continue
            item = QListWidgetItem(f"{label}  |  {local}")
            item.setData(Qt.UserRole, row)
            self.equipment_list.addItem(item)
        if self.equipment_list.count() and not self.equipment_list.currentItem():
            self.equipment_list.setCurrentRow(0)

    def _select_equipment(self):
        item = self.equipment_list.currentItem()
        self.selected_row = item.data(Qt.UserRole) if item else None
        current = (self.selected_row or {}).get("current")
        if current is None:
            current = ((self.selected_row or {}).get("state") or {}).get("latest_hourmeter")
        if current is None:
            self.last_reading_label.setText("Último horímetro: Sem leitura")
            self.reading_spin.setValue(0)
        else:
            current_value = float(current)
            self.last_reading_label.setText(f"Último horímetro: {current_value:.2f} h")
            self.reading_spin.setValue(current_value)
        self._update_difference()

    def _update_difference(self):
        current = (self.selected_row or {}).get("current")
        if current is None:
            current = ((self.selected_row or {}).get("state") or {}).get("latest_hourmeter")
        self.difference_label.setText(f"{self.reading_spin.value() - float(current):.2f} h" if current is not None else "Primeira leitura")

    def _select_photo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar foto do painel", "", "Imagens (*.png *.jpg *.jpeg *.webp);;Todos os arquivos (*)")
        if path:
            self.photo_path = path
            self.photo_label.setText(Path(path).name)

    def _save(self):
        if not self.selected_row:
            show_notice(self, "Equipamento obrigatório", f"Selecione um equipamento {self.family}.", icon_name="warning")
            return
        if self.recorded_at.dateTime() > QDateTime.currentDateTime():
            show_notice(self, "Data inválida", "A data da leitura não pode estar no futuro.", icon_name="warning")
            return
        current = (self.selected_row or {}).get("current")
        if current is None:
            current = ((self.selected_row or {}).get("state") or {}).get("latest_hourmeter")
        reading = self.reading_spin.value()
        if current is not None and reading < float(current):
            show_notice(
                self,
                "Leitura menor que a anterior",
                f"A leitura informada é menor que a última leitura registrada ({float(current):.2f} h).",
                icon_name="warning",
            )
            return
        if current is not None and reading - float(current) > 400:
            answer = QMessageBox.question(
                self,
                "Variação elevada",
                f"A diferença informada é de {reading - float(current):.2f} h. Confirma a leitura?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        vehicle = self.selected_row.get("vehicle") or {}
        evidence_path = None
        try:
            if self.photo_path:
                upload = self.api_client.upload_file(
                    self.photo_path,
                    str(vehicle.get("frota") or vehicle.get("placa") or "equipamento"),
                    "horimetro",
                    str((self.api_client.user or {}).get("login") or "desktop"),
                )
                evidence_path = upload.get("path") or upload.get("url")
            self.api_client.record_equipment_hourmeter(
                int(vehicle["id"]),
                {
                    "reading": reading,
                    "recorded_at": self.recorded_at.dateTime().toPython().isoformat(timespec="minutes"),
                    "notes": self.notes.toPlainText().strip() or None,
                    "evidence_path": evidence_path,
                },
            )
        except Exception as exc:
            show_notice(self, "Leitura não salva", str(exc), icon_name="warning")
            return
        self.accept()


def _text(value) -> str:
    return str(value or "").strip()


def _date_text(value) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(value)[:10]


def _family_match(vehicle: dict, family: str) -> bool:
    family_data = vehicle.get("family") or {}
    expected = family.casefold()
    return any(
        expected == _text(value).casefold()
        for value in (vehicle.get("tipo"), family_data.get("code"), family_data.get("name"))
    )


def _status_for_plan(plan: dict | None) -> str:
    if not plan:
        return "SEM_DADOS"
    due = plan.get("due") or {}
    status = _text(due.get("calculation_status")).upper()
    if status in STATUS_LABELS:
        return status
    return {"VENCENDO": "ATENCAO", "EM_DIA": "NO_PRAZO", "VENCIDA": "VENCIDA"}.get(
        _text(due.get("status")).upper(), "SEM_DADOS"
    )


class PreventiveFamilyPage(QFrame):
    """Tela compartilhada de preventiva por família.

    A Etapa 6 habilita RTG. A mesma classe será reutilizada pela tela LBS na
    Etapa 7, mantendo as fontes de dados filtradas por família.
    """

    data_changed = Signal()
    open_page_requested = Signal(str)

    def __init__(self, api_client, family: str, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.family = _text(family).upper()
        self.rows: list[dict] = []
        self.visible_rows: list[dict] = []
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title_wrap = QVBoxLayout()
        title = QLabel(f"PREVENTIVA {self.family}")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Controle de manutenção preventiva por horímetro")
        subtitle.setObjectName("PageSubtitle")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header.addLayout(title_wrap, 1)
        self.last_update = QLabel("Última atualização: -")
        self.last_update.setObjectName("SectionCaption")
        header.addWidget(self.last_update, 0, Qt.AlignTop)
        register_button = QPushButton("Registrar horímetro")
        register_button.setProperty("variant", "primary")
        register_button.clicked.connect(self._open_hourmeter_dialog)
        pcm_button = QPushButton("Abrir PCM")
        pcm_button.clicked.connect(lambda: self.open_page_requested.emit("pcm"))
        refresh_button = QPushButton("Atualizar")
        refresh_button.setProperty("variant", "primary")
        refresh_button.clicked.connect(self.refresh)
        header.addWidget(register_button)
        header.addWidget(pcm_button)
        header.addWidget(refresh_button)
        layout.addLayout(header)

        cards = QGridLayout()
        cards.setHorizontalSpacing(10)
        cards.setVerticalSpacing(10)
        self.cards = {
            "total": StatCard("Equipamentos", "0", f"Ativos {self.family}", icon_name="equipment"),
            "NO_PRAZO": StatCard("No prazo", "0", "Ciclo acima de 200 h", icon_name="ok"),
            "ATENCAO": StatCard("Atenção", "0", "Entre 101 e 200 h", icon_name="warning"),
            "PROXIMA": StatCard("Próximas", "0", "Entre 21 e 100 h", icon_name="warning"),
            "CRITICA": StatCard("Críticas", "0", "Até 20 h restantes", icon_name="warning"),
            "VENCIDA": StatCard("Vencidas", "0", "Ciclo atingido", icon_name="warning"),
            "SEM_DADOS": StatCard("Sem leitura", "0", "Sem plano ou horímetro", icon_name="dashboard"),
        }
        for index, card in enumerate(self.cards.values()):
            cards.addWidget(card, index // 4, index % 4)
        for column in range(4):
            cards.setColumnStretch(column, 1)
        layout.addLayout(cards)

        filters = QFrame()
        style_filter_bar(filters)
        filter_layout = QGridLayout(filters)
        filter_layout.setContentsMargins(12, 10, 12, 10)
        filter_layout.setHorizontalSpacing(10)
        self.status_filter = QComboBox()
        self.status_filter.addItem("Todos os status", "")
        for key, label in STATUS_LABELS.items():
            self.status_filter.addItem(label, key)
        self.search = QLineEdit()
        self.search.setPlaceholderText(f"Buscar equipamento, local ou plano {self.family}")
        filter_layout.addWidget(QLabel("Situação"), 0, 0)
        filter_layout.addWidget(self.status_filter, 1, 0)
        filter_layout.addWidget(QLabel("Pesquisa"), 0, 1)
        filter_layout.addWidget(self.search, 1, 1)
        filter_layout.setColumnStretch(0, 1)
        filter_layout.setColumnStretch(1, 2)
        self.status_filter.currentIndexChanged.connect(self._render_rows)
        self.search.textChanged.connect(self._render_rows)
        layout.addWidget(filters)

        content = QHBoxLayout()
        content.setSpacing(12)
        table_card = QFrame()
        style_table_card(table_card)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.addWidget(QLabel("Equipamentos RTG" if self.family == "RTG" else f"Equipamentos {self.family}"))
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Status", "Equipamento", "Local", "Horímetro", "Última leitura", "Próx. h", "Restantes", "Progresso", "Situação"]
        )
        configure_table(self.table, stretch_last=False)
        self.table.setMinimumHeight(420)
        self.table.itemSelectionChanged.connect(self._show_selected_row)
        table_layout.addWidget(self.table)
        content.addWidget(table_card, 3)

        self.detail_card = QFrame()
        style_table_card(self.detail_card)
        detail_layout = QVBoxLayout(self.detail_card)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(8)
        detail_title = QLabel("Detalhes do equipamento")
        detail_title.setObjectName("SectionTitle")
        detail_layout.addWidget(detail_title)
        self.detail_labels: dict[str, QLabel] = {}
        for key, label in (
            ("equipment", "Equipamento"),
            ("location", "Local"),
            ("model", "Modelo / motor"),
            ("current", "Horímetro atual"),
            ("last", "Última leitura"),
            ("last_preventive", "Última preventiva"),
            ("next", "Próxima preventiva"),
            ("remaining", "Horas restantes"),
            ("status", "Situação"),
        ):
            line = QLabel(f"{label}: -")
            line.setWordWrap(True)
            detail_layout.addWidget(line)
            self.detail_labels[key] = line
        detail_layout.addStretch(1)
        content.addWidget(self.detail_card, 1)
        layout.addLayout(content, 1)

    def set_loading_state(self, loading: bool):
        self.setEnabled(not loading)

    def _open_hourmeter_dialog(self):
        if not self.rows:
            show_notice(self, "Equipamentos indisponíveis", f"Nenhum equipamento ativo da família {self.family} foi carregado.", icon_name="warning")
            return
        dialog = HourmeterEntryDialog(self.api_client, self.family, self.rows, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh()
            self.data_changed.emit()

    def refresh(self):
        try:
            vehicles = self.api_client.get_equipment(tipo=self.family.lower(), ativos=True) or []
            plans = self.api_client.get_preventive_plans() or []
            plans_by_vehicle: dict[int, dict] = {}
            for plan in plans:
                if _text(plan.get("status")).upper() != "ATIVO":
                    continue
                vehicle_id = plan.get("vehicle_id")
                if vehicle_id is not None and vehicle_id not in plans_by_vehicle:
                    plans_by_vehicle[vehicle_id] = plan
            self.rows = []
            for vehicle in vehicles:
                if not vehicle.get("ativo", True) or not _family_match(vehicle, self.family):
                    continue
                plan = plans_by_vehicle.get(vehicle.get("id"))
                due = (plan or {}).get("due") or {}
                state = vehicle.get("operational_state") or {}
                status = _status_for_plan(plan)
                self.rows.append({
                    "vehicle": vehicle,
                    "plan": plan,
                    "state": state,
                    "status": status,
                    "current": state.get("latest_hourmeter"),
                    "last_reading_at": state.get("latest_hourmeter_at"),
                    "next_due": due.get("next_due_hourmeter") or (plan or {}).get("next_due_hourmeter"),
                    "remaining": due.get("hours_remaining"),
                    "percent": due.get("percent_used"),
                })
            self.last_update.setText(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            self._render_rows()
        except Exception as exc:
            show_notice(self, f"Falha ao carregar preventiva {self.family}", str(exc), icon_name="warning")

    def _matches(self, row: dict) -> bool:
        selected = _text(self.status_filter.currentData()).upper()
        if selected and row["status"] != selected:
            return False
        query = self.search.text().strip().casefold()
        if not query:
            return True
        vehicle = row.get("vehicle") or {}
        plan = row.get("plan") or {}
        location = vehicle.get("operational_location") or {}
        searchable = " ".join(
            _text(value)
            for value in (
                vehicle.get("frota"), vehicle.get("modelo"), vehicle.get("local"),
                location.get("name"), location.get("full_name"), plan.get("title"),
            )
        ).casefold()
        return query in searchable

    def _render_rows(self):
        self.visible_rows = [row for row in self.rows if self._matches(row)]
        counts = {key: 0 for key in self.cards if key != "total"}
        for row in self.visible_rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        self.cards["total"].set_content("Equipamentos", str(len(self.visible_rows)), f"Ativos {self.family}")
        for key in counts:
            self.cards[key].set_content(STATUS_LABELS.get(key, key), str(counts[key]), self.cards[key].subtitle_label.text())

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.visible_rows))
        for index, row in enumerate(self.visible_rows):
            vehicle = row["vehicle"]
            location = vehicle.get("operational_location") or {}
            local = location.get("full_name") or location.get("name") or vehicle.get("local") or "Sem local"
            current = row.get("current")
            next_due = row.get("next_due")
            remaining = row.get("remaining")
            percent = row.get("percent")
            progress = f"{float(percent):.0f}%" if percent is not None else "-"
            values = [
                STATUS_LABELS.get(row["status"], row["status"]),
                vehicle.get("frota") or vehicle.get("placa") or "-",
                local,
                f"{float(current):.2f} h" if current is not None else "-",
                _date_text(row.get("last_reading_at")),
                f"{float(next_due):.2f} h" if next_due is not None else "-",
                f"{float(remaining):.0f} h" if remaining is not None else "-",
                progress,
                STATUS_LABELS.get(row["status"], row["status"]),
            ]
            for column, value in enumerate(values):
                item = make_table_item(value, payload=row if column == 1 else None)
                if column in (0, 8):
                    background, foreground = STATUS_COLORS.get(row["status"], STATUS_COLORS["SEM_DADOS"])
                    item.setBackground(QColor(background))
                    item.setForeground(QColor(foreground))
                self.table.setItem(index, column, item)
        self.table.resizeColumnsToContents()
        if self.visible_rows and self.table.currentRow() < 0:
            self.table.selectRow(0)
        elif not self.visible_rows:
            self._clear_details()

    def _show_selected_row(self):
        index = self.table.currentRow()
        if index < 0 or index >= len(self.visible_rows):
            self._clear_details()
            return
        row = self.visible_rows[index]
        vehicle = row["vehicle"]
        plan = row.get("plan") or {}
        detail = {
            "equipment": vehicle.get("frota") or "-",
            "location": (vehicle.get("operational_location") or {}).get("full_name") or vehicle.get("local") or "Sem local",
            "model": " / ".join(value for value in (vehicle.get("modelo"), vehicle.get("configuracao")) if value) or "-",
            "current": f"{float(row['current']):.2f} h" if row.get("current") is not None else "Sem leitura",
            "last": _date_text(row.get("last_reading_at")),
            "last_preventive": plan.get("title") or "Sem plano preventivo",
            "next": f"{float(row['next_due']):.2f} h" if row.get("next_due") is not None else "Não calculada",
            "remaining": f"{float(row['remaining']):.0f} h" if row.get("remaining") is not None else "-",
            "status": STATUS_LABELS.get(row["status"], row["status"]),
        }
        for key, value in detail.items():
            label = self.detail_labels[key]
            caption = label.text().split(":", 1)[0]
            label.setText(f"{caption}: {value}")

    def _clear_details(self):
        for label in self.detail_labels.values():
            caption = label.text().split(":", 1)[0]
            label.setText(f"{caption}: -")


class PreventiveRTGPage(PreventiveFamilyPage):
    def __init__(self, api_client, parent=None):
        super().__init__(api_client, "RTG", parent)


class PreventiveLBSPage(PreventiveFamilyPage):
    def __init__(self, api_client, parent=None):
        super().__init__(api_client, "LBS", parent)

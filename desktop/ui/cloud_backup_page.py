from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)

from components import AnimatedButton, make_icon, show_notice
from theme import style_card


class UsageCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        style_card(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("SectionTitle")

        self.level_badge = QLabel("OK")
        self.level_badge.setAlignment(Qt.AlignCenter)
        self.level_badge.setMinimumWidth(56)
        self.level_badge.setStyleSheet(_badge_style("ok"))

        header.addWidget(self.title_label, 1)
        header.addWidget(self.level_badge, 0)

        self.detail_label = QLabel("0% | 0 MB de 0 MB")
        self.detail_label.setObjectName("MutedText")

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(12)
        self.progress.setStyleSheet(_progress_style("#5B6571"))

        layout.addLayout(header)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.progress)

    def set_usage(self, data: dict):
        percent = float(data.get("percent") or 0)
        level = str(data.get("level") or "ok")
        used = data.get("used_mb") or 0
        limit = data.get("limit_mb") or 0

        self.detail_label.setText(f"{percent:.2f}% | {used} MB de {limit} MB")
        self.progress.setValue(max(0, min(100, int(round(percent)))))
        self.level_badge.setText(_level_label(level))
        self.level_badge.setStyleSheet(_badge_style(level))
        self.progress.setStyleSheet(_progress_style(_level_color(level)))


class CloudBackupPage(QFrame):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.status_payload: dict | None = None
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        heading = QLabel("Nuvem e Backup")
        heading.setObjectName("PageTitle")

        subtitle = QLabel("Acompanhe o uso da nuvem e gere uma cÃ³pia completa do banco e das fotos.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)

        hero_card = QFrame()
        style_card(hero_card)
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(14)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(6)

        overline = QLabel("NUVEM E BACKUP")
        overline.setObjectName("CardTitle")
        self.summary_label = QLabel("CARREGANDO STATUS DA NUVEM...")
        self.summary_label.setObjectName("CloudSummaryLabel")
        self.generated_label = QLabel("")
        self.generated_label.setObjectName("MutedText")

        title_wrap.addWidget(overline)
        title_wrap.addWidget(self.summary_label)
        title_wrap.addWidget(self.generated_label)

        self.backup_button = AnimatedButton("BACKUP")
        self.backup_button.setIcon(make_icon("reports", "#E7EBF0", "#4F5B69"))
        self.backup_button.setMinimumWidth(154)
        self.backup_button.clicked.connect(self.create_backup)

        self.refresh_button = AnimatedButton("ATUALIZAR")
        self.refresh_button.setIcon(make_icon("dashboard", "#E7EBF0", "#4F5B69"))
        self.refresh_button.setMinimumWidth(154)
        self.refresh_button.clicked.connect(self.refresh)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.backup_button)

        top_row.addLayout(title_wrap, 1)
        top_row.addLayout(actions, 0)

        cards = QGridLayout()
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setSpacing(14)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)

        self.database_card = UsageCard("BANCO SUPABASE")
        self.storage_card = UsageCard("FOTOS/STORAGE")
        cards.addWidget(self.database_card, 0, 0)
        cards.addWidget(self.storage_card, 0, 1)

        hero_layout.addLayout(top_row)
        hero_layout.addLayout(cards)

        note = QLabel("O backup baixa um arquivo ZIP com os dados do banco, fotos e manifesto de restauraÃ§Ã£o.")
        note.setObjectName("SectionCaption")
        note.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(subtitle)
        layout.addWidget(hero_card)
        layout.addWidget(note)
        layout.addStretch(1)

    def set_loading_state(self, loading: bool):
        self.backup_button.setDisabled(loading)
        self.refresh_button.setDisabled(loading)
        if loading:
            self.summary_label.setText("ATUALIZANDO STATUS DA NUVEM...")

    def refresh(self):
        self.status_payload = self.api_client.get_cloud_storage_status()
        self._render_status(self.status_payload)

    def create_backup(self):
        default_dir = Path.home() / "Downloads"
        if not default_dir.exists():
            default_dir = Path.cwd()

        target_dir = QFileDialog.getExistingDirectory(self, "Salvar backup em", str(default_dir))
        if not target_dir:
            return

        self.set_loading_state(True)
        self.summary_label.setText("GERANDO BACKUP COMPLETO...")
        try:
            backup = self.api_client.create_cloud_backup()
            output_path = Path(target_dir) / backup["filename"]
            self.summary_label.setText("BAIXANDO BACKUP...")
            self.api_client.download_cloud_backup(backup["download_url"], str(output_path))
            self.status_payload = backup.get("storage_status") or self.status_payload
            if self.status_payload:
                self._render_status(self.status_payload)
            show_notice(self, "Backup concluÃ­do", f"Arquivo salvo em:\n{output_path}", icon_name="reports")
        except Exception as exc:
            show_notice(self, "Falha no backup", str(exc), icon_name="warning")
            if self.status_payload:
                self._render_status(self.status_payload)
        finally:
            self.set_loading_state(False)

    def _render_status(self, payload: dict):
        database = payload.get("database", {})
        storage = payload.get("storage", {})
        self.database_card.set_usage(database)
        self.storage_card.set_usage(storage)

        db_percent = float(database.get("percent") or 0)
        storage_percent = float(storage.get("percent") or 0)
        levels = {database.get("level") or "ok", storage.get("level") or "ok"}
        state = "OK" if levels == {"ok"} else "ATENÃ‡ÃƒO"
        self.summary_label.setText(f"{state} | BANCO {db_percent:.2f}% | FOTOS {storage_percent:.2f}%")

        backend = str(payload.get("storage_backend") or "storage")
        self.generated_label.setText(f"Armazenamento: {backend.upper()}")


def _level_label(level: str) -> str:
    return {
        "ok": "OK",
        "amarelo": "ALERTA",
        "vermelho": "ALTO",
        "critico": "CRÃTICO",
    }.get(level, "OK")


def _level_color(level: str) -> str:
    return {
        "ok": "#5B6571",
        "amarelo": "#6A7079",
        "vermelho": "#7A6666",
        "critico": "#5A4D4D",
    }.get(level, "#5B6571")


def _badge_style(level: str) -> str:
    color = _level_color(level)
    return (
        f"background:#E9EDF2; color:{color}; border:1px solid rgba(91, 101, 113, 0.24); "
        "border-radius:8px; padding:6px 10px; font-size:12px; font-weight:800;"
    )


def _progress_style(color: str) -> str:
    return f"""
        QProgressBar {{
            background: #DEE3E9;
            border: none;
            border-radius: 6px;
        }}
        QProgressBar::chunk {{
            background: {color};
            border-radius: 6px;
        }}
    """


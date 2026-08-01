from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
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
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("ContentSurface")
        self.title = title
        self.shortcut_rows = [row for row in shortcuts if row[2] in allowed_pages]

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


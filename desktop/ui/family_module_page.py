from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from theme import style_card, style_table_card


class FamilyModulePage(QFrame):
    """Shell de navegação para uma família operacional.

    A Etapa 1 cria somente a estrutura visual. Os controles de paradas,
    manutenções e ordens serão ligados nas etapas seguintes, usando as
    estruturas de dados já existentes.
    """

    def __init__(self, family: str, parent=None):
        super().__init__(parent)
        self.family = str(family or "").strip().upper() or "FAMILIA"
        self.setObjectName("ContentSurface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel(f"GEST\u00c3O {self.family}")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            f"Central de controle da familia {self.family}. "
            "As telas de operacao, paradas e manutencao serao organizadas aqui."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        identity_card = QFrame()
        style_card(identity_card)
        identity_layout = QHBoxLayout(identity_card)
        identity_layout.setContentsMargins(18, 16, 18, 16)
        identity_layout.setSpacing(16)
        family_caption = QLabel("FAMILIA OPERACIONAL")
        family_caption.setObjectName("SectionCaption")
        family_value = QLabel(self.family)
        family_value.setObjectName("SectionTitle")
        family_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        identity_layout.addWidget(family_caption)
        identity_layout.addStretch()
        identity_layout.addWidget(family_value)
        layout.addWidget(identity_card)

        section_title = QLabel("SUBTELAS DO MODULO")
        section_title.setObjectName("SectionTitle")
        section_caption = QLabel(
            "A mesma base operacional sera usada para RTG e LBS, "
            "com navegacao separada para cada equipe."
        )
        section_caption.setObjectName("SectionCaption")
        section_caption.setWordWrap(True)
        layout.addWidget(section_title)
        layout.addWidget(section_caption)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        modules = (
            ("01", "PAINEL OPERACIONAL", "Resumo de disponibilidade e situacao da familia."),
            ("02", "CONTROLE DE PARADAS", "Inicio, fim, motivo e horas paradas por equipamento."),
            ("03", "MANUTENCOES", "Preventivas, corretivas e servicos direcionados."),
            ("04", "ORDENS DE SERVICO", "Acompanhar abertura, execucao e conclusao das OS."),
            ("05", "PCM", "Planejamento, agenda e backlog da familia."),
            ("06", "HISTORICO", "Linha do tempo de ocorrencias e intervencoes."),
        )
        for index, (number, label_text, description) in enumerate(modules):
            card = QFrame()
            style_table_card(card)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(6)
            number_label = QLabel(number)
            number_label.setObjectName("SectionCaption")
            label = QLabel(label_text)
            label.setObjectName("SectionTitle")
            description_label = QLabel(description)
            description_label.setObjectName("SectionCaption")
            description_label.setWordWrap(True)
            card_layout.addWidget(number_label)
            card_layout.addWidget(label)
            card_layout.addWidget(description_label)
            grid.addWidget(card, index // 2, index % 2)
            grid.setColumnStretch(index % 2, 1)

        layout.addLayout(grid)
        layout.addStretch(1)

        note = QLabel(
            "Etapa 1 concluida: navegacao criada. Nenhum lancamento foi alterado e nenhuma tabela nova foi criada."
        )
        note.setObjectName("SectionCaption")
        note.setWordWrap(True)
        layout.addWidget(note)

    def refresh(self):
        """Mantem a pagina pronta para o ciclo de refresh do Desktop."""

        return None

# Fase 1 - Fundacao Visual Global (Desktop)

Data: 2026-04-23
Status: concluida

## Objetivo
Padronizar a camada visual base do desktop sem alterar banco, regras de negocio, modulos, navegacao funcional ou integracoes.

## Aplicado no tema global
Arquivo principal:
- `desktop/theme.py`

Controles base padronizados:
- botoes (`QPushButton`)
- campos de texto (`QLineEdit`, `QTextEdit`)
- combobox (`QComboBox`)
- checkbox (`QCheckBox`)
- abas (`QTabWidget`, `QTabBar`)
- tabelas e cabecalhos (`QTableWidget`, `QHeaderView`)
- barras de rolagem (`QScrollBar`)
- data/numero (`QDateEdit`, `QSpinBox`, `QDoubleSpinBox`)
- menu classico (`QMenuBar`, `QMenu`)
- arvore lateral (`QTreeWidget`, `QTreeView`)
- area MDI (`QMdiArea`)
- agrupadores (`QGroupBox`)
- tooltips e caixas de mensagem (`QToolTip`, `QMessageBox`)

## Diretriz visual consolidada
- paleta neutra corporativa (cinza ERP classico)
- baixo contraste agressivo e baixo ruido
- borda reta e pequena (`border-radius: 2px`)
- foco em legibilidade e previsibilidade operacional

## Garantias de escopo
- nenhuma alteracao de regras de negocio
- nenhuma alteracao de banco de dados
- nenhuma alteracao de endpoint/integracao
- nenhuma alteracao de fluxo funcional


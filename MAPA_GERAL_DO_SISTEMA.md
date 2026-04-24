# MAPA GERAL DO SISTEMA - CHECKLIST FROTA

Data: 2026-04-24
Objetivo: centralizar em um arquivo unico a visao completa do sistema (arquitetura, modulos, fluxos, arquivos-chave e operacao).

## 1) Visao geral

O sistema e dividido em 3 camadas:

1. `backend/`:
API Flask + SQLAlchemy, regras de negocio e acesso a banco.
2. `desktop/`:
App PySide6 para operacao administrativa e gestao.
3. `web_app/`:
Interface web/mobile para uso operacional em navegador.

Arquivos de apoio:
- `README.md`: resumo geral e comandos principais.
- `requirements.txt`: dependencias Python.
- `abrir_checklist_frota.bat` e `abrir_desktop_nuvem.bat`: atalhos de execucao no Windows.

## 2) Entrada do sistema (onde tudo comeca)

### Desktop
- Entrada principal: `desktop/main.py`
- Janela de login: `desktop/ui/login_window.py`
- Janela principal e navegacao: `desktop/ui/main_window.py`

### Backend
- Bootstrap local: `backend/run.py`
- App factory/config: `backend/app/__init__.py`
- WSGI: `backend/wsgi.py` e `backend/app/wsgi.py`

### Web app
- Pagina principal: `web_app/index.html`
- JS principal: `web_app/static/js/app.js`
- Estilos web: `web_app/static/css/styles.css`

## 3) Backend detalhado

### 3.1 Estrutura central
- Configuracao: `backend/app/config.py`
- Extensoes (db, etc.): `backend/app/extensions.py`
- Modelos: `backend/app/models/`
- Rotas: `backend/app/routes/`
- Servicos de negocio/exportacao: `backend/app/services/`

### 3.2 Modelos principais
- `vehicle.py`: frota/equipamentos
- `user.py`: usuarios e perfis
- `checklist.py`: execucao de checklist
- `checklist_catalog_item.py`: itens configuraveis do checklist
- `mechanic_non_conformity.py`: ocorrencias e tratativas
- `activity.py`: atividades em massa
- `material.py`: materiais/estoque
- `maintenance.py`: manutencao/programacao
- `wash.py`: lavagens/fila/cronograma

### 3.3 Rotas (API por modulo)
- Auth: `auth.py`
- Veiculos: `vehicles.py`
- Usuarios: `users.py`
- Checklist e catalogo: `checklist.py`
- Nao conformidades: `non_conformities.py`
- Nao conformidades mecanico: `mechanic_non_conformities.py`
- Atividades: `activities.py`
- Materiais: `materials.py`
- Manutencao: `maintenance.py`
- Lavagens: `washes.py`
- Relatorios: `reports.py`
- Upload: `upload.py`
- Admin/utilitarios: `admin.py`

### 3.4 Servicos de negocio relevantes
- Regras de checklist: `backend/app/services/checklist_catalog.py`
- Relatorios gerais: `backend/app/services/report_service.py`
- Exportacao PDF manutencao: `backend/app/services/maintenance_pdf_export_service.py`
- Exportacao PDF lavagem: `backend/app/services/wash_pdf_export_service.py`
- Importacao de inventario: `backend/app/services/inventory_import_service.py`
- Backup: `backend/app/services/backup_service.py`

## 4) Desktop detalhado

### 4.1 Camada de UI por modulo
- Dashboard: `desktop/ui/dashboard_page.py`
- Ocorrencias: `desktop/ui/non_conformities_page.py`
- Produtividade: `desktop/ui/productivity_page.py`
- Frota/Equipamentos: `desktop/ui/equipment_page.py`
- Checklist (itens): `desktop/ui/checklist_items_page.py`
- Materiais: `desktop/ui/materials_page.py`
- Lavagens: `desktop/ui/washes_page.py`
- Atividades: `desktop/ui/activities_page.py`
- Manutencao: `desktop/ui/maintenance_page.py`
- Relatorios: `desktop/ui/reports_page.py`
- Logins: `desktop/ui/users_page.py`
- Backup nuvem: `desktop/ui/cloud_backup_page.py`

### 4.2 Componentes compartilhados
- Dialogos de confirmacao/aviso: `desktop/components/confirmation_dialog.py`
- Botoes animados: `desktop/components/animated_button.py`
- Painel de imagens: `desktop/components/image_panel.py`
- Skeleton de tabela: `desktop/components/table_skeleton.py`
- Overlay de loading: `desktop/components/loading_overlay.py`
- Fabrica de icones: `desktop/components/icon_factory.py`
- Progresso de exportacao: `desktop/components/export_progress.py`

### 4.3 Tema e estilo global
- Tema QSS e utilitarios: `desktop/theme.py`
- Aplicacao do tema no app: `desktop/main.py` e `desktop/ui/main_window.py`

## 5) Web app detalhado

Arquivos principais:
- `web_app/index.html`
- `web_app/acesso.html`
- `web_app/entrar-direto.html`
- `web_app/static/js/app.js`
- `web_app/static/js/config.js`
- `web_app/static/css/styles.css`
- `web_app/service-worker.js`
- `web_app/manifest.json`

## 6) Fluxos de negocio (resumo operacional)

### 6.1 Checklist e ocorrencias
1. Usuario executa checklist.
2. Item com problema gera nao conformidade (com foto antes obrigatoria).
3. Gestao acompanha em Ocorrencias, Relatorios e Dashboard.
4. Resolucao pode ocorrer via tratativa direta ou atividade em massa.

### 6.2 Atividades em massa
1. Criacao da atividade por modulo/item.
2. Selecao de varios equipamentos.
3. Atualizacao por equipamento (instalado/nao instalado/pendente, evidencia).
4. Exportacoes CSV/XLSX/PDF e mensagem operacional.

### 6.3 Lavagens
1. Fila e cronograma mensal.
2. Confirmacao de cumprimento por turno (OK/X).
3. Replanejamento, bloqueio/liberacao de dia e exportacoes.

### 6.4 Manutencao
1. Programacao por calendario.
2. Aplicacao de mecanico/material e acompanhamento.
3. Relatorio executivo e exportacao.

## 7) Dados e banco

Padrao esperado:
- Produção: PostgreSQL via `DATABASE_URL`
- Desenvolvimento: fallback SQLite local quando aplicavel

Importacao inicial de frota:
- Arquivo de inventario Excel (abas `CARRETAS` e `CAVALOS`)
- Pode ser acionado pelo backend e pela tela de Equipamentos no desktop.

## 8) Execucao e operacao

### 8.1 Backend local
1. `cd backend`
2. `python run.py`

### 8.2 Desktop
1. `python desktop/main.py`
2. Ou use `abrir_checklist_frota.bat` / `abrir_desktop_nuvem.bat`

### 8.3 Web app
1. `cd web_app`
2. `python -m http.server 5500`

## 9) Testes e validacao

Suites uteis:
- `tests/test_desktop_navigation.py`: navegacao e atualizacao de telas.
- `tests/test_export_service.py`: exportacoes.
- `tests/test_message_service.py`: mensagens.
- `tests/test_severity_service.py`: severidade e status.

Documentacao de homologacao e regressao:
- `desktop/docs/FASE0_CHECKLIST_REGRESSAO_FUNCIONAL.md`
- `desktop/docs/FASE7_HOMOLOGACAO_GO_LIVE.md`

## 10) Onde mexer em cada demanda (guia rapido)

- Mudanca visual global desktop: `desktop/theme.py`
- Mudanca de navegacao desktop: `desktop/ui/main_window.py`
- Mudanca de login desktop: `desktop/ui/login_window.py`
- Mudanca de regras de checklist: `backend/app/services/checklist_catalog.py`
- Mudanca de endpoint/API: `backend/app/routes/*.py`
- Mudanca de modelo de dados: `backend/app/models/*.py`
- Mudanca de exportacao PDF/Excel: `backend/app/services/*export*` e `desktop/services/*export*`
- Mudanca web/mobile: `web_app/static/js/app.js` e `web_app/static/css/styles.css`

## 11) Observacoes praticas de manutencao

- Projeto em Windows/OneDrive pode sofrer com lock/permissao em arquivos temporarios.
- Em testes de exportacao, falhas de `WinError 5` normalmente sao de ambiente e nao de regra.
- Para alteracoes visuais no desktop, sempre validar:
  1. Dashboard
  2. Frota
  3. Logins
  4. Relatorios
  5. Lavagens e Atividades

## 12) Resumo final

Se voce precisar entender o sistema inteiro rapidamente:
1. Leia `README.md`.
2. Leia este arquivo (`MAPA_GERAL_DO_SISTEMA.md`).
3. Abra `desktop/ui/main_window.py` para ver os modulos.
4. Siga para `backend/app/routes/` e `backend/app/models/` para regra e dados.


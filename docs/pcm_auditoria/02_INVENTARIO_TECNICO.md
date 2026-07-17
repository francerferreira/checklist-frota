# Inventario tecnico

## Metodo e limite

Inventario feito por leitura integral do escopo e varredura read-only do repositorio. Foram encontrados 264 arquivos versionados no inicio do ciclo. Nao foram alterados codigo, banco, models, migrations, APIs, services, telas ou regras.

O schema fisico e os dados do PostgreSQL de producao nao foram consultados. Assim, "tabela existente" neste documento significa declarada em model/migration, salvo indicacao contraria.

## Dimensao do codigo

| Area | Arquivos Python/JS/HTML/CSS | Linhas aproximadas | Papel |
|---|---:|---:|---|
| `backend/app/` | 79 | 12.601 | API, regras, persistencia, relatorios |
| `desktop/` | 46 | 23.004 | gestao Desktop PySide6 |
| `web_app/` | 23 | 33.621 | Web Mobile/PWA e legados JS |
| `migrations/` | 11 | 752 | Alembic/Flask-Migrate |
| `tests/` | 33 | aproximadamente 3.400 | pytest e Playwright |
| `tools/` | 5 | aproximadamente 2.100 | apoio operacional e protecao |

## Tecnologias e dependencias

- Python, Flask 3.1.3, Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.36.
- Flask-Migrate 4.1.0/Alembic.
- PostgreSQL via psycopg2-binary 2.9.10; SQLite local como fallback.
- PySide6 6.11.0 no Desktop.
- HTML/CSS/JavaScript sem framework no Web Mobile, Service Worker e IndexedDB.
- ReportLab e openpyxl para PDF/Excel.
- Requests para Supabase Storage.
- Gunicorn/Waitress, Render, PyInstaller.
- pytest e Playwright para testes.
- Fonte: `requirements.txt`, `render.yaml`, `backend/app/config.py`.

## Pastas principais

| Pasta | Conteudo | Evidencia |
|---|---|---|
| `backend/app/models/` | 46 tabelas declaradas | atributos `__tablename__` |
| `backend/app/routes/` | 22 blueprints, 149 endpoints | decoradores `@bp.get/post/put/delete` |
| `backend/app/services/` | regras de negocio e integracoes | funcoes de servico |
| `desktop/ui/` | 20 paginas gerenciais | `MainWindow._build_pages()` |
| `web_app/` | 13 telas/secoes operacionais principais | `<section id=...>` em `index.html` |
| `migrations/versions/` | baseline + 9 evolucoes lineares | `revision`/`down_revision` |
| `tests/` | 32 arquivos de teste | nomes listados abaixo |
| `.github/` | automacao do repositorio | workflows versionados |

## Models e tabelas

### Nucleo e cadastro

- `User` -> `users`, em `backend/app/models/user.py`.
- `Vehicle` -> `vehicles`, em `backend/app/models/vehicle.py`.
- `EquipmentFamily`, `OperationalLocation`, `EquipmentProfile`, `EquipmentLink` -> `equipment_families`, `operational_locations`, `equipment_profiles`, `equipment_links`, em `equipment_structure.py`.
- `SystemSetting` -> `system_settings`.
- `RevokedToken` -> `revoked_tokens`.

### Checklist, atividades e nao conformidades

- `Checklist`, `ChecklistItem`, `ChecklistCatalogItem` -> `checklists`, `checklist_items`, `checklist_catalog_items`.
- `Activity`, `ActivityItem`, `ActivityNonConformityLink` -> `activities`, `activity_items`, `activity_non_conformity_links`.
- `MechanicNonConformity` -> `mechanic_non_conformities`.
- `ResolutionPackage`, `ResolutionPackageLink` -> `resolution_packages`, `resolution_package_links`.

### PCM, OS e operacao

- `EquipmentOperationalState`, `EquipmentStatusEvent`, `HourmeterReading` -> `equipment_operational_states`, `equipment_status_events`, `hourmeter_readings`.
- `MaintenanceSchedule`, `MaintenanceScheduleItem`, `MaintenanceMaterial`, `MaintenanceWorkOrder` -> `maintenance_schedules`, `maintenance_schedule_items`, `maintenance_materials`, `maintenance_work_orders`.
- `PreventivePlan` -> `preventive_plans`.
- `EmergencyEvent`, `WorkOrderExecution` -> `emergency_events`, `work_order_executions`.
- `InspectionTemplate`, `InspectionTemplateItem`, `InspectionExecution`, `InspectionExecutionItem` -> quatro tabelas `inspection_*`.
- `MobileSyncOperation` -> `mobile_sync_operations`.
- `AutomationExecution` -> `automation_executions`.

### Materiais, biblioteca e lavagem

- `Material`, `MaterialMovement` -> `materials`, `material_movements`.
- `Warehouse`, `WarehouseStock`, `MaterialFamilyApplication`, `WarehouseReservation`, `TechnicalDocument` -> tabelas de suprimentos/biblioteca.
- `WashQueueItem`, `WashRecord`, `WashPlanConfig`, `WashBlockedDay`, `WashScheduleDecision` -> tabelas `wash_*`.

### Auditoria

- `AuditLog` -> `audit_logs`, com `user_id`, entidade, id, acao, valor anterior, valor novo e data.
- Hooks globais em `audit_service.py`: `_before_flush()`, `_after_flush_postexec()`, `_after_commit()` e `_after_rollback()`.

## Migrations

| Revisao | Finalidade | Dependencia |
|---|---|---|
| `20260712_0000` | schema baseline | nenhuma |
| `20260712_0001` | estrutura de equipamentos | `0000` |
| `20260712_0002` | disponibilidade e horimetro | `0001` |
| `20260712_0003` | inspecoes tecnicas | `0002` |
| `20260712_0004` | emergenciais e OS | `0003` |
| `20260712_0005` | PCM e planos preventivos | `0004` |
| `20260713_0006` | suprimentos e biblioteca | `0005` |
| `20260713_0007` | inteligencia e automacoes | `0006` |
| `20260713_0008` | seguranca e governanca | `0007` |
| `20260713_0009` | operacao mobile por ativo | `0008` |

Risco: `backend/app/__init__.py:create_app()` tambem altera/garante schema em runtime por `db.create_all()` e `ensure_runtime_schema()`. Deve ser comparado com o PostgreSQL antes de nova migration.

## Rotas e APIs

Foram identificados 149 endpoints em blueprints, mais `/health`. Quantidade por arquivo:

| Modulo | Qtd. | Arquivo |
|---|---:|---|
| Atividades | 6 | `routes/activities.py` |
| Administracao | 10 | `routes/admin.py` |
| Autenticacao | 2 | `routes/auth.py` |
| Disponibilidade | 5 | `routes/availability.py` |
| Checklist | 10 | `routes/checklist.py` |
| Emergenciais/OS | 10 | `routes/emergencies.py` |
| Estrutura de equipamentos | 8 | `routes/equipment_structure.py` |
| Inteligencia | 4 | `routes/intelligence.py` |
| Manutencao | 14 | `routes/maintenance.py` |
| Materiais | 7 | `routes/materials.py` |
| NC do mecanico | 3 | `routes/mechanic_non_conformities.py` |
| Operacao mobile | 2 | `routes/mobile_operations.py` |
| Nao conformidades | 3 | `routes/non_conformities.py` |
| PCM | 7 | `routes/pcm.py` |
| Relatorios | 6 | `routes/reports.py` |
| Pacotes de resolucao | 4 | `routes/resolution_packages.py` |
| Suprimentos/biblioteca | 12 | `routes/supply_library.py` |
| Inspecoes tecnicas | 7 | `routes/technical_inspections.py` |
| Upload | 3 | `routes/upload.py` |
| Usuarios | 6 | `routes/users.py` |
| Veiculos/equipamentos | 6 | `routes/vehicles.py` |
| Lavagens | 14 | `routes/washes.py` |

Detalhamento PCM em `06_MAPA_DE_APIS.md`.

## Services principais

- Equipamentos: `equipment_structure_service.py`, `inventory_import_service.py`.
- Disponibilidade/horimetro: `availability_service.py`.
- Manutencao/OS: `maintenance_service.py`, `emergency_service.py`.
- PCM: `pcm_service.py`.
- Inteligencia: `maintenance_intelligence_service.py`.
- Inspecao: `technical_inspection_service.py`.
- Materiais/biblioteca: `supply_library_service.py`, `storage_service.py`.
- Auditoria/seguranca: `audit_service.py`, `auth_service.py`, `backup_service.py`, `security_governance_service.py`.
- Relatorios: `report_service.py`, `export_service.py`, `message_service.py`.
- Legado preservado: checklist, lavagem, atividades, NC e pacotes de resolucao.

## Componentes, templates, telas e dashboards

- Desktop: 20 paginas instanciadas por `MainWindow._build_pages()` em `desktop/ui/main_window.py`.
- PCM Desktop: `PCMPage` e `PreventivePlanDialog` em `desktop/ui/pcm_page.py`.
- Manutencao Desktop: `MaintenancePage` em `desktop/ui/maintenance_page.py`.
- Disponibilidade Desktop: `AvailabilityPage`.
- Web Mobile: `web_app/index.html` + `web_app/static/js/app.js` + `styles.css`.
- Dashboard atual: `DashboardPage` consome `/relatorios/dashboard`.
- Inteligencia de manutencao: `/relatorios/manutencao-executivo` usa `build_maintenance_intelligence_overview()`.
- Relatorios: macro, micro, item, produtividade, historico de veiculo, manutencao PDF e OS PDF.
- Nao existem templates Flask/Jinja de negocio; o frontend web e estatico.

## Jobs e automacoes

- Existe endpoint `POST /inteligencia/automacoes/executar-agendada`, protegido por `AUTOMATION_JOB_TOKEN`.
- Existem regras para emergencia critica, preventiva vencida e estoque minimo em `_automation_candidates()`.
- `render.yaml` nao declara cron job. A execucao automatica depende de agente externo nao comprovado.
- `generate_due_preventives()` so foi encontrado na rota PCM e no botao Desktop; nao ha job comprovado para gerar OS preventivas automaticamente.

## Integracoes

- PostgreSQL/Supabase por `DATABASE_URL`.
- Supabase Storage por API REST em `storage_service.py`; fallback local.
- Render Web Service e Static Site em `render.yaml`.
- Excel externo por openpyxl: inventario de carretas/cavalos e controle de lavagem.
- QR/NFC via Web APIs no PWA; QR usa camera e NFC depende de suporte do navegador/dispositivo.
- Nao foi encontrado provedor de envio de WhatsApp/e-mail; existem apenas textos/relatorios de apoio.

## Variaveis de ambiente

`SECRET_KEY`, `DATABASE_URL`, `TOKEN_MAX_AGE_SECONDS`, `CORS_STRICT_MODE`, `CORS_ALLOWED_ORIGINS`, `AUTOMATION_JOB_TOKEN`, `API_BASE_URL`, `INVENTORY_FILE`, `WASH_CONTROL_FILE`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `STORAGE_BACKEND`, `FREE_DB_LIMIT_MB`, `FREE_STORAGE_LIMIT_MB`, `BACKUP_FOLDER`. Evidencia: `.env.example`, `render.yaml`, `backend/app/config.py`.

## Testes existentes

33 arquivos cobrem auditoria, disponibilidade, checklist, navegacao Desktop, emergenciais/OS, estrutura de equipamentos, exportacao, arquivos externos, inteligencia, mensagens, operacao mobile, PCM, migrations 2/3/4/5/6/7/9/11, seguranca, severidade, suprimentos, inspecoes, fuso horario, upload, veiculos, Web Mobile/Playwright e ferramentas de protecao da Fase 1.

Lacunas de teste: concorrencia de numero de OS, cancelamento/reabertura, correcao de horimetro, ciclos 500-6000 h, faixas de backlog, disponibilidade por periodo total, paradas sobrepostas, Base Mestre/Power BI e importacao RTG/LBS com rollback.

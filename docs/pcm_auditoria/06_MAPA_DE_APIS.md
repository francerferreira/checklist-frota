# Mapa de APIs

## Convencoes

- Autenticacao padrao: `Authorization: Bearer <token>` via `auth_required()` em `backend/app/services/auth_service.py`.
- Publicos: `GET /health` e `POST /login`. Logout exige token.
- Perfis atuais: `admin`, `gestor`, `mecanico`, `motorista`.
- Total encontrado: 153 endpoints em 22 blueprints, mais `/health`.

## Saude e autenticacao

| Metodo | Endpoint | Funcao | Autenticacao | Permissao | Service/Model | Situacao |
|---|---|---|---|---|---|---|
| GET | `/health` | `health()` | Publica | - | `SELECT 1`, `audit_runtime_status()` | Implementado |
| POST | `/login` | login | Publica | usuario ativo | `User`, token assinado | Implementado |
| POST | `/logout` | logout | Bearer | autenticado | `revoke_token()`, `RevokedToken` | Implementado |

## Equipamentos e estrutura

| Metodo | Endpoint | Funcao | Autenticacao | Permissao | Service/Model | Situacao |
|---|---|---|---|---|---|---|
| GET | `/veiculos` | `list_vehicles()` | Bearer | autenticado | `Vehicle` | Reaproveitar |
| GET | `/veiculos/{id}/historico` | `vehicle_history()` | Bearer | autenticado | `build_vehicle_history()` | Parcial PCM |
| POST | `/veiculos` | `create_vehicle()` | Bearer | admin/gestor | `Vehicle`, `apply_equipment_profile()` | Reaproveitar |
| PUT | `/veiculos/{id}` | `update_vehicle()` | Bearer | admin/gestor | profile/link sync | Reaproveitar |
| DELETE | `/veiculos/{id}` | `retire_vehicle()` | Bearer | admin/gestor | inativacao logica | Reaproveitar |
| POST | `/veiculos/importar-inventario` | `import_inventory()` | Bearer | admin/gestor | `import_inventory_data()` | Parcial; so carreta/cavalo |
| GET | `/equipamentos/estrutura` | estrutura | Bearer | autenticado | familias/locais | Implementado |
| POST/PUT | `/equipamentos/familias[/{id}]` | criar/editar familia | Bearer | admin/gestor | `EquipmentFamily` | Implementado |
| POST/PUT | `/equipamentos/locais[/{id}]` | criar/editar local | Bearer | admin/gestor | `OperationalLocation` | Implementado |
| GET | `/equipamentos/{id}/movimentos-localizacao` | consultar historico de local | Bearer | autenticado | `build_equipment_location_history()` | Implementado 3A.1 |
| POST | `/equipamentos/{id}/movimentos-localizacao` | movimentar equipamento | Bearer | admin/gestor | `move_equipment_location()` | Implementado 3A.1 |
| GET/POST | `/equipamentos/vinculos` | listar/criar vinculo | Bearer | leitura autenticada; escrita admin/gestor | `EquipmentLink` | Implementado |
| PUT | `/equipamentos/vinculos/{id}/encerrar` | encerrar vinculo | Bearer | admin/gestor | `EquipmentLink` | Implementado |

## Gestao e Base Mestre

| Metodo | Endpoint | Funcao | Autenticacao | Permissao | Service/Model | Situacao |
|---|---|---|---|---|---|---|
| GET | `/relatorios/base-mestre` | consulta paginada de intervencoes | Bearer | admin/gestor | `build_management_master_base()` | Implementado Fase 5 |
| GET | `/relatorios/base-mestre/exportar` | exporta JSON, CSV ou XLSX | Bearer | admin/gestor | `build_management_master_export()` | Implementado Fase 5 |

## Disponibilidade e horimetro

| Metodo | Endpoint | Funcao | Autenticacao | Permissao | Service | Model/Tabela | Situacao |
|---|---|---|---|---|---|---|---|
| GET | `/disponibilidade/visao` | `availability_overview()` | Bearer | autenticado | `build_availability_overview()` | status/events | Regra parcial |
| PUT | `/equipamentos/{id}/status-operacional` | `update_operational_status()` | Bearer | autenticado | `set_operational_status()` | state/events | Implementado |
| GET | `/equipamentos/{id}/status-historico` | `status_history()` | Bearer | autenticado | `list_status_history()` | events | Implementado |
| POST | `/equipamentos/{id}/horimetros` | `create_hourmeter_reading()` | Bearer | autenticado | `record_hourmeter()` | readings/state | Implementado |
| GET | `/equipamentos/{id}/horimetros` | `hourmeter_history()` | Bearer | autenticado | `list_hourmeter_readings()` | readings | Implementado |

Gap: nao existe endpoint de correcao/aprovacao de horimetro nem endpoint central em lote.

## PCM

| Metodo | Endpoint | Funcao | Autenticacao | Permissao | Service | Model | Situacao |
|---|---|---|---|---|---|---|---|
| GET | `/pcm/agenda` | `pcm_agenda()` | Bearer | admin/gestor | `build_pcm_agenda()` | plans/schedules | Implementado |
| GET | `/pcm/backlog` | `pcm_backlog()` | Bearer | admin/gestor | `build_backlog()` | work orders | Parcial |
| GET | `/pcm/planos-preventivos` | lista | Bearer | admin/gestor | `list_preventive_plans()` | `PreventivePlan` | Implementado |
| GET | `/pcm/planos-preventivos/{id}` | detalhe | Bearer | admin/gestor | `get_preventive_plan()` | `PreventivePlan` | Implementado |
| POST | `/pcm/planos-preventivos` | cria | Bearer | admin/gestor | `create_preventive_plan()` | `PreventivePlan` | Implementado |
| PUT | `/pcm/planos-preventivos/{id}` | altera | Bearer | admin/gestor | `update_preventive_plan()` | `PreventivePlan` | Implementado |
| POST | `/pcm/gerar-preventivas` | gera OS vencidas | Bearer | admin/gestor | `generate_due_preventives()` | schedules/items/OS | Manual; nao agendado |

## Manutencao e corretiva programada

| Metodo | Endpoint | Permissao | Service principal | Situacao PCM |
|---|---|---|---|---|
| GET | `/manutencao/visao` | admin/gestor/mecanico | `build_maintenance_overview()` | Reaproveitar |
| GET | `/manutencao/mecanico` | workspace; mecanico ve o proprio | `mechanic_items_for_user()` | Reaproveitar |
| GET | `/manutencao/programacoes` | workspace | query schedules | Reaproveitar |
| GET | `/manutencao/relatorio/pdf` | workspace | `build_maintenance_report_payload()` | Reaproveitar |
| GET | `/manutencao/os/{id}/pdf` | workspace | `build_work_order_report_payload()` | Reaproveitar |
| POST | `/manutencao/programacoes` | admin/gestor | `create_maintenance_schedule()` | Parcial tipo oficial |
| POST | `/manutencao/sugestao-responsavel` | admin/gestor | `suggest_mechanic_for_payload()` | Apoio |
| POST | `/manutencao/sugestao-agenda` | admin/gestor | `suggest_schedule_window()` | Apoio |
| GET | `/manutencao/programacoes/{id}/sugestao-peca` | admin/gestor | `suggest_material_for_schedule()` | Apoio |
| POST | `/manutencao/programacoes/sincronizar-nc` | admin/gestor | sync NC | Legado integrado |
| POST | `/manutencao/programacoes/{id}/materiais` | admin/gestor | `link_schedule_material()` | Reaproveitar |
| PUT | `/manutencao/programacoes/{id}/cronograma` | admin/gestor | `program_maintenance_schedule()` | Reaproveitar |
| PUT | `/manutencao/itens/{id}/reprogramar` | admin/gestor/mecanico conforme regra | `reprogram_schedule_item()` | Reaproveitar |
| PUT | `/manutencao/itens/{id}` | workspace/atribuicao | `update_schedule_item()` | Reaproveitar; conclui preventiva |

## Emergenciais e ciclo da OS

| Metodo | Endpoint | Permissao | Service | Situacao |
|---|---|---|---|---|
| GET/POST | `/emergenciais` | workspace/autenticado conforme acao | listar/`create_emergency()` | Implementado |
| GET | `/emergenciais/{id}` | workspace | `get_emergency()` | Implementado |
| PUT | `/emergenciais/{id}/triagem` | admin/gestor | `triage_emergency()` | Implementado |
| POST | `/emergenciais/{id}/converter-os` | admin/gestor | `convert_emergency_to_work_order()` | Implementado |
| GET | `/ordens-servico/{id}` | workspace e atribuicao | `get_work_order()` | Implementado |
| PUT | `/ordens-servico/{id}/iniciar` | workspace e atribuicao | `start_work_order()` | Implementado |
| PUT | `/ordens-servico/{id}/concluir-reparo` | workspace e atribuicao | `complete_repair()` | Implementado |
| PUT | `/ordens-servico/{id}/teste` | workspace e atribuicao | `record_operational_test()` | Implementado |
| PUT | `/ordens-servico/{id}/liberar` | workspace e atribuicao | `release_work_order()` | Implementado |

Gap: nao existem endpoints formais para cancelar ou reabrir OS.

## Operacao mobile por ativo

| Metodo | Endpoint | Permissao | Service/Model | Situacao |
|---|---|---|---|---|
| GET | `/operacao-mobile/ativos/{access_code}` | Bearer | `resolve_mobile_asset()` | Implementado QR/NFC |
| POST | `/operacao-mobile/sincronizar` | Bearer + regra por operacao/OS | `sync_mobile_operation()`, `MobileSyncOperation` | Implementado offline/conflito |

Operacoes aceitas: `HORIMETRO`, `EMERGENCIA`, `OS_INICIAR`, `OS_CONCLUIR`, `OS_TESTAR`, `OS_LIBERAR`.

## Relatorios, inteligencia e auditoria

| Metodo | Endpoint | Permissao | Service | Situacao |
|---|---|---|---|---|
| GET | `/relatorios/dashboard` | autenticado | `build_dashboard_summary()` | Implementado legado |
| GET | `/relatorios/produtividade` | autenticado | `build_productivity_report()` | Implementado |
| GET | `/relatorios/manutencao-executivo` | admin/gestor | `build_maintenance_intelligence_overview()` | Parcial PCM |
| GET | `/relatorios/macro` | autenticado | `build_macro_report()` | Implementado |
| GET | `/relatorios/micro` | autenticado | `build_micro_report()` | Implementado |
| GET | `/relatorios/item` | autenticado | `build_item_report()` | Implementado |
| GET | `/inteligencia/automacoes` | admin/gestor | `list_automation_alerts()` | Implementado |
| POST | `/inteligencia/automacoes/avaliar` | admin/gestor | `evaluate_automation_rules()` | Manual |
| POST | `/inteligencia/automacoes/executar-agendada` | token de job | mesmo servico | Endpoint pronto; job nao comprovado |
| PUT | `/inteligencia/automacoes/{id}/reconhecer` | admin/gestor | `acknowledge_automation_alert()` | Implementado |
| GET | `/admin/audit-logs` | admin | `AuditLog` | Implementado |
| GET | `/admin/audit-health` | admin | `audit_runtime_status()` | Implementado |

## Upload e biblioteca

| Metodo | Endpoint | Permissao | Service | Situacao |
|---|---|---|---|---|
| POST | `/upload` | Bearer | storage local/Supabase | Implementado parcial |
| GET | `/uploads/supabase/{path}` | conforme rota autenticada | download Supabase | Implementado |
| GET | `/uploads/{filename}` | conforme rota autenticada | arquivo local | Implementado |
| GET/POST/PUT | `/biblioteca-tecnica[...]` | leitura/gestao por perfil | `supply_library_service.py` | Implementado |

## Inventario dos demais blueprints preservados

| Modulo | Endpoints | Papel | Decisao |
|---|---:|---|---|
| Atividades | 6 | inspecoes/atividades e materiais | preservar e integrar por origem |
| Checklist | 10 | configuracao, execucao e historico | preservar |
| Materiais | 7 | CRUD, movimentos e relatorio | preservar |
| NC mecanico | 3 | fila interna do mecanico | preservar |
| Nao conformidades | 3 | consulta/resolucao/conversao | preservar |
| Pacotes de resolucao | 4 | agrupar ocorrencias | preservar |
| Suprimentos/biblioteca | 12 | depositos, estoques, reservas, docs | preservar |
| Inspecoes tecnicas | 7 | templates/versionamento/execucao | preservar |
| Usuarios | 6 | usuarios, mecanicos e senha | preservar; evoluir perfis |
| Lavagens | 14 | agenda, fila, relatorios e mensagens | fora do PCM RTG/LBS; nao apagar |
| Administracao | 10 | auditoria, storage, regras, backup, limpeza | preservar |

## Gaps de contrato

1. Base Mestre paginada em JSON/CSV/Excel para Power BI.
2. Correcao autorizada de horimetro.
3. Movimentacao de localizacao.
4. Cancelamento/reabertura de OS.
5. Execucao centralizada de preventiva e ciclo oficial.
6. Filtros e agregacoes oficiais de backlog/KPIs.
7. Importacao RTG/LBS por lote com preview e rollback.

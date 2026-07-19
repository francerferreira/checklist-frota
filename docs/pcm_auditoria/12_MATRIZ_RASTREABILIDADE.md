# Matriz de rastreabilidade

## Regra de conclusao

Nenhum item foi marcado como "Concluido" neste primeiro ciclo. Mesmo quando o codigo existe, ainda faltam um ou mais itens entre homologacao operacional, comparacao com producao, cobertura de teste, permissao/auditoria especifica ou aceite formal.

Abreviacoes de caminhos: models em `backend/app/models/`, services em `backend/app/services/`, rotas em `backend/app/routes/`, telas Desktop em `desktop/ui/` e Web em `web_app/`.

## Equipamentos

| Requisito | Regra de negocio | Model/Tabela | Service | API | Tela | Teste | Status |
|---|---|---|---|---|---|---|---|
| EQ-01 | cadastro mestre unico | `Vehicle`/`vehicles` | `apply_equipment_profile()` | `/veiculos` | `EquipmentPage` | `test_vehicle_routes.py` | Existente; aceite pendente |
| EQ-02 | familias RTG/LBS/Spreader | `EquipmentFamily` | `seed_equipment_structure()` | `/equipamentos/estrutura` | `EquipmentPage` | `test_equipment_structure_routes.py` | Existente; dados pendentes |
| EQ-03 | campos mestres completos | `Vehicle`, `EquipmentProfile` | `apply_equipment_profile()` | `/veiculos` | `EquipmentPage` | parcial em vehicle routes | Parcial |
| EQ-04 | local atual | `OperationalLocation`, `EquipmentProfile` | `move_equipment_location()` | `/equipamentos/locais` | `EquipmentPage` | estrutura routes | Implementado no backend |
| EQ-05 | historico de movimento | `EquipmentLocationMovement` | `build_equipment_location_history()` | `/equipamentos/{id}/movimentos-localizacao` | tela pendente | `test_equipment_structure_routes.py`, `test_phase3a_location_migration.py` | Implementado no backend; tela Fase 4 |
| EQ-06 | detalhe dinamico por ativo | models existentes | `resolve_mobile_asset()` | `/operacao-mobile/ativos/{code}` | `vehicles-screen` | `test_mobile_operations_routes.py` | Parcial |
| EQ-07 | 22 RTG e 16 LBS homologados | `vehicles`/profiles | - | `/veiculos` | `EquipmentPage` | Ausente para dados reais | Validacao operacional |
| EQ-08 | vinculo LBS-Spreader temporal | `EquipmentLink` | `sync_active_equipment_link()` | `/equipamentos/vinculos` | cadastro | `test_equipment_structure_routes.py` | Existente; homologar regra |

## Ordem de servico

| Requisito | Regra de negocio | Model/Tabela | Service | API | Tela | Teste | Status |
|---|---|---|---|---|---|---|---|
| OS-01 | somente numero da OS; sem MTR/TRM | `MaintenanceWorkOrder.order_number` | `_sync_work_order_for_item()` | APIs de OS/manutencao | Emergenciais/Manutencao | sem teste dedicado a MTR | Existente; aceite pendente |
| OS-02 | numero automatico/concorrente | unique `order_number` | `_sync_work_order_for_item()` | geracao indireta | Manutencao/PCM | sem concorrencia | Parcial |
| OS-03 | campos minimos oficiais | `MaintenanceWorkOrder`, `WorkOrderExecution` | maintenance/emergency services | `/manutencao`, `/ordens-servico` | duas telas | testes de rota parciais | Parcial |
| OS-04 | data/hora e multi-dia | `WorkOrderExecution` | start/complete/release | `/ordens-servico/{id}/*` | Web/desktop | `test_emergency_work_order_routes.py` parcial | Parcial |
| OS-05 | tipos oficiais separados da origem | `source_type` atual | normalizadores atuais | `/manutencao/programacoes` | Manutencao | Ausente | Regra diferente |
| OS-06 | gerar OS da programacao | `MaintenanceWorkOrder` | `sync_work_order_for_item()` | programacao/PCM | Manutencao/PCM | PCM/manutencao parciais | Existente; aceite pendente |
| OS-07 | iniciar/reparar/testar/liberar | `WorkOrderExecution` | `emergency_service.py` | `/ordens-servico/{id}/*` | Web Emergencial | emergency routes | Existente no emergencial |
| OS-08 | cancelar/reabrir com motivo | sem evento/status formal | Ausente | Ausente | Ausente | Ausente | Nao encontrado |
| OS-09 | evidencias completas | paths em execucao | `storage_service.py` | `/upload` | formularios atuais | `test_upload_security.py` | Parcial |

## Corretivas

| Requisito | Regra de negocio | Model/Tabela | Service | API | Tela | Teste | Status |
|---|---|---|---|---|---|---|---|
| CR-01 | abrir emergencial | `EmergencyEvent` | `create_emergency()` | `POST /emergenciais` | Web Emergencial | emergency routes | Existente; aceite pendente |
| CR-02 | triagem e conversao | emergency + work order | `triage_emergency()`, `convert_emergency_to_work_order()` | rotas de triagem/conversao | Desktop Emergenciais | emergency routes | Existente; aceite pendente |
| CR-03 | execucao/teste/liberacao | `WorkOrderExecution` | quatro funcoes de ciclo | rotas `/ordens-servico` | Web/desktop | emergency/mobile routes | Existente; aceite pendente |
| CR-04 | corretiva programada | schedule/item/OS | `create_maintenance_schedule()` | `/manutencao/programacoes` | `MaintenancePage` | testes indiretos | Parcial |
| CR-05 | parada e indicadores | execution/status events | `_reliability_metrics()` | `/relatorios/manutencao-executivo` | Dashboard | intelligence routes | Parcial; formula pendente |
| CR-06 | abrir pelo detalhe do ativo | models existentes | asset/emergency services | asset + emergenciais | PWA | mobile routes | Parcial |

## Preventivas

| Requisito | Regra de negocio | Model/Tabela | Service | API | Tela | Teste | Status |
|---|---|---|---|---|---|---|---|
| PR-01 | gatilho calendario/horimetro/ambos | `PreventivePlan` | `plan_due_state()` | `/pcm/planos-preventivos` | `PCMPage` | `test_pcm_routes.py` | Existente; homologar parametros |
| PR-02 | gerar agenda/item/OS/backlog | plans/schedules/items/OS | `_create_schedule_for_plan()` | `/pcm/gerar-preventivas` | `PCMPage` | PCM routes | Existente; acionamento manual |
| PR-03 | ciclos 500-6000 e reinicio | Ausente como ciclo | Ausente | Ausente | Ausente | Ausente | Nao encontrado |
| PR-04 | faixas automaticas oficiais | campos de proxima leitura | `plan_due_state()` com 3 estados | retorno PCM | `PCMPage` | parcial | Parcial |
| PR-05 | Central unica | models compartilhados | PCM + maintenance services | `/pcm` e `/manutencao` | PCM + Manutencao | navegacao/PCM | Regra diferente |
| PR-06 | geracao automatica | `last_generated_at`, sequence | `generate_due_preventives()` | endpoint manual | botao PCM | sem job | Nao integrado a agendador |
| PR-07 | avancar proxima previsao | `PreventivePlan` | `advance_preventive_plan_after_completion()` | via update item | Manutencao | PCM routes parcial | Existente; sem ciclo oficial |
| PR-08 | historico preventivo | schedule/item/OS preservados | history/report services | historico manutencao | Manutencao/Relatorios | parcial | Parcial |
| PR-09 | campos operacionais completos | dados distribuidos | varios | varias | PCM/Manutencao | Ausente consolidado | Parcial |
| PR-10 | concluir apenas na Central | item/OS | `update_schedule_item()` | `/manutencao/itens/{id}` | Manutencao | desktop/PCM parcial | Regra diferente |

## Horimetros

| Requisito | Regra de negocio | Model/Tabela | Service | API | Tela | Teste | Status |
|---|---|---|---|---|---|---|---|
| HR-01 | lancamento Web Mobile | `HourmeterReading` | `record_hourmeter()` | `POST /equipamentos/{id}/horimetros` | Disponibilidade Web | availability/mobile tests | Existente; aceite pendente |
| HR-02 | tela central diaria | tabela existe | list/record atuais | APIs individuais | Ausente no Desktop | Ausente | Nao encontrado |
| HR-03 | monotonia/futuro/duplicidade | checks + unique | `record_hourmeter()` | POST horimetro | Web | availability tests | Existente; periodo a homologar |
| HR-04 | alertar igual/variacao | sem parametro | Ausente | Ausente | Ausente | Ausente | Nao encontrado |
| HR-05 | correcao autorizada | sem entidade de ajuste | Ausente | Ausente | Ausente | Ausente | Nao encontrado |
| HR-06 | historico/auditoria | readings + audit log | hooks de auditoria | GET historico | consulta por ativo | audit/availability parcial | Parcial |
| HR-07 | recalcular preventiva/data | latest state + plan | `plan_due_state()` | leitura indireta | PCM refresh | PCM parcial | Parcial |
| HR-08 | offline/conflito | `MobileSyncOperation` | `sync_mobile_operation()` | `/operacao-mobile/sincronizar` | PWA/IndexedDB | mobile + phase11 | Existente; homologar dispositivo |

## Backlog

| Requisito | Regra de negocio | Model/Tabela | Service | API | Tela | Teste | Status |
|---|---|---|---|---|---|---|---|
| BK-01 | OS abertas entram | `MaintenanceWorkOrder` | `build_backlog()` | `/pcm/backlog` | `PCMPage` | PCM routes | Existente; aceite pendente |
| BK-02 | concluida sai e historico fica | work order persistida | filtro de status | `/pcm/backlog` | PCM | parcial | Existente; cancelamento ausente |
| BK-03 | todos os status oficiais | checks atuais | `_open_work_order_statuses()` | manutencao/PCM | Manutencao | Ausente para novos status | Parcial |
| BK-04 | faixas de idade | `scheduled_date` | so `age_days` | `/pcm/backlog` | PCM | Ausente | Nao encontrado |
| BK-05 | visoes/filtros oficiais | dados relacionais existem | retorno simples | `/pcm/backlog` | PCM | Ausente | Parcial |
| BK-06 | bloqueio de material | `MaintenanceMaterial` | `blocker_summary()` | backlog/maintenance | PCM/Manutencao | testes de suprimentos parciais | Existente; aceite pendente |
| BK-07 | cinco OS antigas | work orders | ordenacao sem resumo | backlog | Ausente dedicado | Ausente | Nao encontrado |

## Indicadores

| Requisito | Regra de negocio | Model/Tabela | Service | API | Tela | Teste | Status |
|---|---|---|---|---|---|---|---|
| IN-01 | MTTR oficial | `WorkOrderExecution` | `_reliability_metrics()` | `/relatorios/manutencao-executivo` | Dashboard/relatorio | intelligence routes | Formula/cobertura parcial |
| IN-02 | MTBF por horas operacionais | execution + readings | usa intervalo calendario | mesmo endpoint | Dashboard/relatorio | intelligence routes | Regra diferente |
| IN-03 | disponibilidade por periodo total | status events | `build_availability_overview()` | `/disponibilidade/visao` | Availability/Dashboard | availability tests | Regra diferente |
| IN-04 | paradas sem sobreposicao | status events | fluxo sequencial manual | status API | Availability | Ausente dedicado | Parcial |
| IN-05 | cumprimento preventivo | dados dispersos | Ausente | Ausente | Ausente | Ausente | Nao encontrado |
| IN-06 | recortes oficiais | relacionamentos existem | retorno limitado | relatorio executivo | Dashboard | Ausente | Nao encontrado |

## Dashboard

| Requisito | Regra de negocio | Model/Tabela | Service | API | Tela | Teste | Status |
|---|---|---|---|---|---|---|---|
| DA-01 | dashboard existente | varias | `build_dashboard_summary()` | `/relatorios/dashboard` | `DashboardPage` | navegacao/report indireto | Existente; escopo legado |
| DA-02 | resumo manutencao | varias PCM | `build_maintenance_intelligence_overview()` | `/relatorios/manutencao-executivo` | consumo gerencial | intelligence routes | Existente; formulas pendentes |
| DA-03 | cards oficiais | dados parciais | overview atual | endpoints de relatorio | Dashboard | parcial | Parcial |
| DA-04 | graficos oficiais | sem dataset completo | Ausente | Ausente | Ausente | Ausente | Nao encontrado |
| DA-05 | filtros completos | campos existem parcialmente | filtros pontuais | endpoints diversos | telas diversas | Ausente consolidado | Parcial |

## Auditoria

| Requisito | Regra de negocio | Model/Tabela | Service | API | Tela | Teste | Status |
|---|---|---|---|---|---|---|---|
| AU-01 | CRUD geral auditado | `AuditLog` | hooks SQLAlchemy | indireta | `AuditLogsPage` | `test_audit_service.py` | Existente; cobertura a validar |
| AU-02 | login/logout/status | `AuditLog` | funcoes explicitas | auth/status routes | Logs | audit test parcial | Existente; aceite pendente |
| AU-03 | consulta e saude | `AuditLog` | `audit_runtime_status()` | `/admin/audit-logs`, `/admin/audit-health` | Logs/Admin | security governance | Existente; aceite pendente |
| AU-04 | motivo para correcao/reabertura | sem campo/evento especifico | Ausente | Ausente | Ausente | Ausente | Nao encontrado |
| AU-05 | contexto imutavel completo | old/new text | serialize/redact | consulta admin | Logs | audit test | Parcial |
| AU-06 | testes de eventos PCM | audit table | hooks/eventos | varias | varias | apenas cobertura geral | Parcial |

## Permissoes

| Requisito | Regra de negocio | Model/Tabela | Service | API | Tela | Teste | Status |
|---|---|---|---|---|---|---|---|
| PE-01 | token e revogacao | `User`, `RevokedToken` | `auth_required()`, `revoke_token()` | auth | login | security routes | Existente; aceite pendente |
| PE-02 | quatro perfis atuais | `User.tipo` | helpers de acesso | guards | Desktop/Web | testes parciais | Existente; de-para pendente |
| PE-03 | acesso por pagina | user role | `desktop/access.py` | nao substitui API | `MainWindow` | `test_desktop_navigation.py` | Existente; visual |
| PE-04 | acao granular | tipo + guards dispersos | route guards | varias | botoes/telas | parcial | Parcial |
| PE-05 | perfis alvo adicionais | constraint logica atual | Ausente | `/usuarios` rejeita | Ausente | Ausente | Nao encontrado |
| PE-06 | policy consistente nos canais | user role | auth + mobile guards + desktop matrix | varias | Desktop/Web | parcial | Parcial |

## Importacao

| Requisito | Regra de negocio | Model/Tabela | Service | API | Tela | Teste | Status |
|---|---|---|---|---|---|---|---|
| IM-01 | Excel atual | grava `Vehicle` | `import_inventory_data()` | `/veiculos/importar-inventario` | `EquipmentPage` | `test_external_file_discovery.py` | Parcial; carreta/cavalo |
| IM-02 | mapper RTG | destino models existe | Ausente | Ausente | Ausente | Ausente | Nao encontrado |
| IM-03 | mapper LBS/Spreader | destino models/link existe | Ausente | Ausente | Ausente | Ausente | Nao encontrado |
| IM-04 | staging/preview/erros | tabelas ausentes | Ausente | Ausente | Ausente | Ausente | Nao encontrado |
| IM-05 | rollback por lote | batch ausente | Ausente | Ausente | Ausente | Ausente | Nao encontrado |
| IM-06 | inventario real homologado | `vehicles`/profiles/links | - | `/veiculos` | Equipment | sem teste de dados reais | Validacao operacional |

## Requisitos transversais ainda sem rastreabilidade completa

| Requisito | Persistencia | Backend/API | Tela | Teste | Status |
|---|---|---|---|---|---|
| Base Mestre/Power BI | consulta e exportacao v1 | endpoints protegidos e versionados | tela dedicada pendente | contrato/API aprovados | Parcial; Power BI pendente |
| Evidencia normalizada | Ausente; apenas paths | upload/storage existe | formularios pontuais | upload security | Parcial |
| Parametros PCM versionados | `SystemSetting` generico | admin rules parcial | AdminRulesPage | governance parcial | Parcial |
| Jobs preventivos | timestamps no plano | funcao/endpoint manual | botao | sem job | Nao integrado |
| Restore comprovado | backup service | rotas admin | BackupPage | sem ensaio neste ciclo | Validacao pendente |
| Schema producao x models | desconhecido | runtime schema existe | - | - | Validacao pendente |

## Gate final

Para alterar qualquer status desta matriz para `Concluido`, anexar evidencia de banco, backend, endpoint, tela, permissao, auditoria, teste automatizado, teste manual e aceite do responsavel operacional.

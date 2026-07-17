# De-para funcional

## Criterio

`Parcial` no resumo inclui "implementado parcialmente", "regra diferente", "apenas backend/frontend" e "nao integrado". Nenhuma duplicidade funcional foi comprovada; por isso a coluna duplicado ficou zerada. `MTR`/`TRM` foi descartado e o identificador oficial permanece o numero da OS.

## Equipamentos

| ID | Requisito operacional | RTG/LBS | Existe? | Situacao | Evidencia no codigo | Pode reaproveitar? | Lacuna | Acao recomendada | Prioridade |
|---|---|---|---|---|---|---|---|---|---|
| EQ-01 | Cadastro mestre unico | Ambos | Sim | Implementado | `Vehicle`/`vehicles`, `routes/vehicles.py` | Sim | Nome legado "veiculo" | Manter tabela e ajustar linguagem gradualmente | P1 |
| EQ-02 | Familias RTG, LBS e Spreader | Ambos | Sim | Implementado | `EquipmentFamily`, `seed_equipment_structure()` | Sim | Homologar codigos | Validar cadastros com operacao | P1 |
| EQ-03 | Todos os campos mestres exigidos | Ambos | Parcial | Implementado parcialmente | `Vehicle` + `EquipmentProfile` | Sim | Prefixo, area semantica e alguns dados tecnicos | Acrescentar apenas campos aprovados | P1 |
| EQ-04 | Local atual por patio/berco | Ambos | Sim | Implementado parcialmente | `EquipmentProfile.operational_location_id`, `OperationalLocation` | Sim | Um unico local atual | Preservar atual e criar movimento | P1 |
| EQ-05 | Historico de localizacao | Ambos | Nao | Nao encontrado | Nao ha model/tabela de movimento | Nao | Origem, destino, motivo, usuario e data | Criar entidade aditiva de movimentacao | P1 |
| EQ-06 | Tela individual dinamica | Ambos | Parcial | Implementado parcialmente | `/operacao-mobile/ativos/{access_code}` e tela `vehicles-screen` | Sim | Nao consolida PCM, KPIs e historicos | Evoluir tela por id/codigo, sem telas fixas | P2 |
| EQ-07 | Inventario 22 RTG e 16 LBS | Ambos | Incerto | Necessita validacao operacional | Codigo aceita familias; dados reais nao auditados | Sim | Quantidade e identidade nao homologadas | Conferir banco e planilhas oficiais | P1 |
| EQ-08 | Vinculo LBS-Spreader com vigencia | LBS | Sim | Implementado | `EquipmentLink`, `sync_active_equipment_link()` | Sim | Regras operacionais a homologar | Manter vinculo temporal | P1 |

## Ordem de servico

| ID | Requisito operacional | RTG/LBS | Existe? | Situacao | Evidencia no codigo | Pode reaproveitar? | Lacuna | Acao recomendada | Prioridade |
|---|---|---|---|---|---|---|---|---|---|
| OS-01 | Identificador somente numero da OS | Ambos | Sim | Implementado | `MaintenanceWorkOrder.order_number`; busca sem MTR/TRM | Sim | Nenhuma dependencia MTR encontrada | Preservar decisao | P1 |
| OS-02 | Numero automatico, unico e concorrente | Ambos | Parcial | Implementado parcialmente | `_sync_work_order_for_item()` gera `OS-{id:06d}`; unique index | Sim | Formato oficial e teste concorrente | Definir formato e estrategia transacional | P1 |
| OS-03 | Campos minimos completos | Ambos | Parcial | Implementado parcialmente | `MaintenanceWorkOrder` e `WorkOrderExecution` | Sim | Especialidade, equipe, fornecedor, horimetros e outros | Estender de forma normalizada | P1 |
| OS-04 | Datas completas e multi-dia | Ambos | Parcial | Implementado parcialmente | `failure_started_at`, `repair_started_at`, `repair_completed_at`, `released_at` | Sim | Fluxo programado nao possui mesma riqueza | Unificar eventos temporais da OS | P1 |
| OS-05 | Tipos oficiais de manutencao | Ambos | Parcial | Implementado com regra diferente | `source_type`: CHECKLIST_NC, ATIVIDADE, PREVENTIVA | Sim | Falta classificacao oficial independente da origem | Criar de-para origem x tipo | P1 |
| OS-06 | Geracao a partir de programacao | Ambos | Sim | Implementado | `sync_work_order_for_item()` | Sim | Cobertura depende da programacao | Manter servico central | P1 |
| OS-07 | Iniciar, reparar, testar e liberar | Ambos | Sim | Implementado | rotas `/ordens-servico/{id}/...`; `emergency_service.py` | Sim | Fluxo pleno esta concentrado na emergencial | Generalizar sem duplicar | P2 |
| OS-08 | Cancelar e reabrir formalmente | Ambos | Nao | Nao encontrado | Status/model/rotas sem operacoes formais | Nao | Historico e justificativa | Criar transicoes auditadas | P2 |
| OS-09 | Evidencias completas por OS | Ambos | Parcial | Implementado parcialmente | paths em `WorkOrderExecution`; `/upload` | Sim | Sem metadados/hash/vinculo multiplo | Criar anexo normalizado | P2 |

## Corretivas

| ID | Requisito operacional | RTG/LBS | Existe? | Situacao | Evidencia no codigo | Pode reaproveitar? | Lacuna | Acao recomendada | Prioridade |
|---|---|---|---|---|---|---|---|---|---|
| CR-01 | Abrir emergencial | Ambos | Sim | Implementado | `create_emergency()`, `POST /emergenciais` | Sim | Impacto/sistema ainda genericos | Acrescentar classificacao | P1 |
| CR-02 | Triar e converter em OS | Ambos | Sim | Implementado | `triage_emergency()`, `convert_emergency_to_work_order()` | Sim | Nenhuma estrutural | Manter fluxo | P1 |
| CR-03 | Executar, testar e liberar | Ambos | Sim | Implementado | `start_work_order()`, `complete_repair()`, `record_operational_test()`, `release_work_order()` | Sim | Expandir para demais tipos | Reusar state machine | P1 |
| CR-04 | Corretiva programada | Ambos | Parcial | Implementado parcialmente | `create_maintenance_schedule()` e `MaintenancePage` | Sim | Tipo oficial e fluxo individual nao explicitos | Classificar e integrar | P2 |
| CR-05 | Horas paradas e indicadores | Ambos | Parcial | Implementado parcialmente | `_reliability_metrics()` usa `WorkOrderExecution` | Sim | Conceitos e cobertura limitados | Homologar formulas e eventos | P2 |
| CR-06 | Abertura pela tela individual | Ambos | Parcial | Implementado parcialmente | acesso por ativo no PWA e formulario emergencial | Sim | Tela individual nao consolida todo o contexto | Preselecionar e exibir historico | P2 |

## Preventivas

| ID | Requisito operacional | RTG/LBS | Existe? | Situacao | Evidencia no codigo | Pode reaproveitar? | Lacuna | Acao recomendada | Prioridade |
|---|---|---|---|---|---|---|---|---|---|
| PR-01 | Plano por calendario/horimetro/ambos | Ambos | Sim | Implementado | `PreventivePlan.trigger_type`; `plan_due_state()` | Sim | Parametros portuarios nao homologados | Preservar model | P1 |
| PR-02 | Gerar agenda, item, OS e backlog | Ambos | Sim | Implementado | `_create_schedule_for_plan()`, `generate_due_preventives()` | Sim | Acionamento manual | Automatizar apos homologacao | P1 |
| PR-03 | Ciclos 500 a 6.000 h e reinicio | Ambos | Nao | Nao encontrado | Plano aceita intervalo livre; nao ha ciclo oficial | Parcial | Sequencia/ciclo anterior/proximo | Criar configuracao e execucao de ciclo | P1 |
| PR-04 | Faixas No prazo ate Vencida | Ambos | Parcial | Implementado parcialmente | apenas `EM_DIA`, `VENCENDO`, `VENCIDA` | Sim | Faixas 100/50/20/0 h | Parametrizar situacao | P1 |
| PR-05 | Central unica de preventiva | Ambos | Parcial | Implementado com regra diferente | plano em `PCMPage`, execucao em `MaintenancePage` | Sim | Operacao dividida em duas telas | Definir central sem duplicar backend | P1 |
| PR-06 | Geracao automatica | Ambos | Parcial | Existe, mas nao esta integrado | endpoint `/pcm/gerar-preventivas`; sem cron em `render.yaml` | Sim | Agendamento comprovado ausente | Criar job idempotente | P2 |
| PR-07 | Avancar proxima previsao | Ambos | Sim | Implementado | `advance_preventive_plan_after_completion()` | Sim | Soma intervalo, sem reinicio 6.000 h | Evoluir calculo | P1 |
| PR-08 | Historico de execucao preventiva | Ambos | Parcial | Implementado parcialmente | OS/item concluido preservado | Sim | Nao ha entidade especifica de execucao/ciclo | Consolidar consulta ou entidade | P2 |
| PR-09 | Todos os campos operacionais | Ambos | Parcial | Implementado parcialmente | `PreventivePlan` + schedule + OS | Sim | media diaria, horas restantes, desvio e equipe | Criar projecao consolidada | P2 |
| PR-10 | Concluir somente na central | Ambos | Parcial | Implementado com regra diferente | conclusao em `update_schedule_item()` na Manutencao | Sim | Restricao de tela nao corresponde ao escopo | Realinhar UX e permissao | P1 |

## Horimetros

| ID | Requisito operacional | RTG/LBS | Existe? | Situacao | Evidencia no codigo | Pode reaproveitar? | Lacuna | Acao recomendada | Prioridade |
|---|---|---|---|---|---|---|---|---|---|
| HR-01 | Lancamento operacional Web Mobile | Ambos | Sim | Implementado | `submitHourmeter()`, `POST /equipamentos/{id}/horimetros` | Sim | Nenhuma estrutural | Manter mobile | P1 |
| HR-02 | Tela central diaria no Desktop | Ambos | Nao | Nao encontrado | Desktop mostra disponibilidade, sem grade diaria de lancamento | Parcial | anterior, atual, variacao e responsavel em lote | Criar sobre APIs atuais | P1 |
| HR-03 | Monotonia, futuro e duplicidade temporal | Ambos | Sim | Implementado | `record_hourmeter()`, check/unique em `HourmeterReading` | Sim | Duplicidade por periodo precisa definicao | Homologar periodo | P1 |
| HR-04 | Alertar igual e variacao acima do limite | Ambos | Nao | Nao encontrado | valor igual e aceito; nao ha limite configurado | Nao | Alertas operacionais | Parametrizar e auditar | P1 |
| HR-05 | Correcao autorizada | Ambos | Nao | Nao encontrado | rotas possuem POST/GET, sem PUT de leitura | Nao | motivo, aprovador e recalc | Criar fluxo imutavel de correcao | P1 |
| HR-06 | Trilha de alteracao | Ambos | Parcial | Implementado parcialmente | auditoria generica de inserts; leitura nao e editavel | Sim | Sem evento de correcao | Integrar ao fluxo HR-05 | P1 |
| HR-07 | Recalcular preventiva e estimativa | Ambos | Parcial | Implementado parcialmente | `plan_due_state()` le horimetro atual | Sim | nao gera OS automaticamente nem calcula media/data | Criar recalculo idempotente | P2 |
| HR-08 | Offline com conflito | Ambos | Sim | Implementado | `MobileSyncOperation`, `sync_mobile_operation()`, IndexedDB | Sim | Homologar dispositivos | Manter arquitetura | P2 |

## Backlog

| ID | Requisito operacional | RTG/LBS | Existe? | Situacao | Evidencia no codigo | Pode reaproveitar? | Lacuna | Acao recomendada | Prioridade |
|---|---|---|---|---|---|---|---|---|---|
| BK-01 | OS abertas compoem backlog | Ambos | Sim | Implementado | `build_backlog()` consulta status abertos | Sim | - | Manter fonte unica | P1 |
| BK-02 | Concluida sai sem apagar historico | Ambos | Sim | Implementado | consulta exclui status fechado; OS permanece | Sim | Cancelada ainda nao formalizada | Completar cancelamento | P1 |
| BK-03 | Todos os status de espera | Ambos | Parcial | Implementado parcialmente | aberta, programada, material, execucao, reprogramada | Sim | fornecedor, liberacao, orcamento, suspensa | Padronizar state machine | P2 |
| BK-04 | Faixas 7/15/30/60 dias | Ambos | Nao | Nao encontrado | apenas `age_days` e `overdue` | Sim | bucket/faixa | Calcular no backend | P2 |
| BK-05 | Visao por familia/local/tipo/responsavel | Ambos | Parcial | Implementado parcialmente | dados base existem no retorno | Sim | filtros e agregacoes incompletos | Expandir consulta | P2 |
| BK-06 | Bloqueio de material | Ambos | Sim | Implementado | `blocker_summary()` e `materials_bloqueados` | Sim | outros bloqueios | Generalizar blockers | P2 |
| BK-07 | Cinco OS mais antigas | Ambos | Nao | Nao encontrado | retorno ordena, mas nao cria indicador dedicado | Sim | cartao/ranking | Derivar da consulta | P3 |

## Indicadores

| ID | Requisito operacional | RTG/LBS | Existe? | Situacao | Evidencia no codigo | Pode reaproveitar? | Lacuna | Acao recomendada | Prioridade |
|---|---|---|---|---|---|---|---|---|---|
| IN-01 | MTTR oficial | Ambos | Parcial | Implementado com regra diferente | `_reliability_metrics()`: liberacao - inicio do reparo | Sim | so execucoes emergenciais completas e poucos filtros | Homologar conceito e universo | P2 |
| IN-02 | MTBF por horas operacionais/falhas | Ambos | Parcial | Implementado com regra diferente | intervalo entre liberacao e proxima falha | Parcial | nao usa horimetro/horas operacionais | Recalcular pela formula oficial | P2 |
| IN-03 | Disponibilidade por periodo total | Ambos | Parcial | Implementado com regra diferente | `available_seconds / covered_seconds` | Sim | periodos sem evento ficam fora | Definir baseline e sobreposicao | P1 |
| IN-04 | Evitar parada sobreposta | Ambos | Parcial | Implementado parcialmente | eventos sequenciais no fluxo manual | Sim | importacao/correcao pode exigir reconciliacao | Criar regra e teste | P1 |
| IN-05 | Cumprimento preventivo | Ambos | Nao | Nao encontrado | nao ha calculo programada x realizada no prazo | Parcial | KPI e desvios | Criar servico consolidado | P3 |
| IN-06 | Todos os recortes oficiais | Ambos | Nao | Nao encontrado | retorno atual e geral/por equipamento limitado | Parcial | familia, tipo, mensal, responsavel, componente | Adicionar filtros apos base mestre | P3 |

## Dashboard

| ID | Requisito operacional | RTG/LBS | Existe? | Situacao | Evidencia no codigo | Pode reaproveitar? | Lacuna | Acao recomendada | Prioridade |
|---|---|---|---|---|---|---|---|---|---|
| DA-01 | Dashboard existente | Ambos | Sim | Implementado | `DashboardPage`, `/relatorios/dashboard` | Sim | foco original em checklist/frota | Preservar e ampliar | P3 |
| DA-02 | Resumo executivo de manutencao | Ambos | Sim | Implementado | `/relatorios/manutencao-executivo`, `build_maintenance_intelligence_overview()` | Sim | formulas parciais | Reusar apos homologacao | P3 |
| DA-03 | Todos os cartoes PCM | Ambos | Parcial | Implementado parcialmente | disponibilidade, backlog, MTBF/MTTR e preventivas | Sim | concluidas, horas paradas e cumprimento | Completar KPIs | P3 |
| DA-04 | Graficos exigidos | Ambos | Nao | Nao encontrado | telas atuais nao cobrem conjunto solicitado | Parcial | 13 visoes graficas | Construir depois da base mestre | P3 |
| DA-05 | Filtros operacionais completos | Ambos | Parcial | Implementado parcialmente | filtros pontuais por periodo/familia/local | Sim | ciclo, tipo, situacao e responsavel | Padronizar filtros | P3 |

## Auditoria

| ID | Requisito operacional | RTG/LBS | Existe? | Situacao | Evidencia no codigo | Pode reaproveitar? | Lacuna | Acao recomendada | Prioridade |
|---|---|---|---|---|---|---|---|---|---|
| AU-01 | Auditoria geral de CRUD | Ambos | Sim | Implementado | hooks SQLAlchemy em `audit_service.py` | Sim | validar cobertura fisica | Manter | P1 |
| AU-02 | Login, logout e status | Ambos | Sim | Implementado | `record_login_event()`, `record_logout_event()`, `record_status_change()` | Sim | - | Manter | P1 |
| AU-03 | Consulta e saude da auditoria | Ambos | Sim | Implementado | `/admin/audit-logs`, `/admin/audit-health`, `AuditLogsPage` | Sim | - | Manter | P1 |
| AU-04 | Motivo obrigatorio em correcao/reabertura | Ambos | Nao | Nao encontrado | `AuditLog` nao possui campo `reason` especifico | Parcial | regra por dominio | Criar eventos de dominio | P1 |
| AU-05 | Evidencia imutavel e contexto completo | Ambos | Parcial | Implementado parcialmente | old/new JSON e usuario | Sim | IP/request-id/hash nao persistidos no model | Evoluir metadados | P2 |
| AU-06 | Testes de todos os eventos PCM | Ambos | Parcial | Implementado parcialmente | `tests/test_audit_service.py` | Sim | novos fluxos nao existem | Expandir testes | P2 |

## Permissoes

| ID | Requisito operacional | RTG/LBS | Existe? | Situacao | Evidencia no codigo | Pode reaproveitar? | Lacuna | Acao recomendada | Prioridade |
|---|---|---|---|---|---|---|---|---|---|
| PE-01 | Autenticacao e revogacao | Ambos | Sim | Implementado | `auth_required()`, `RevokedToken` | Sim | - | Manter | P1 |
| PE-02 | Perfis atuais | Ambos | Sim | Implementado | admin, gestor, mecanico, motorista em `User.tipo` | Sim | nomenclatura alvo diferente | Criar de-para, nao duplicar usuarios | P1 |
| PE-03 | Acesso por pagina | Ambos | Sim | Implementado | `PAGE_ACCESS_BY_ROLE` em `desktop/access.py` | Sim | apenas Desktop | Manter como camada visual | P1 |
| PE-04 | Permissao granular por acao | Ambos | Parcial | Implementado parcialmente | guards em rotas e `ACTION_ACCESS_BY_ROLE` com 4 acoes | Sim | abrir/alterar/concluir/corrigir/exportar nao centralizados | Criar matriz unica backend-first | P1 |
| PE-05 | Supervisor, PCM, administrativo, tecnico, consulta | Ambos | Nao | Nao encontrado | `VALID_USER_TYPES` limita quatro perfis | Parcial | papeis alvo | Homologar antes de migration | P2 |
| PE-06 | Consistencia Desktop/API/Mobile | Ambos | Parcial | Implementado parcialmente | guards existem nas tres camadas | Sim | regras distribuidas | Centralizar policy sem retirar guards | P2 |

## Importacao

| ID | Requisito operacional | RTG/LBS | Existe? | Situacao | Evidencia no codigo | Pode reaproveitar? | Lacuna | Acao recomendada | Prioridade |
|---|---|---|---|---|---|---|---|---|---|
| IM-01 | Importacao Excel atual | Nao especifico | Parcial | Implementado parcialmente | `import_inventory_data()` le `CARRETAS` e `CAVALOS` | Sim | escopo nao portuario | Reusar infraestrutura openpyxl | P1 |
| IM-02 | Importar RTG | RTG | Nao | Nao encontrado | nenhum mapper RTG | Parcial | layout e validacao | Criar mapper apos homologar planilha | P1 |
| IM-03 | Importar LBS/Spreader | LBS | Nao | Nao encontrado | nenhum mapper LBS/Spreader | Parcial | relacoes e seriais | Criar mapper e reconciliacao | P1 |
| IM-04 | Staging, preview e relatorio de erros | Ambos | Nao | Nao encontrado | importacao grava diretamente | Nao | processamento controlado | Criar lote de importacao | P1 |
| IM-05 | Backup e rollback do lote | Ambos | Nao | Nao encontrado | rota nao registra batch reversivel | Parcial | restauracao seletiva | Implementar transacao/lote | P1 |
| IM-06 | Homologacao do inventario real | Ambos | Incerto | Necessita validacao operacional | dados de producao/planilhas nao comparados | Sim | 22 RTG, 16 LBS e Spreaders | Gerar de-para de dados | P1 |

## Consolidado

| Grupo | Implementado | Parcial | Nao encontrado | Duplicado | Necessita validacao |
|---|---:|---:|---:|---:|---:|
| Equipamentos | 3 | 3 | 1 | 0 | 1 |
| OS | 3 | 5 | 1 | 0 | 0 |
| Corretivas | 3 | 3 | 0 | 0 | 0 |
| Preventivas | 3 | 6 | 1 | 0 | 0 |
| Horimetros | 3 | 2 | 3 | 0 | 0 |
| Backlog | 3 | 2 | 2 | 0 | 0 |
| Indicadores | 0 | 4 | 2 | 0 | 0 |
| Dashboard | 2 | 2 | 1 | 0 | 0 |
| Auditoria | 3 | 2 | 1 | 0 | 0 |
| Permissoes | 3 | 2 | 1 | 0 | 0 |
| Importacao | 0 | 1 | 4 | 0 | 1 |

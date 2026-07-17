# ADRs da arquitetura-alvo - Fase 2

Data: 17/07/2026

Status do pacote: **CONCLUIDO TECNICAMENTE, PENDENTE DE HOMOLOGACAO OPERACIONAL**.

## Objetivo

Definir a arquitetura que orientara as migrations e APIs da Fase 3 sem alterar o sistema atual. Este documento nao cria tabela, model, rota, tela, perfil ou formula oficial.

## Invariantes da solucao

1. O Checklist de Frota continuara sendo o unico sistema.
2. O Desktop continuara sendo a interface de gestao e PCM.
3. O Web Mobile continuara sendo a interface operacional.
4. Backend, Desktop e Web Mobile usarao a mesma API e o mesmo PostgreSQL oficial.
5. `Vehicle` continuara sendo a raiz tecnica de todo ativo.
6. `MaintenanceWorkOrder.order_number` sera o unico identificador oficial de OS.
7. MTR e TRM nao serao criados.
8. Migrations futuras serao aditivas, compativeis e reversiveis.
9. Dados historicos nao serao apagados nem renumerados.
10. Indicadores somente serao publicados como oficiais depois de reconciliacao manual.

## Evidencias atuais

| Dominio | Implementacao comprovada | Limite atual |
|---|---|---|
| Ativo | `Vehicle`, tabela `vehicles`, em `backend/app/models/vehicle.py` | `tipo` e `local` legados ainda participam do fluxo |
| Estrutura | `EquipmentFamily`, `OperationalLocation`, `EquipmentProfile` e `EquipmentLink` em `backend/app/models/equipment_structure.py` | nao existe movimento historico de localizacao |
| OS | `MaintenanceWorkOrder`, tabela `maintenance_work_orders`, em `backend/app/models/maintenance.py` | OS depende de `MaintenanceSchedule` e `MaintenanceScheduleItem` |
| Execucao | `WorkOrderExecution` em `backend/app/models/emergency.py` | execucao detalhada existe apenas no fluxo emergencial |
| Disponibilidade | `EquipmentOperationalState` e `EquipmentStatusEvent` em `backend/app/models/operational_availability.py` | classificacao oficial dos periodos nao foi homologada |
| Horimetro | `HourmeterReading` e `record_hourmeter()` em `backend/app/services/availability_service.py` | nao existe correcao autorizada append-only |
| Preventiva | `PreventivePlan` e `generate_due_preventives()` em `backend/app/services/pcm_service.py` | nao existe sequencia formal de 500 a 6.000 h |
| Backlog | `build_backlog()` em `backend/app/services/pcm_service.py` | idade usa `scheduled_date`, nao a abertura da OS |
| KPI | `_reliability_metrics()` em `backend/app/services/maintenance_intelligence_service.py` | MTBF usa horas de calendario e formula nao homologada |
| Permissao | `User.tipo` e guards em `backend/app/services/auth_service.py` | RBAC atual possui apenas quatro perfis amplos |
| Auditoria | `AuditLog` e hooks em `backend/app/services/audit_service.py` | eventos de dominio ainda nao seguem um catalogo oficial |
| Anexo | `/upload`, `storage_service.py` e varios campos `*_path` | metadados e vinculos estao espalhados entre entidades |

## ADR-001 - Raiz de equipamento e localizacao

Status: **ACEITA TECNICAMENTE**.

### Decisao

- `Vehicle` permanece como aggregate root e ID estavel de Frota, RTG, LBS, Spreader e apoio.
- `EquipmentFamily` e a classificacao oficial; `Vehicle.tipo` permanece como cache legado durante a transicao.
- `EquipmentProfile` permanece como extensao tecnica 1:1 do ativo.
- `OperationalLocation` representa a hierarquia Terminal, Area, Pier, Berco, Patio ou Outro.
- O local atual fica em `EquipmentProfile.operational_location_id`; `Vehicle.local` permanece como texto compativel.
- A Fase 3 devera acrescentar um movimento imutavel de localizacao com origem, destino, inicio, fim, motivo e responsavel.
- `EquipmentLink` continua registrando o vinculo temporal entre LBS pai e Spreader filho.
- Apos migracao, um Spreader podera ter no maximo um vinculo ativo, sem apagar vinculos encerrados.
- Exclusao fisica de ativo nao sera permitida quando houver historico; sera usado encerramento/inativacao.

### Evidencia e fluxo atual

- Models: `Vehicle`, `EquipmentFamily`, `OperationalLocation`, `EquipmentProfile` e `EquipmentLink`.
- Service: `apply_equipment_profile()` e `sync_active_equipment_link()` em `backend/app/services/equipment_structure_service.py`.
- Rotas: `/veiculos`, `/equipamentos/estrutura`, `/equipamentos/locais` e `/equipamentos/vinculos`.
- Tabelas: `vehicles`, `equipment_families`, `operational_locations`, `equipment_profiles` e `equipment_links`.

### Compatibilidade e rollback

- Nenhum ID, `frota`, `tipo` ou `local` legado sera removido na Fase 3.
- O codigo anterior podera continuar lendo `vehicles` enquanto os novos movimentos ficam desativados por feature flag.

## ADR-002 - OS unica, origem e tipo de manutencao

Status: **ACEITA TECNICAMENTE**.

### Decisao

- `MaintenanceWorkOrder` sera a unica entidade de Ordem de Servico.
- `order_number` sera o unico numero oficial; numeros existentes nunca serao alterados.
- `EmergencyEvent.event_number` continuara sendo referencia de evento, nao um segundo numero de OS.
- MTR e TRM nao serao criados.
- Origem, tipo e modo de execucao serao conceitos separados.

| Conceito | Valores-alvo iniciais | Uso |
|---|---|---|
| Origem | `MANUAL`, `CHECKLIST_NC`, `INSPECAO_TECNICA`, `EMERGENCIA`, `PREVENTIVA`, `IMPORTACAO` | explica de onde a OS nasceu |
| Tipo | `CORRETIVA`, `PREVENTIVA`, `PREDITIVA`, `MELHORIA` | classifica a natureza da manutencao |
| Modo | `EMERGENCIAL`, `PROGRAMADA` | define urgencia e planejamento |

- A OS podera existir sem programacao previa; os FKs de agenda deverao se tornar opcionais por migration compativel.
- Agenda, emergencia, NC e preventiva apontarao para a mesma OS.
- Numeracao concorrente devera ser gerada de forma atomica pelo banco ou por sequencia transacional.
- Diagnostico, especialidade, prioridade, equipe, fornecedor e custos pertencerao a OS ou aos seus sub-registros, nunca ao numero.

### Evidencia e fluxo atual

- Model: `MaintenanceWorkOrder` em `backend/app/models/maintenance.py`.
- Geracao atual: `_sync_work_order_for_item()` em `backend/app/services/maintenance_service.py` cria `OS-000000` a partir do ID.
- Emergencia: `convert_emergency_to_work_order()` em `backend/app/services/emergency_service.py` cria agenda, item e OS.
- Tabelas: `maintenance_work_orders`, `maintenance_schedules`, `maintenance_schedule_items` e `emergency_events`.

### Compatibilidade e rollback

- `schedule_id`, `schedule_item_id` e `resolution_package_id` permanecerao legiveis.
- Clientes antigos continuarao recebendo os campos atuais de `to_dict()`.
- Novos campos serao opcionais ate o backfill e a homologacao.

## ADR-003 - Tempos, falha, reparo e indisponibilidade

Status: **PROPOSTA PARA HOMOLOGACAO OPERACIONAL**.

### Decisao

Os seguintes fatos nao serao confundidos nem derivados uns dos outros:

| Fato | Definicao-alvo |
|---|---|
| Falha detectada | instante em que a falha foi percebida |
| Inicio da parada | instante em que o ativo deixou de atender a operacao |
| Inicio do reparo | instante de trabalho tecnico efetivo |
| Fim do reparo | instante em que o servico tecnico terminou |
| Inicio/fim do teste | janela de teste operacional |
| Liberacao | decisao autorizada que devolve o ativo a operacao |
| Fim da parada | encerramento do periodo de indisponibilidade |
| Horas da equipe | soma de apontamentos inicio/fim por pessoa, sem usar o tempo total da OS |

- A falha tera classificacao `counts_as_failure` para decidir se participa de MTBF/MTTR.
- A indisponibilidade sera calculada pelos periodos de `EquipmentStatusEvent`, vinculados quando possivel a OS ou emergencia.
- Horas da equipe serao lancamentos proprios e poderao se sobrepor entre tecnicos.
- Os timestamps atuais de Manaus permanecerao compativeis; conversao global de timezone nao faz parte da Fase 3.
- Alteracoes de tempo exigirao motivo e evento de auditoria; fatos originais nao serao apagados.

### Evidencia e fluxo atual

- `WorkOrderExecution.failure_started_at`, `repair_started_at`, `repair_completed_at` e `released_at` em `backend/app/models/emergency.py`.
- `start_work_order()`, `complete_repair()`, `record_operational_test()` e `release_work_order()` em `backend/app/services/emergency_service.py`.
- `EquipmentStatusEvent.started_at/ended_at` em `backend/app/models/operational_availability.py`.

### Ponto pendente

PCM, Manutencao e Operacao devem aprovar quais fatos abrem e encerram MTTR, MTBF e indisponibilidade.

## ADR-004 - Horimetro append-only e correcao

Status: **ACEITA TECNICAMENTE; ALCADA DE APROVACAO PENDENTE**.

### Decisao

- `HourmeterReading` sera imutavel: nao havera UPDATE ou DELETE de leitura confirmada.
- Nova leitura devera ser crescente em relacao a serie efetiva do ativo.
- Correcao sera uma nova operacao que referencia a leitura substituida, informa valor correto, motivo, solicitante e aprovador.
- A leitura incorreta continuara armazenada e sera desconsiderada apenas pela projecao efetiva.
- Solicitante e aprovador nao poderao ser a mesma pessoa.
- Aprovacao disparara recalculo de preventiva, previsoes e indicadores dependentes.
- `source` distinguira `MANUAL`, `MOBILE`, `IMPORTADO`, `TELEMETRIA` e `CORRECAO`.
- Operacoes offline usarao chave idempotente para evitar leitura duplicada.
- Evidencia sera obrigatoria quando a familia ou a faixa de variacao assim exigir.

### Evidencia e fluxo atual

- Model: `HourmeterReading`, tabela `hourmeter_readings`.
- Service: `record_hourmeter()` valida vizinhos anterior/posterior.
- Rotas: `POST/GET /equipamentos/<id>/horimetros`.
- Mobile: `MobileSyncOperation` e testes em `tests/test_mobile_operations_routes.py`.

### Compatibilidade e rollback

- A tabela atual sera preservada e novos campos/entidades serao aditivos.
- Sem feature flag, a API continuara usando a serie atual.
- Rollback desativa a projecao corrigida sem apagar leituras.

## ADR-005 - Ciclo preventivo por calendario e horimetro

Status: **PENDENTE DE HOMOLOGACAO OPERACIONAL**.

### Decisao tecnica

- `PreventivePlan` continuara representando o plano de um ativo.
- A Fase 3 devera acrescentar template por familia e passos versionados para representar 500, 1.000, 1.500 ate 6.000 h.
- Cada passo guardara codigo, ordem, intervalo, tolerancia, tarefas e revisao tecnica.
- Uma OS preventiva guardara a versao e o passo que a originaram, mesmo que o template mude depois.
- Para gatilho `AMBOS`, a proposta e vencer no primeiro limite atingido entre calendario e horimetro.
- Tolerancia classifica o desvio, mas nao muda a data/hora nominal do vencimento.
- Geracao sera idempotente por plano, versao e sequencia do ciclo.
- Conclusao por horimetro exigira leitura efetiva do momento da execucao.

### Evidencia e fluxo atual

- Model: `PreventivePlan` em `backend/app/models/pcm.py`.
- Services: `plan_due_state()`, `generate_due_preventives()` e `advance_preventive_plan_after_completion()`.
- Rotas: `/pcm/planos-preventivos`, `/pcm/gerar-preventivas` e `/pcm/agenda`.

### Ponto pendente

Nao existe decisao oficial para o passo posterior a 6.000 h. O sistema nao assumira reinicio em 500 h, continuidade em 6.500 h ou encerramento sem aprovacao explicita.

## ADR-006 - State machine de OS e backlog derivado

Status: **PROPOSTA PARA HOMOLOGACAO OPERACIONAL**.

### Estados-alvo

`ABERTA`, `PROGRAMADA`, `AGUARDANDO_MATERIAL`, `AGUARDANDO_OPERACAO`, `AGUARDANDO_TERCEIRO`, `EM_EXECUCAO`, `EM_TESTE`, `SUSPENSA`, `CONCLUIDA` e `CANCELADA`.

### Transicoes principais

| Origem | Destino permitido | Condicao minima |
|---|---|---|
| `ABERTA` | `PROGRAMADA`, esperas, `CANCELADA` | classificacao e motivo quando aplicavel |
| `PROGRAMADA` | esperas, `EM_EXECUCAO`, `SUSPENSA`, `CANCELADA` | responsavel e janela definidos |
| Esperas | `PROGRAMADA`, `EM_EXECUCAO`, `SUSPENSA`, `CANCELADA` | motivo de saida registrado |
| `EM_EXECUCAO` | `EM_TESTE`, `SUSPENSA` | diagnostico e apontamento tecnico |
| `EM_TESTE` | `CONCLUIDA`, `EM_EXECUCAO` | teste aprovado ou retorno com motivo |
| `SUSPENSA` | estado operacional anterior, `CANCELADA` | motivo e autorizacao |
| Terminal | `ABERTA` por reabertura | motivo, autorizador e evento `REABERTA` |

- Toda transicao gerara evento com estado anterior, novo, motivo, usuario e instante.
- `REPROGRAMADA` sera evento e voltara a `PROGRAMADA`; `NAO_EXECUTADA` sera resultado/motivo, nao estado permanente novo.
- Enquanto houver clientes legados, os valores atuais continuarao aceitos por uma camada de compatibilidade.
- Backlog continuara sendo consulta derivada, nunca uma tabela duplicada.
- Entram no backlog todas as OS nao terminais.
- Idade sera `hoje - opened_at`; atraso de agenda sera calculado separadamente.
- Faixas: 0-7, 8-15, 16-30, 31-60 e acima de 60 dias.

### Evidencia e fluxo atual

- Constraint de `MaintenanceWorkOrder.status` em `backend/app/models/maintenance.py`.
- Mapeamento atual em `_work_order_status_from_item()`.
- Atualizacao atual em `update_schedule_item()`.
- Backlog atual em `build_backlog()` usa `scheduled_date`.

## ADR-007 - Formulas oficiais e versao de KPI

Status: **PENDENTE DE HOMOLOGACAO OPERACIONAL**.

### Propostas de formula

| Indicador | Formula proposta | Regra de qualidade |
|---|---|---|
| Disponibilidade | horas em `DISPONIVEL` + `RESTRICAO` divididas pelas horas cobertas | `SEM_APONTAMENTO` nao entra e deve aparecer como falta de dado |
| MTTR | media de `liberacao - inicio_reparo` das corretivas classificadas como falha | exige reparo, teste e liberacao validos |
| MTBF | horas efetivas de horimetro entre liberacao da falha anterior e proxima falha | sem horimetro suficiente, resultado oficial fica indisponivel |
| Cumprimento preventivo | preventivas concluidas no limite dividido pelas preventivas vencidas no periodo | versao do plano e tolerancia devem ser preservadas |
| Backlog | quantidade e idade das OS nao terminais | idade pela abertura, atraso pela agenda |

- `RESTRICAO` sera mostrada separadamente, mesmo quando contar como disponivel.
- `MANUTENCAO` e `INDISPONIVEL` contam como indisponiveis na proposta.
- MTBF em horas de calendario podera aparecer apenas como indicador provisorio, nunca rotulado como oficial.
- Cada formula publicada tera codigo, versao, vigencia, filtros e aprovador.
- O mesmo dataset alimentara Desktop, exportacoes e Power BI.

### Evidencia e fluxo atual

- Disponibilidade atual: `build_availability_overview()` em `availability_service.py`.
- MTTR/MTBF atuais: `_reliability_metrics()` em `maintenance_intelligence_service.py`.
- Teste atual de 48 h/7,5 h: `tests/test_maintenance_intelligence_routes.py`.

## ADR-008 - Permissoes por capacidade e auditoria

Status: **PENDENTE DE HOMOLOGACAO OPERACIONAL**.

### Decisao tecnica

- Autorizacao sera backend-first e baseada em capacidades, nao apenas em esconder botoes.
- `User.tipo` sera preservado durante a transicao.
- Mapeamento legado inicial: `admin` para Administrador; `gestor` para Supervisor + PCM; `mecanico` para Tecnico; `motorista` para Operacao.
- Perfis Administrativo e Consulta somente serao ativados depois de aprovacao.
- Correcao de horimetro, reabertura/cancelamento de OS, liberacao de ativo, importacao e mudanca de formula exigirao auditoria explicita.
- Nenhuma acao critica podera ser autorizada apenas pelo cliente Desktop ou Mobile.

### Capacidades-alvo

| Grupo | Capacidades |
|---|---|
| Cadastro | consultar, editar ativo, mover local, vincular Spreader |
| Operacao | registrar status, horimetro, emergencia e evidencia |
| OS | abrir, classificar, programar, executar, testar, liberar, suspender, cancelar, reabrir |
| PCM | manter plano, gerar preventiva, priorizar backlog e agenda |
| Suprimentos | reservar, consumir, ajustar e consultar estoque |
| Gestao | consultar KPI, exportar, homologar formula e consultar auditoria |
| Governanca | importar, corrigir horimetro, administrar usuarios e permissoes |

### Evidencia e fluxo atual

- `User.tipo` em `backend/app/models/user.py`.
- `user_has_management_access()` e `user_has_mechanic_workspace_access()` em `auth_service.py`.
- Guards nas rotas `maintenance.py`, `pcm.py`, `emergencies.py`, `equipment_structure.py` e `admin.py`.
- `AuditLog`, `record_event()` e hooks em `audit_service.py`.

## ADR-009 - Anexos e evidencias normalizados

Status: **ACEITA TECNICAMENTE**.

### Decisao

- Arquivos continuarao no storage local ou Supabase; o banco guardara metadados e vinculos.
- A Fase 3 devera criar catalogo de anexo e vinculo polimorfico controlado.
- Metadados minimos: provider, object key imutavel, nome original, extensao, MIME, tamanho, SHA-256, criador, instante e status.
- O vinculo informara entidade, ID, categoria da evidencia e ordem de exibicao.
- Upload nao sobrescrevera objeto existente.
- Exclusao sera logica; objeto fisico sera mantido durante a janela de rollback e retencao.
- Download exigira autenticacao e autorizacao sobre a entidade vinculada.
- Campos atuais `foto_*`, `evidence_path`, `photo_after` e `file_path` permanecerao durante o backfill.
- PDF tecnico continuara permitido; imagens continuarao limitadas aos formatos atuais.

### Evidencia e fluxo atual

- Rota `/upload` em `backend/app/routes/upload.py`.
- `save_local_upload()` e `save_supabase_upload()` em `backend/app/services/storage_service.py`.
- Campos espalhados em `checklist.py`, `activity.py`, `emergency.py`, `operational_availability.py`, `technical_inspection.py`, `maintenance.py`, `vehicle.py` e `supply_library.py`.
- Testes de autorizacao e PDF em `tests/test_upload_security.py`.

## Contrato para a Fase 3

Somente depois do gate operacional, cada modulo da Fase 3 devera entregar:

1. Uma migration aditiva e seu downgrade avaliado.
2. Backfill idempotente com contagens antes/depois.
3. Service de dominio como ponto unico da regra.
4. API retrocompativel com Desktop e Web Mobile atuais.
5. Evento de auditoria para operacoes criticas.
6. Testes de regra, API, permissao, upgrade e rollback.
7. Feature flag quando o comportamento novo competir com o legado.

## Itens que continuam proibidos

- Aplicar migration na producao sem comparar o PostgreSQL real.
- Importar RTG, LBS ou Spreader diretamente nas tabelas finais.
- Publicar MTBF, MTTR ou disponibilidade como oficial sem homologacao.
- Renumerar OS ou criar MTR/TRM.
- Corrigir leitura apagando ou sobrescrevendo o horimetro original.
- Excluir anexo durante a janela de rollback.

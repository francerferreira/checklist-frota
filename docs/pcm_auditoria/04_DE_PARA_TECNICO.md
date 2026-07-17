# De-para tecnico

## Matriz por camada

| Camada | Recurso atual | Caminho | Recurso necessario | Compatibilidade | Gap | Risco | Decisao |
|---|---|---|---|---|---|---|---|
| Banco | `vehicles` | `models/vehicle.py:Vehicle` | cadastro mestre de equipamento | Alta | nome e campos ainda orientados a frota | Baixo | reaproveitar como raiz |
| Banco | familias/perfis/locais | `models/equipment_structure.py` | RTG/LBS/Spreader e local atual | Alta | falta historico de movimento | Medio | manter e adicionar entidade temporal |
| Banco | `equipment_links` | `EquipmentLink` | vinculo LBS-Spreader | Alta | regras operacionais a homologar | Medio | reaproveitar vigencia existente |
| Banco | `hourmeter_readings` | `operational_availability.py` | serie historica de horimetros | Alta | sem correcao/aprovacao e alertas | Alto | manter leitura imutavel e criar ajuste formal |
| Banco | estado/eventos operacionais | `EquipmentOperationalState`, `EquipmentStatusEvent` | disponibilidade e paradas | Alta | formula oficial e sobreposicao | Alto | reutilizar eventos, homologar baseline |
| Banco | `maintenance_work_orders` | `models/maintenance.py` | OS oficial portuaria | Media | muitos campos operacionais ausentes | Alto | estender sem criar outra OS |
| Banco | `work_order_executions` | `models/emergency.py` | tempos, diagnostico, acao e teste | Media | focada em emergencial | Medio | generalizar relacao com OS |
| Banco | `preventive_plans` | `models/pcm.py` | plano/ciclo preventivo | Alta | sem ciclo 500-6000 e execucao propria | Alto | manter plano e adicionar configuracao/execucao |
| Banco | schedules/items | `models/maintenance.py` | agenda e backlog | Alta | estados e faixas incompletos | Medio | manter como agenda operacional |
| Banco | `audit_logs` | `models/audit_log.py` | auditoria PCM | Media | sem motivo/contexto dedicado | Alto | evoluir trilha, nao substituir |
| Banco | anexos por path | varios models | evidencia normalizada | Baixa | sem hash/tamanho/vinculo multiplo | Medio | criar entidade de anexo depois da arquitetura |
| Banco | migrations lineares | `migrations/versions/` | evolucao controlada | Media | runtime tambem altera schema | Alto | comparar producao e retirar mutacao gradual |
| Backend | cadastro e perfil | `equipment_structure_service.py` | mestre dinamico | Alta | validacao de inventario | Medio | reaproveitar |
| Backend | horimetro | `availability_service.record_hourmeter()` | regras diarias oficiais | Alta | igual/limite/correcao/recalculo | Alto | ampliar servico central |
| Backend | disponibilidade | `build_availability_overview()` | formula por periodo total | Media | denominador usa tempo coberto | Alto | corrigir apos homologar conceito |
| Backend | OS | `maintenance_service._sync_work_order_for_item()` | numero e ciclo completo | Media | formato, concorrencia e campos | Alto | manter gerador central e endurecer transacao |
| Backend | emergencial | `emergency_service.py` | corretiva emergencial | Alta | integrar classificacoes/indicadores | Medio | reaproveitar state machine |
| Backend | preventiva | `pcm_service.py` | central 500-6000 h | Media | ciclo livre, geracao manual | Alto | evoluir sem novo modulo paralelo |
| Backend | inteligencia | `maintenance_intelligence_service.py` | KPIs oficiais | Media | MTBF/MTTR/disponibilidade divergentes | Alto | manter endpoint, trocar calculo homologado |
| API | `/veiculos` e `/equipamentos/estrutura` | `routes/vehicles.py`, `equipment_structure.py` | API mestre | Alta | resposta ainda usa vocabulario legado | Baixo | manter compatibilidade |
| API | `/equipamentos/{id}/horimetros` | `routes/availability.py` | lancar/consultar/corrigir | Media | nao existe PUT de correcao | Alto | adicionar endpoint auditado |
| API | `/pcm/*` | `routes/pcm.py` | central preventiva completa | Media | sem execucao central e simulacao | Medio | ampliar rotas existentes |
| API | `/manutencao/*` | `routes/maintenance.py` | programadas, OS e backlog | Alta | filtros/estados oficiais | Medio | reaproveitar |
| API | `/operacao-mobile/*` | `routes/mobile_operations.py` | offline por ativo | Alta | homologacao de conflito/dispositivos | Medio | preservar contrato |
| API | `/relatorios/manutencao-executivo` | `routes/reports.py` | dashboard/Base Mestre | Media | sem dataset detalhado/paginado | Alto | separar resumo e dataset mestre |
| Frontend | `EquipmentPage` | `desktop/ui/equipment_page.py` | cadastro unificado | Alta | tela individual consolidada ausente | Medio | evoluir navegacao por ativo |
| Frontend | `AvailabilityPage` | `desktop/ui/availability_page.py` | status e horimetro central | Media | sem grade diaria de lancamento | Alto | adicionar modo central |
| Frontend | `PCMPage` | `desktop/ui/pcm_page.py` | central de preventivas | Alta | poucos campos e execucao separada | Alto | expandir esta tela |
| Frontend | `MaintenancePage` | `desktop/ui/maintenance_page.py` | corretiva programada/OS | Alta | classificacoes oficiais | Medio | reaproveitar janelas |
| Frontend | Web Mobile | `web_app/index.html`, `static/js/app.js` | operacao no campo | Alta | sem painel PCM completo, corretamente | Baixo | manter apenas operacional |
| Dashboard | `DashboardPage` | `desktop/ui/dashboard_page.py` | executivo portuario | Media | cards/graficos/filtros incompletos | Medio | alimentar por servico oficial |
| Relatorio | PDF/Excel atuais | `report_service.py`, `export_service.py` | gerencial e Base Mestre | Media | sem CSV/JSON mestre/paginacao | Medio | reaproveitar exportacao |
| Auditoria | hooks globais | `audit_service.py` | CRUD e eventos de dominio | Alta | motivo e contexto de negocio | Alto | combinar hooks + eventos explicitos |
| Permissao | quatro perfis | `auth_service.py`, `desktop/access.py` | matriz granular | Media | funcoes espalhadas e perfis faltantes | Alto | definir policy backend-first |
| Integracao | Supabase Storage | `storage_service.py` | anexos PCM | Alta | metadados nao persistidos | Medio | manter storage, normalizar catalogo |
| Integracao | Render | `render.yaml` | API/web/jobs | Media | sem cron declarado | Medio | adicionar job somente apos idempotencia |
| Importacao | openpyxl direto | `inventory_import_service.py` | RTG/LBS controlado | Baixa | sem mapper/staging/preview/rollback | Alto | criar pipeline, reusar parser |

## De-para de valores atuais

### Origem atual x tipo oficial

| Valor/origem atual | Significado atual | Tipo oficial sugerido | Observacao |
|---|---|---|---|
| `PREVENTIVA` | agenda gerada por plano PCM | Preventiva | aderente |
| `CHECKLIST_NC` | falha detectada em checklist | Corretiva programada ou emergencial | depende de impacto/prioridade |
| `ATIVIDADE` | inspecao/atividade convertida | Inspecao, melhoria ou corretiva programada | exige classificacao |
| `PACOTE_RESOLUCAO` | conjunto de NCs | Corretiva programada/campanha | exige classificacao |
| `EmergencyEvent` | parada comunicada | Corretiva emergencial | aderente |

Nao se recomenda substituir `source_type`: origem e tipo de manutencao sao conceitos diferentes e ambos devem ser preservados.

### Status atuais x backlog oficial

| Atual | Oficial mais proximo | Gap |
|---|---|---|
| `ABERTA` | Nao iniciada | aderente |
| `PROGRAMADA` | Programada | aderente |
| `EM_EXECUCAO` | Em andamento | aderente |
| `AGUARDANDO_MATERIAL` | Aguardando material | aderente |
| `REPROGRAMADA` | Programada/suspensa | precisa regra |
| inexistente | Aguardando fornecedor | criar |
| inexistente | Aguardando liberacao operacional | criar |
| inexistente | Aguardando orcamento | criar |
| inexistente | Suspensa | criar |

## Decisoes recomendadas para aprovacao

1. `Vehicle` continua sendo a raiz tecnica do equipamento.
2. `MaintenanceWorkOrder` continua sendo a unica OS; nenhum MTR/TRM sera criado.
3. Origem da OS e tipo de manutencao devem ser campos separados.
4. Horimetro deve permanecer append-only; correcao cria evento compensatorio/aprovado, sem apagar leitura.
5. Local atual permanece no perfil, mas toda alteracao passa a gerar movimento historico.
6. O Desktop concentra PCM/gestao; Web Mobile concentra apontamento e execucao.
7. Indicadores so podem ser publicados como oficiais depois de formula e dados de origem homologados.

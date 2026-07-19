# Resumo executivo - Auditoria PCM Portuario

## Identificacao

- Ciclo: primeiro ciclo de auditoria, sem implementacao funcional.
- Data da leitura tecnica: 17/07/2026.
- Escopo operacional: RTG, LBS e Spreaders, com reaproveitamento do Checklist de Frota.
- Regra de identificacao: somente o numero da OS. Nao foi encontrada referencia a `MTR` ou `TRM` em `backend/`, `desktop/`, `web_app/`, `migrations/`, `tests/` ou `tools/`.
- Fonte da conclusao: codigo versionado, models e migrations. O schema fisico do PostgreSQL de producao e os dados reais do inventario nao foram consultados neste ciclo.

## Visao geral

O sistema nao e apenas um checklist. Ele ja possui uma base relevante de manutencao: cadastro unificado de ativos, familias, localizacoes, vinculo LBS-Spreader, disponibilidade, horimetros, inspecoes, emergenciais, OS, agenda de manutencao, planos preventivos, backlog, estoque, biblioteca tecnica, indicadores, automacoes, auditoria e operacao mobile offline.

A arquitetura atual e hibrida:

- Backend Flask/SQLAlchemy em `backend/app/`.
- Desktop PySide6 em `desktop/`, voltado a gestao e PCM.
- Web Mobile/PWA em `web_app/`, voltado a execucao operacional.
- SQLite como fallback local e PostgreSQL por `DATABASE_URL`, conforme `backend/app/config.py`.
- Deploy previsto no Render e arquivos no Supabase Storage, conforme `render.yaml` e `backend/app/services/storage_service.py`.

Em analogia simples: a fundacao e boa e varios comodos ja existem, mas ainda faltam portas de controle entre eles e padronizacao para operar como PCM portuario oficial.

## Fluxos reais comprovados

1. Horimetro: `web_app/index.html` abre "Disponibilidade e Horimetro" -> `submitHourmeter()` em `web_app/static/js/app.js` -> `POST /equipamentos/{id}/horimetros` ou fila offline -> `record_hourmeter()` -> tabelas `hourmeter_readings` e `equipment_operational_states`.
2. Preventiva: `PCMPage`/`PreventivePlanDialog` em `desktop/ui/pcm_page.py` -> `desktop/api_client.py` -> rotas `/pcm/planos-preventivos` -> `create_preventive_plan()` -> tabela `preventive_plans`.
3. Geracao: botao "Gerar preventivas vencidas" -> `POST /pcm/gerar-preventivas` -> `generate_due_preventives()` -> `maintenance_schedules`, `maintenance_schedule_items` e `maintenance_work_orders`.
4. Conclusao: tela de manutencao -> `PUT /manutencao/itens/{id}` -> `update_schedule_item()` -> `advance_preventive_plan_after_completion()` -> proxima data/horimetro do plano.
5. Emergencial: Web Mobile -> `POST /emergenciais` -> triagem/conversao -> OS -> iniciar, concluir reparo, testar e liberar -> `emergency_events`, `maintenance_work_orders` e `work_order_executions`.

## Maturidade atual

Classificacao geral: **intermediaria (3 de 5)**.

- Forte em reaproveitamento de estrutura, cobertura de modulos e operacao mobile.
- Intermediaria em PCM, pois as entidades e fluxos principais existem, mas varias regras portuarias ainda sao genericas.
- Inicial em Base Mestre/Power BI, historico de movimentacao, importacao controlada de RTG/LBS e governanca fina de horimetros.

## Quadro consolidado

As contagens abaixo representam criterios auditados na matriz `03_DE_PARA_FUNCIONAL.md`, nao quantidade de arquivos.

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
| **Total** | **26** | **32** | **17** | **0** | **2** |

## Pontos reaproveitaveis

- `Vehicle` como cadastro mestre atual, complementado por `EquipmentProfile` e `EquipmentFamily`.
- `OperationalLocation` para area/patio/berco e `EquipmentLink` para relacao LBS-Spreader.
- `HourmeterReading` e `EquipmentOperationalState` para leitura e estado consolidado.
- `MaintenanceSchedule`, `MaintenanceScheduleItem` e `MaintenanceWorkOrder` para agenda, execucao e OS.
- `PreventivePlan` para gatilhos por calendario, horimetro ou ambos.
- `EmergencyEvent` e `WorkOrderExecution` para corretiva emergencial.
- `AuditLog` e hooks de `audit_service.py` para trilha geral.
- PWA offline e acesso por QR/NFC em `mobile_operation_service.py`.
- Relatorios PDF/Excel e integracao com Supabase Storage.

## Principais lacunas

- Nao existe historico de movimentacao fisica do equipamento; o local atual pode ser alterado no perfil.
- Nao existe tela central diaria de horimetros com anterior, variacao, alertas e correcao autorizada.
- Nao existem ciclos portuarios oficiais de 500 a 6.000 horas nem reinicio configurado.
- A geracao de preventivas vencidas depende de chamada manual; `render.yaml` nao declara cron.
- A OS tem poucos campos frente ao escopo oficial e usa `OS-000001`, sem familia/tipo/data na numeracao.
- Nao existem cancelamento e reabertura formal de OS.
- Backlog nao possui todas as situacoes, faixas de idade e visoes exigidas.
- MTBF, MTTR e disponibilidade existem com conceitos diferentes ou cobertura parcial.
- A Base Mestre API foi criada na Fase 5 com contrato `pcm.base_mestre.v1`; a tela dedicada e a homologacao Power BI ainda estao pendentes.
- A importacao Excel atual trata apenas planilhas `CARRETAS` e `CAVALOS`, sem staging, preview e rollback de RTG/LBS.

## Principais riscos

1. **Schema divergente:** `create_app()` executa `db.create_all()`, `ensure_runtime_schema()` e novamente `db.create_all()`. As migrations nao sao hoje a unica fonte de evolucao do schema.
2. **Producao nao comparada:** o mapa do banco representa codigo e migrations; colunas/tabelas orfas no PostgreSQL real continuam "necessita validacao".
3. **Indicador incompleto:** disponibilidade divide tempo disponivel apenas pelo tempo coberto por eventos, em `build_availability_overview()`, e nao por todo o periodo oficial.
4. **Concorrencia de OS:** a unicidade existe no banco, mas a numeracao posterior ao `flush()` nao possui teste especifico de concorrencia.
5. **Dados mestres:** nao houve homologacao, neste ciclo, dos 22 RTG, 16 LBS e respectivos Spreaders.
6. **Evidencias:** existem caminhos de arquivo nas entidades, mas nao uma tabela normalizada com hash, tamanho, descricao, usuario e vinculos multiplos.

## Recomendacao

Nao criar outro sistema. Evoluir o atual em pequenas migrations aditivas e modulos integrados. A ordem segura e: proteger e comparar producao; fechar arquitetura-alvo; corrigir fundamentos de OS/localizacao/horimetro; consolidar preventiva e backlog; concluir indicadores/dashboard/Base Mestre; importar inventario com staging; homologar e implantar.

Nenhuma implementacao deve iniciar antes da aprovacao deste diagnostico e da comparacao do schema PostgreSQL de producao com `backend/app/models/` e `migrations/versions/`.

## Evidencias principais

- Inicializacao e saude: `backend/app/__init__.py`, funcoes `create_app()` e `health()`.
- Configuracao de banco: `backend/app/config.py`, funcao `_normalize_database_url()` e `Config.SQLALCHEMY_DATABASE_URI`.
- Models: `backend/app/models/`.
- Rotas: `backend/app/routes/`.
- PCM: `backend/app/services/pcm_service.py` e `desktop/ui/pcm_page.py`.
- Horimetro/disponibilidade: `backend/app/services/availability_service.py` e `web_app/static/js/app.js`.
- OS/emergencial: `backend/app/services/maintenance_service.py` e `backend/app/services/emergency_service.py`.
- Inteligencia: `backend/app/services/maintenance_intelligence_service.py`.
- Auditoria: `backend/app/services/audit_service.py`.

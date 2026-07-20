# Diagnostico e planejamento - Dashboard Operacional de Manutencao

Data: 2026-07-20

## 1. Objetivo

Adicionar ao sistema existente um dashboard operacional de manutencao e um modo TV, sem criar um segundo sistema, sem duplicar regras e usando exclusivamente dados reais.

Rotas pretendidas:

- `/dashboard-manutencao`
- `/dashboard-manutencao/tv`

## 2. Arquitetura atual confirmada

| Camada | Implementacao atual | Reaproveitamento para o dashboard |
| --- | --- | --- |
| Backend | Flask + Flask-SQLAlchemy | Criar uma camada agregadora de leitura no backend, seguindo o padrao de `services/`. |
| Banco | PostgreSQL por `DATABASE_URL`; SQLite somente como fallback local | Consultas agregadas no PostgreSQL. Nenhuma tabela nova e necessaria no primeiro corte. |
| Desktop | PySide6 | Usar como referencia funcional e visual; nao compartilhar componentes diretamente com Web. |
| Web Mobile | HTML, CSS e JavaScript estatico em `web_app/` | Estender a SPA atual e reutilizar `apiFetch`, sessao JWT, tokens de cor, cards e estados de erro. |
| Deploy | Render: API Gunicorn e site estatico separados | Rotas Web precisam de arquivos/estrategia explicita de fallback no site estatico. |

Evidencias principais:

- `backend/app/__init__.py`: fabrica Flask, banco, CORS e `/health`.
- `backend/app/config.py`: seleciona PostgreSQL por `DATABASE_URL` e le `PORTUARY_ONLY_MODE`.
- `render.yaml`: publica `backend` como API e `web_app` como site estatico.
- `web_app/static/js/app.js`: SPA autenticada, com `apiFetch` e token Bearer.
- `desktop/ui/dashboard_page.py`: dashboard executivo atual.
- `desktop/ui/availability_page.py`: painel operacional de disponibilidade.

## 3. Funcionalidades e dados reutilizaveis

### 3.1 Disponibilidade e horimetro

- Models: `EquipmentOperationalState`, `EquipmentStatusEvent` e `HourmeterReading` em `backend/app/models/operational_availability.py`.
- API: `GET /disponibilidade/visao` em `backend/app/routes/availability.py`.
- Regra existente: `build_availability_overview()` em `backend/app/services/availability_service.py` calcula a disponibilidade pelo tempo de eventos com status `DISPONIVEL` ou `RESTRICAO` dividido pelo tempo coberto por apontamentos.
- Sem apontamento nao e disponibilidade. O sistema ja devolve `null`/"sem medicao" quando nao ha cobertura historica.

### 3.2 PCM, preventivas, backlog e OS

- Models: `PreventivePlan`, `MaintenanceSchedule`, `MaintenanceScheduleItem`, `MaintenanceWorkOrder`, `MaintenanceMaterial` e `WorkOrderExecution`.
- APIs existentes: `GET /pcm/agenda`, `GET /pcm/backlog`, `GET /manutencao/visao`, `GET /manutencao/programacoes` e os fluxos de OS/emergencial.
- `build_maintenance_overview()` ja entrega OS abertas, atrasadas, bloqueadas e concluidas, alem de percentual de conclusao do cronograma mensal.
- A origem da manutencao e real: `CHECKLIST_NC`, `ATIVIDADE` e `PREVENTIVA`; emergenciais sao identificados pelo `source_key` do agendamento.

### 3.3 Confiabilidade e alertas

- `build_maintenance_intelligence_overview()` em `backend/app/services/maintenance_intelligence_service.py` consolida disponibilidade, backlog, preventivas vencendo/vencidas, estoque baixo e alertas.
- MTTR e calculado de `repair_started_at` ate `released_at`.
- MTBF e calculado entre a liberacao anterior e a proxima `failure_started_at`, por equipamento.
- Alertas ja existem para emergencial critica aberta, preventiva vencida e estoque abaixo do minimo.
- API existente: `GET /relatorios/manutencao-executivo`, restrita a `admin` e `gestor`.

### 3.4 Estrutura de ativos

- Modelos: `Vehicle`, `EquipmentProfile`, `EquipmentFamily`, `OperationalLocation` e `EquipmentLink`.
- Familias e locais permitem filtros dinamicos. O dashboard nao deve fixar LBS, RTG ou Spreader em codigo; deve carregar os grupos ativos no cadastro.
- O modo portuario ja e controlado por `PORTUARY_ONLY_MODE`.

### 3.5 Interface existente

- O Web atual usa a paleta institucional definida em `web_app/static/css/styles.css`: azul, verde, vermelho, amarelo, cinzas, cards arredondados e fontes Bahnschrift/Segoe.
- O desktop ja possui `StatCard`, tabela de itens criticos e semaforo executivo. Eles servem como referencia, mas o componente PySide6 nao pode ser reutilizado diretamente no HTML/JS.

## 4. Autenticacao e permissoes

- Login em `POST /login`; token assinado e enviado como `Authorization: Bearer`.
- `auth_required` valida sessao e revogacao em `backend/app/services/auth_service.py`.
- Regra atual de gestao: somente `admin` e `gestor` em `user_has_management_access()`.
- Ainda nao ha permissao especifica para "visualizar dashboard", "ver custos", "exportar" ou "modo TV".

Decisao recomendada:

1. A rota normal exige sessao autenticada e, no primeiro corte, usa a regra atual `admin`/`gestor`.
2. O modo TV nao deve ser publico. Deve receber, em etapa propria, um token de somente leitura, revogavel e com expiracao; nunca reutilizar senha, token do usuario ou chave Supabase no navegador.

## 5. Indicadores: viabilidade atual

| Indicador | Situacao | Fonte/regra real |
| --- | --- | --- |
| Total de equipamentos e grupos | Pronto | `vehicles`, `equipment_profiles`, `equipment_families`. |
| Disponiveis, indisponiveis e em manutencao | Pronto | `equipment_operational_states`. |
| Disponibilidade por ativo/grupo | Pronto quando houver eventos | `equipment_status_events` + `build_availability_overview()`. |
| Horimetro atual | Pronto quando registrado | `equipment_operational_states.latest_hourmeter`. |
| OS abertas, atrasadas, bloqueadas e concluidas | Pronto quando houver OS | `maintenance_work_orders` + `build_maintenance_overview()`. |
| Preventivas pendentes/vencidas | Pronto quando houver planos | `preventive_plans` + `plan_due_state()`. |
| Backlog | Pronto quando houver OS | `build_backlog()`. |
| MTTR e MTBF | Regra pronta; depende de execucoes completas | `work_order_executions` com datas de falha, reparo e liberacao. |
| Alertas criticos | Pronto quando regras forem avaliadas | `automation_executions`, emergenciais, preventivas e materiais. |
| Falhas por ativo | Possivel com OS/checklist/atividades | Requer definir uma consulta unica para nao misturar conceitos. |
| Reincidencia por componente/causa | Parcial | Ha item de checklist e diagnostico textual; nao ha classificacao estruturada unica de causa/componente. |
| Custos por ativo/grupo/fornecedor | Nao disponivel ainda | Os models de material guardam quantidade e estoque, mas nao preco, mao de obra, servico externo, fornecedor ou custo de OS. |
| Ocorrencias por turno | Nao disponivel ainda | Nao ha campo estruturado de turno nos eventos de manutencao. |
| Comparacao com periodo anterior | Possivel quando houver historico | Deve usar a mesma consulta agregada com janela anterior equivalente. |

## 6. Situacao dos dados validada nesta auditoria

- A API de producao respondeu `HTTP 200` em `/health` com `database: ok` em 2026-07-20.
- O PostgreSQL local em `127.0.0.1:5432` recusou conexao durante esta auditoria. Por isso, contagens locais de eventos, OS, planos, horimetros e materiais nao foram reconfirmadas agora.
- Esta indisponibilidade local nao autoriza dados ficticios: o dashboard deve mostrar "Sem dados" quando nao houver registros reais.

## 7. Riscos e dependencias antes de implementar

1. O Web e um site estatico de pagina unica. As rotas `/dashboard-manutencao` e `/dashboard-manutencao/tv` exigem arquivos HTML proprios ou fallback configurado; somente adicionar uma tela na SPA nao cria URLs diretas.
2. Consultar cada modulo separadamente no navegador causaria lentidao e divergencia. O backend deve expor um payload agregador versionado e paginado.
3. O modo TV nao pode ficar protegido por token de usuario no endereco, pois ele pode vazar pelo navegador/TV. Precisa de token dedicado somente leitura.
4. MTBF, MTTR, tendencias e comparativos precisam de disciplina de registro. Sem datas de falha/reparo/liberacao e eventos de status, o resultado correto e "Sem dados", nao zero.
5. Custos, fornecedor, causa, componente e turno ainda requerem campos/modelagem antes de aparecerem como KPI confiavel.
6. Indices so devem ser criados depois de medir as consultas agregadas com dados reais; nao ha migration necessaria para a primeira etapa de leitura.

## 8. Plano de implementacao proposto

### Fase 1 - Contrato de dados e API agregada

- Criar um servico de leitura `maintenance_dashboard_service`.
- Criar endpoints autenticados de resumo, disponibilidade, ordens, preventivas, falhas e ativos criticos.
- Reutilizar regras existentes; nao duplicar MTBF, MTTR, backlog nem disponibilidade.
- Padronizar filtros: periodo, familia, ativo e local no primeiro corte.
- Entrega: JSON real com estados `sem dados`, permissao e erro.

### Fase 2 - Tela operacional Web

- Adicionar o acesso separado no Web existente.
- Criar cards, filtros, tabela de pendencias e estados de carregamento/erro/vazio.
- Reutilizar `apiFetch`, autenticacao, tokens CSS e componentes de card/lista atuais.
- Exibir somente graficos cujos dados estejam disponiveis; demais ficam com aviso objetivo de dado ainda nao registrado.

### Fase 3 - Graficos e desempenho

- Adicionar graficos leves sem dependencia nova, ou aprovar uma biblioteca antes da instalacao.
- Disponibilidade por familia/ativo, evolucao, OS por status, preventivas e ranking de falhas.
- Medir consultas no PostgreSQL antes de criar indices e aplicar cache curto no backend.

### Fase 4 - Modo TV seguro

- Criar `/dashboard-manutencao/tv` com layout 16:9, alto contraste, relogio, atualizacao a cada 60 segundos e rotacao de telas.
- Implementar token de leitura dedicado, expiravel e revogavel.
- Ocultar valores sensiveis (custos e detalhes) sem permissao explicita.

### Fase 5 - Dados faltantes e governanca

- Com aprovacao, modelar custo de peca/mao de obra/servico externo, fornecedor, causa, componente e turno.
- Criar migrations, formularios e validacoes para alimentar os indicadores hoje indisponiveis.
- Configurar metas e limites operacionais em `system_settings`, sem valores ficticios.

### Fase 6 - Validacao e liberacao

- Testes de API, calculos, permissoes, tela normal e TV.
- Validacao em 1920x1080, notebook, tablet e celular.
- Checagem de console, falha de rede, dados vazios, atualizacao automatica e ausencia de regressao nos modulos atuais.

## 9. Primeira entrega recomendada

Implementar somente as Fases 1 e 2. Elas entregam uma tela autenticada com dados reais ja existentes, sem tocar em migrations nem inventar campos. O modo TV e os graficos avancados devem vir depois que o contrato de dados for validado.

## 10. Execucao da Fase 1 - contrato de dados

Executada em 2026-07-20, sem migration nem alteracao de dados operacionais.

- Novo servico: `backend/app/services/maintenance_dashboard_service.py`.
- Novo blueprint protegido: `backend/app/routes/maintenance_dashboard.py`.
- Endpoints somente leitura: `GET /dashboard-manutencao/filtros`, `/resumo`, `/disponibilidade`, `/ordens`, `/preventivas` e `/ativos-criticos`.
- Acesso inicial: somente `admin` e `gestor`, reutilizando a permissao atual de gestao.
- Filtros aplicados: periodo, familia, equipamento e local.
- Testes: contrato do dashboard, disponibilidade e inteligencia de manutencao.

O Web e o modo TV nao foram alterados nesta fase. Eles serao a Fase 2, depois da validacao deste contrato de dados.

## 11. Execucao da Fase 2 - tela operacional Web

Executada em 2026-07-20, sem migration, sem alteracao de dados operacionais e sem nova dependencia de frontend.

- Nova rota estatica autenticada: `web_app/dashboard-manutencao/index.html` em `/dashboard-manutencao/`.
- Novo script: `web_app/static/js/maintenance-dashboard.js`, reutilizando a sessao e a URL de API ja usadas pelo Web Mobile.
- Novo estilo responsivo: `web_app/static/css/maintenance-dashboard.css`, preservando os tokens visuais existentes.
- Novo atalho no menu inicial para perfis `admin` e `gestor`; os demais perfis nao visualizam o acesso.
- Filtros entregues: periodo, familia, equipamento e local.
- Dados exibidos: situacao dos ativos, disponibilidade, OS, preventivas, ativos criticos, MTTR e MTBF quando houver registros reais.
- Dados indisponiveis permanecem explicitamente como `SEM DADOS`; custos, turno e causa estruturada continuam fora do painel por nao existirem no modelo atual.
- O modo TV, atualizacao automatica e graficos permanecem nas fases posteriores do plano.
- Testes: contrato estatico da nova tela e contrato do Web Mobile, alem da validacao de sintaxe JavaScript.

## 12. Execucao da Fase 3 - graficos e desempenho

Executada em 2026-07-20, sem migration, sem indice novo e sem dependencia externa de frontend.

- Novo endpoint somente leitura: `GET /dashboard-manutencao/graficos`.
- Graficos leves feitos com HTML e CSS: status operacional, OS por status, planos preventivos, evolucao de apontamentos e motivos registrados de indisponibilidade.
- A disponibilidade por familia continua usando o calculo existente; a tela passa a reutilizar a resposta do endpoint de graficos para evitar uma requisicao Web duplicada.
- O ranking usa somente o campo real `equipment_status_events.reason` para eventos `INDISPONIVEL`; nao o apresenta como causa estruturada de falha.
- A resposta informa a duracao da consulta e usa cache por processo de 15 segundos para os graficos, reduzindo repeticao imediata sem ocultar atualizacoes por longos periodos.
- Nenhum indice foi criado: a decisao fica para depois da observacao de tempos reais em producao.
- Testes: dados reais do fixture, permissao, cache curto, contrato da tela e sintaxe JavaScript.

## 13. Execucao da Fase 4 - modo TV seguro

Executada em 2026-07-20. Esta etapa adiciona uma tabela tecnica de acessos TV, sem alterar dados operacionais, cadastros, OS ou usuarios.

- Nova rota estatica: `web_app/dashboard-manutencao/tv/index.html` em `/dashboard-manutencao/tv/`.
- Layout de alto contraste e leitura a distancia, com relogio, tela cheia, rotacao de tres paineis a cada 20 segundos e atualizacao dos dados a cada 60 segundos.
- Novo modelo `DashboardTvAccessToken`: armazena somente o hash da credencial, emissor, expiracao, revogacao e ultimo uso. O valor bruto nunca e persistido.
- Gestao protegida por `admin` ou `gestor`: `GET` e `POST /dashboard-manutencao/tv/acessos`, `DELETE /dashboard-manutencao/tv/acessos/<id>`.
- Leitura TV por `GET /dashboard-manutencao/tv/dados` usando exclusivamente o header `X-Dashboard-TV-Token`; nao aceita token normal de usuario nem senha.
- A tela TV pede o codigo manualmente e o guarda somente em `sessionStorage`, nao na URL e nem em `localStorage`.
- A carga TV omite motivos, observacoes, responsaveis, itens individuais, custos e outros detalhes sensiveis; exibe apenas KPIs e agregados operacionais.
- Credenciais geradas e revogadas sao auditadas, e `token_hash` foi marcado como campo sensivel para nao aparecer em logs de auditoria.
- Testes: emissao, listagem sem segredo, leitura restrita, revogacao, permissao, contrato estatico e sintaxe JavaScript.

## 14. Execucao da Fase 5 - dados faltantes e governanca

Executada em 2026-07-20 com migration aditiva em tempo de inicializacao. Nenhum cadastro, historico, estoque, checklist ou OS existente foi apagado ou alterado automaticamente.

- `MaintenanceWorkOrder` passou a aceitar classificacao opcional de causa da falha, componente afetado e turno informado pela operacao.
- Nova tabela `maintenance_work_order_costs`: custo por OS, com categoria `PECA`, `MAO_DE_OBRA` ou `SERVICO_EXTERNO`, descricao, fornecedor, componente, valor, data, observacao e responsavel pelo registro.
- `ensure_runtime_schema()` cria a tabela e adiciona as tres colunas de classificacao quando necessario. A mudanca e somente aditiva e pode ser aplicada no PostgreSQL/Supabase durante o proximo inicio da API.
- Endpoints restritos a `admin` e `gestor`: consulta e classificacao de OS, inclusao/exclusao de custo e leitura/gravacao das metas de governanca.
- Metas persistidas em `system_settings`: disponibilidade minima, MTTR maximo, MTBF minimo e conformidade preventiva minima. Todas iniciam vazias; o sistema nao inventa meta nem custo.
- Dashboard normal ganhou o painel `GOVERNANCA`, que lista as OS do filtro atual e permite registrar os dados. O modo TV nao recebe custos nem dados sensiveis.
- Inclusao, alteracao e exclusao de dados de governanca geram eventos de auditoria.
- Testes: permissao financeira, validacao de limites, custo por OS, auditoria, atualizacao da disponibilidade de dados, regressao do dashboard, Web Mobile e modo TV.

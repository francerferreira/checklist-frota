# Gap backlog

## Escala

- Prioridade P1: fundamento/risco de dados.
- Prioridade P2: operacao.
- Prioridade P3: gestao.
- Prioridade P4: evolucao.
- Esforco em dias-pessoa, antes de refinamento tecnico e homologacao.

| ID | Epico | Historia | Descricao | Dependencia | Risco | Prioridade | Esforco |
|---|---|---|---|---|---|---|---:|
| GOV-01 | Protecao | Comparar PostgreSQL | Comparar schema fisico, models, migrations e runtime schema | acesso producao read-only | Alto | P1 | 2-4 |
| GOV-02 | Protecao | Backup restauravel | Gerar backup e testar restauracao de banco/anexos | GOV-01 | Alto | P1 | 2-3 |
| GOV-03 | Schema | Fonte unica de migration | Planejar retirada gradual de mutacoes em runtime | GOV-01 | Alto | P1 | 3-5 |
| EQ-01 | Equipamentos | Homologar inventario | Conciliar 22 RTG, 16 LBS e Spreaders com IDs/familias/seriais | acesso aos dados oficiais | Alto | P1 | 3-5 |
| EQ-02 | Localizacao | Historico de movimento | Registrar origem, destino, motivo, data e responsavel | arquitetura-alvo | Alto | P1 | 4-6 |
| EQ-03 | Equipamentos | Tela individual dinamica | Consolidar status, horimetro, OS, backlog, preventiva, docs e KPIs | APIs consolidadas | Medio | P2 | 8-12 |
| OS-01 | OS | Modelo oficial | Acrescentar tipo, classificacao, especialidade, equipe, fornecedor, horimetros e tempos | de-para aprovado | Alto | P1 | 6-10 |
| OS-02 | OS | Numeracao oficial | Definir formato, preservar legado e testar concorrencia | OS-01 | Alto | P1 | 3-5 |
| OS-03 | OS | State machine | Cancelar, reabrir, suspender e registrar historico/motivo | OS-01 | Alto | P1 | 5-8 |
| OS-04 | Evidencias | Anexos normalizados | Persistir metadados/hash e vinculos multiplos usando storage atual | arquitetura-alvo | Medio | P2 | 5-8 |
| OS-05 | Corretiva | Unificar execucao | Reusar inicio/reparo/teste/liberacao em todos os tipos aplicaveis | OS-01/03 | Alto | P2 | 5-8 |
| HM-01 | Horimetro | Central diaria | Grade Desktop com anterior, atual, diferenca, usuario e observacao | APIs atuais | Medio | P1 | 5-8 |
| HM-02 | Horimetro | Alertas e limites | Alertar igual e variacao anormal por parametro | premissas operacionais | Alto | P1 | 3-5 |
| HM-03 | Horimetro | Correcao autorizada | Fluxo append-only, motivo, aprovador, auditoria e recalc | permissoes/auditoria | Alto | P1 | 5-8 |
| HM-04 | Horimetro | Recalculo dependente | Atualizar previsao preventiva, data estimada e dashboards | preventiva oficial | Alto | P2 | 4-6 |
| PV-01 | Preventiva | Ciclos 500-6000 | Configurar sequencia, reinicio, ciclo anterior/proximo | homologacao tecnica | Alto | P1 | 6-10 |
| PV-02 | Preventiva | Faixas automaticas | Calcular horas restantes e situacoes configuraveis | HM-04/PV-01 | Alto | P1 | 4-6 |
| PV-03 | Preventiva | Central unica | Programar, iniciar, atualizar e concluir pela Central PCM | OS oficial | Alto | P1 | 8-12 |
| PV-04 | Preventiva | Job idempotente | Gerar preventivas automaticamente sem duplicar OS | PV-01/02 e job infra | Alto | P2 | 3-5 |
| PV-05 | Preventiva | Execucao/historico | Preservar ciclo, horimetro realizado, desvios e proxima previsao | PV-03 | Alto | P2 | 5-8 |
| BK-01 | Backlog | Status oficiais | Incluir esperas e suspensao com transicoes validas | OS-03 | Medio | P2 | 3-5 |
| BK-02 | Backlog | Idade e faixas | Calcular 0-7, 8-15, 16-30, 31-60 e >60 | BK-01 | Baixo | P2 | 2-3 |
| BK-03 | Backlog | Filtros e rankings | Familia, ativo, tipo, responsavel, local e cinco mais antigas | EQ-02/BK-02 | Medio | P2 | 4-6 |
| KPI-01 | Indicadores | Conceitos oficiais | Homologar universos e formulas MTTR, MTBF, disponibilidade e paradas | OS/HM | Alto | P1 | 3-5 |
| KPI-02 | Indicadores | Calculos oficiais | Implementar por periodo/familia/ativo/tipo/responsavel | KPI-01 e Base Mestre | Alto | P3 | 7-10 |
| KPI-03 | Indicadores | Cumprimento preventivo | Programada, realizada, prazo e desvios | PV-05 | Medio | P3 | 3-5 |
| BI-01 | Base Mestre | Dataset consolidado | Uma linha por intervencao, IDs estaveis, filtros e paginacao | models oficiais | Alto | P3 | 6-10 |
| BI-02 | Base Mestre | Exportacoes | JSON, CSV e Excel consistentes para Power BI | BI-01 | Medio | P3 | 3-5 |
| DASH-01 | Dashboard | Cards oficiais | OS, backlog, preventivas, KPIs e horas paradas | KPI/BI | Medio | P3 | 4-6 |
| DASH-02 | Dashboard | Graficos e filtros | Graficos por familia, ativo, local, idade, tipo e ciclo | DASH-01 | Medio | P3 | 6-10 |
| PERM-01 | Permissoes | Matriz backend-first | Definir abrir/alterar/concluir/corrigir/exportar/importar/auditar | aprovacao operacional | Alto | P1 | 4-6 |
| PERM-02 | Permissoes | Novos perfis | Supervisor, PCM, administrativo, tecnico e consulta, se aprovados | PERM-01 | Medio | P2 | 3-5 |
| AUD-01 | Auditoria | Eventos PCM | Motivo/contexto para OS, horimetro, movimento, preventiva e importacao | novos fluxos | Alto | P1 | 4-6 |
| IMP-01 | Importacao | Staging por lote | Upload, preview, validacao, erros, confirmar e rollback | EQ-01/GOV-02 | Alto | P1 | 6-10 |
| IMP-02 | Importacao | Mapper RTG | Mapear planilha oficial sem gravacao direta | IMP-01 | Alto | P2 | 3-5 |
| IMP-03 | Importacao | Mapper LBS/Spreader | Mapear ativos e vinculos/seriais | IMP-01 | Alto | P2 | 4-6 |
| TEST-01 | Qualidade | Suites criticas | Concorrencia OS, multi-dia, horimetro, ciclos, KPIs, permissoes e import | todos os epicos | Alto | P1 | 10-15 |
| OPS-01 | Operacao | Observabilidade/job | Logs, monitor, cron e alerta de falha | servicos idempotentes | Medio | P4 | 4-6 |
| OPS-02 | Operacao | Treinamento/implantacao | Manual, perfis, piloto e suporte | homologacao | Medio | P4 | 4-7 |

## Ordem recomendada

1. `GOV-*`, `EQ-01`, `KPI-01` e `PERM-01` antes de migration funcional.
2. `EQ-02`, `OS-*`, `HM-*` e `AUD-01` como fundamentos.
3. `PV-*` e `BK-*` como operacao PCM.
4. `BI-*`, `KPI-*` e `DASH-*` como gestao.
5. `IMP-*` somente depois do cadastro mestre estabilizado.
6. `TEST-*` acompanha cada entrega, com homologacao final independente.

## Itens explicitamente fora deste ciclo

- Implementar qualquer historia acima.
- Alterar schema, model, migration, API, service, tela ou permissao.
- Importar dados reais.
- Trocar formulas em producao.

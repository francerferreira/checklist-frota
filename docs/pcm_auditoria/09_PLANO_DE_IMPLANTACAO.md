# Plano de implantacao

## Principios

- Evoluir o sistema atual, sem criar outro produto.
- Desktop para gestao/PCM e Web Mobile para operacao.
- Uma migration aditiva por entrega, com backup e rollback testado.
- Feature flags ou ativacao controlada quando houver convivencia de regra antiga/nova.
- Nenhuma formula vira oficial sem aprovacao operacional.
- Cada fase para em um gate de aceite antes da seguinte.

## Fases e estimativas

Estimativas em dias-pessoa, nao em dias corridos. Nao incluem espera por acesso, decisao ou homologacao.

| Fase | Objetivo | Entregas | Estimativa | Gate de saida |
|---|---|---|---:|---|
| 0 - Protecao | tornar mudanca reversivel | branch, schema dump, backup banco/storage, restore test, migrations atuais | 2-4 | restauracao comprovada |
| 1 - Auditoria | conhecer o existente | 12 documentos deste diretorio | concluida neste ciclo | aprovacao do diagnostico |
| 2 - Arquitetura-alvo | aprovar conceitos | ADRs de equipamento, OS, tempos, ciclo, backlog, KPI, permissao e anexo | 4-6 | de-para operacional assinado |
| 3 - Banco e backend | criar fundamentos | migrations aditivas, services, APIs, auditoria, compatibilidade | 18-28 | testes de banco/API e rollback |
| 4 - Telas operacionais | entregar uso real | tela individual, horimetro central, OS/corretivas, Central de Preventivas, backlog | 20-30 | homologacao por perfil em piloto |
| 5 - Gestao | consolidar decisao | Base Mestre, KPIs, dashboard, relatorios, Power BI | 12-18 | reconciliacao manual x sistema |
| 6 - Importacao | carregar inventario controlado | staging, preview, RTG, LBS, Spreader, reconciliacao e rollback | 8-12 | lote piloto sem divergencia |
| 7 - Testes/homologacao | reduzir risco | regressao, desempenho, seguranca, permissao, mobile/offline e UAT | 10-15 | aceite formal e plano de corte |
| 8 - Producao | ativar com seguranca | deploy, migrations, monitoramento, treinamento e suporte | 4-7 | periodo assistido concluido |
| **Total futuro apos auditoria** |  |  | **78-120** |  |

## Fase 0 - Protecao

1. Registrar commit/tag e versoes implantadas.
2. Obter schema-only e backup de dados PostgreSQL.
3. Inventariar objetos no Supabase Storage.
4. Executar restauracao em ambiente isolado.
5. Comparar `alembic current/heads`, models e `runtime_schema_service.py`.
6. Bloquear migration destrutiva sem aprovacao.

## Fase 2 - Arquitetura-alvo

Status em 17/07/2026: executada tecnicamente nos documentos `14_ADRS_ARQUITETURA_ALVO_FASE_2.md`, `15_DE_PARA_OPERACIONAL_FASE_2.md` e `16_RESULTADO_FASE_2_ARQUITETURA_ALVO.md`. O gate operacional permanece pendente e migrations continuam em `NO-GO`.

Decisoes obrigatorias:

- `Vehicle` como raiz tecnica e `EquipmentFamily` como classificacao oficial.
- Local atual + movimento historico.
- `MaintenanceWorkOrder` como unica OS e numero como unico identificador.
- Origem separada do tipo oficial de manutencao.
- Conceitos de tempos, falha, reparo, indisponibilidade e horas da equipe.
- Horimetro append-only com correcao autorizada.
- Sequencia de ciclos preventivos e regra apos 6.000 h.
- Matriz de transicao de OS/backlog.
- Formulas oficiais de MTTR, MTBF, disponibilidade e cumprimento.
- Matriz de permissao e eventos de auditoria.

## Fase 3 - Banco e backend por modulos

### 3A Equipamento e governanca

- Movimento de localizacao.
- Parametros operacionais.
- Permissoes e auditoria de dominio.
- Evidencias normalizadas, se aprovadas.

### 3B OS e corretivas

- Campos e classificacoes oficiais.
- Numeracao concorrente e compativel.
- State machine, eventos temporais, cancelamento/reabertura.
- Reuso do fluxo emergencial nas OS aplicaveis.

### 3C Horimetro

- Alertas, limites, correcao e recalculo.
- Endpoints de grade diaria e aprovacao.
- Manter sincronizacao mobile idempotente.

### 3D Preventiva e backlog

- Ciclos 500-6000, situacoes e execucao.
- Job idempotente de geracao.
- Status/faixas/filtros de backlog.

Cada subfase deve ter migration, teste e rollback proprios; nao aplicar tudo em uma unica release.

## Fase 4 - Telas operacionais

1. Evoluir `EquipmentPage` e criar detalhe dinamico do ativo.
2. Evoluir `AvailabilityPage` para lancamento diario central.
3. Evoluir `PCMPage` como Central de Preventivas.
4. Reusar `MaintenancePage` para corretiva programada e execucao.
5. Reusar Web Mobile para horimetro, emergencia, OS, QR/NFC e offline.
6. Validar acessibilidade, resolucao Desktop e celulares operacionais.

## Fase 5 - Gestao

- Criar consulta Base Mestre paginada.
- Reconciliar indicadores com amostra manual aprovada.
- Publicar cards antes de graficos complexos.
- Expor CSV/Excel/JSON tipados.
- Validar consumo no Power BI sem acesso direto irrestrito ao banco.

## Fase 6 - Importacao

Fluxo obrigatorio: upload -> staging -> preview -> validacao -> relatorio de erros -> aprovacao -> transacao -> reconciliacao -> fechamento do lote. Nunca gravar diretamente ao selecionar o Excel.

## Fase 7 - Testes e homologacao

- Piloto com poucos RTG/LBS e ao menos um Spreader vinculado.
- Comparacao paralela com controles atuais.
- Teste de turno, meia-noite, multi-dia e operacao offline.
- Segregacao de perfis e tentativas negadas.
- Evidencia de restore/rollback.

## Fase 8 - Producao

- Janela de mudanca e responsaveis nomeados.
- Backup imediatamente anterior.
- Migration observada, smoke tests e monitor de `/health`.
- Ativacao gradual por modulo/perfil.
- Suporte assistido e criterio objetivo de rollback.

## Dependencias externas

- Acesso read-only e janela de backup do PostgreSQL/Supabase.
- Planilhas oficiais e responsaveis por RTG/LBS/Spreader.
- Definicao operacional de formulas, ciclos, status e permissoes.
- Dispositivos reais para QR/NFC/offline.
- Responsavel pelo Power BI e contrato de atualizacao.

## Recomendacao de liberacao

Liberar primeiro cadastro/localizacao e OS; depois horimetro; depois preventiva/backlog; por ultimo indicadores/dashboard/importacao. Assim, os paineis nao tentam medir dados que ainda nao possuem regra confiavel.

Este plano e somente recomendacao do primeiro ciclo. A execucao deve aguardar aprovacao explicita.

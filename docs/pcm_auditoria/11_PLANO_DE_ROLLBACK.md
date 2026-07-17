# Plano de rollback

## Objetivo

Voltar a uma versao estavel sem perder checklists, OS, horimetros, historicos ou anexos. Rollback de codigo e rollback de dados sao operacoes diferentes e devem ser planejadas juntas.

## Pre-condicoes obrigatorias

1. Identificar commit, imagem/binario e revisao Alembic atuais.
2. Pausar gravacoes ou definir janela consistente.
3. Criar backup completo do PostgreSQL com verificacao de integridade.
4. Inventariar/espelhar objetos do bucket Supabase `evidencias`.
5. Exportar sequencias e numeros de OS existentes.
6. Testar restauracao em ambiente isolado.
7. Definir responsavel por autorizar rollback.

`backend/app/services/backup_service.py` e as rotas `/admin/backups/*` sao reaproveitaveis, mas nao substituem um ensaio real de restauracao do PostgreSQL e do Storage.

## Estrategia por tipo de mudanca

| Mudanca | Estrategia segura | Rollback |
|---|---|---|
| Codigo sem schema | deploy versionado | redeploy do commit anterior |
| Campo/tabela aditiva nao usada | manter schema compativel | voltar codigo; remover somente depois |
| Campo com backfill | registrar script e contagens | restaurar valores ou backup |
| Constraint nova | validar dados antes | remover constraint se bloquear operacao |
| Renomeacao | expand/contract com alias | codigo antigo continua lendo coluna antiga |
| Status/regra nova | feature flag/de-para | desativar regra e preservar eventos |
| Importacao | lote/staging | reverter apenas linhas do batch confirmado |
| Anexo | catalogo + storage | nao apagar objeto ate encerrar janela |
| Indicador/dashboard | versao da formula | voltar formula/exibicao, sem alterar fatos |

## Banco e migrations

- Toda migration deve possuir `upgrade()` e `downgrade()` tecnicamente avaliados.
- Preferir expandir, migrar, validar e somente depois contrair.
- Nao usar `DROP`, rename destrutivo ou `NOT NULL` imediato em dados legados.
- Antes do deploy: registrar `flask db current`/`alembic current` e `heads`.
- Em falha sem gravacoes novas: aplicar downgrade testado ou restaurar backup.
- Em falha apos novas gravacoes: preferir roll-forward corretivo; downgrade que apaga colunas pode destruir dados.
- A chamada de `ensure_runtime_schema()` deve ser considerada no plano, pois pode recriar/alterar objetos ao reiniciar a aplicacao.

## Preservacao do numero da OS

- Nunca renumerar `maintenance_work_orders.order_number` existente.
- Antes da mudanca, exportar `id`, `order_number`, `vehicle_id`, `schedule_item_id`, `status` e timestamps.
- Manter unique index durante transicao.
- Se houver nova sequencia/formato, iniciar em namespace que nao colida e registrar a ultima sequencia.
- Rollback de codigo deve continuar reconhecendo numeros antigos e novos.
- Nao criar identificador MTR/TRM como alternativa.

## Preservacao de anexos

- Banco guarda referencias; Storage guarda os objetos. O backup precisa dos dois lados.
- Registrar lista de objetos, tamanho e hash quando disponivel antes da release.
- Upload novo deve ocorrer com nome imutavel; evitar overwrite.
- Nao excluir anexos durante a janela de rollback.
- Em restauracao, primeiro recuperar banco, depois reconciliar referencias e objetos.

## Rollback por fase

### Fase 3 - Banco/backend

1. Desativar endpoints/flags novas.
2. Voltar codigo compativel.
3. Manter tabelas/colunas aditivas se nao causarem falha.
4. Downgrade somente com teste e sem perda de fatos novos.

### Fase 4 - Telas

1. Voltar Desktop/PWA anterior.
2. Invalidar cache do Service Worker de forma controlada.
3. Manter API retrocompativel durante a janela.

### Fase 5 - Indicadores/Base Mestre

1. Despublicar formula/dashboard novo.
2. Voltar versao de consulta.
3. Preservar dados brutos; nunca "corrigir" fatos para fazer indicador fechar.

### Fase 6 - Importacao

1. Bloquear confirmacao de novos lotes.
2. Identificar `batch_id`.
3. Reverter inserts/updates daquele lote conforme log antes/depois.
4. Reconciliar contagens, seriais e vinculos.
5. Se o lote nao for reversivel com seguranca, restaurar backup em janela aprovada.

## Gatilhos de rollback

| Sinal | Acao inicial | Criterio de rollback |
|---|---|---|
| `/health` 503 | parar rollout e verificar DB | persistencia apos limite definido |
| erro de migration | nao iniciar nova versao | schema parcial/incompativel |
| duplicidade de OS | bloquear geracao | qualquer colisao confirmada |
| perda/inversao de horimetro | bloquear lancamentos | fato incorreto sem correcao segura |
| indicadores divergentes | retirar selo/publicacao oficial | amostra nao fecha com fonte |
| fila offline duplicando | pausar sync nova | operacoes reaplicadas |
| permissao indevida | desativar modulo/flag | acesso sensivel confirmado |
| importacao inconsistente | interromper lote | mestre alterado fora do preview |

## Validacao apos rollback

- `/health` com banco e auditoria saudaveis.
- Login dos quatro perfis atuais.
- Consulta e criacao controlada de checklist.
- Leitura dos ultimos horimetros e OS.
- Contagem de OS e unicidade dos numeros.
- Consulta de agenda/backlog sem erro.
- Acesso a amostra de anexos.
- Sincronizacao mobile pendente sem duplicar.
- Registro do incidente e decisao de proximo passo.

## Regra de nao perda

Se houver dados novos validos depois do deploy, nao executar downgrade destrutivo. Exportar fatos novos, aplicar correcao compativel ou restaurar e reaplicar os fatos de forma auditada. O objetivo e voltar o comportamento, nao apagar a historia.

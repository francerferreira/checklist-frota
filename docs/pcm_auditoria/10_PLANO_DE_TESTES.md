# Plano de testes

## Objetivo

Validar cada evolucao sem perder as funcoes atuais de checklist, frota, lavagem, atividades, NC, manutencao e mobile. Os testes devem acompanhar cada modulo, nao ser deixados apenas para o fim.

## Camadas

| Camada | Ferramenta/abordagem | Foco |
|---|---|---|
| Unitario | pytest | formulas, validadores, state machines, numeracao |
| Integracao | pytest + Flask test client | service, transacao, auditoria e permissao |
| Banco | PostgreSQL de teste + Alembic | upgrade/downgrade, constraints, concorrencia |
| API | Flask test client/colecao HTTP | contratos, status, filtros, paginacao |
| Desktop | pytest-qt/contratos existentes | navegacao, campos, bloqueios e refresh |
| Web Mobile | Playwright | responsividade, offline, QR/NFC quando suportado |
| Regressao | suite atual | checklist, NC, lavagem, materiais, login e relatorios |
| Homologacao | roteiro com usuario | conceitos e fluxo real RTG/LBS |

## Baseline atual

Existem 35 arquivos em `tests/`, incluindo `test_availability_routes.py`, `test_emergency_work_order_routes.py`, `test_mobile_operations_routes.py`, `test_pcm_routes.py`, `test_audit_service.py`, testes de migrations e Playwright. A Fase 7 executou as suites tecnicas selecionadas em processos isolados.

Os resultados desta rodada estao em `19_RESULTADO_FASE_7_HOMOLOGACAO.md`. A homologacao operacional com equipe, inventario real e controles manuais ainda nao foi realizada.

## Casos de OS

| ID | Caso | Resultado esperado | Nivel |
|---|---|---|---|
| T-OS-01 | gerar duas OS sequenciais | numeros unicos e formato aprovado | unitario/integracao |
| T-OS-02 | gerar OS concorrentes | sem duplicidade ou numero perdido indevido | PostgreSQL/concorrencia |
| T-OS-03 | abrir por emergencial | evento e OS vinculados, status coerentes | integracao/API |
| T-OS-04 | abrir por programacao/preventiva | uma OS por item, sem duplicar reenvio | integracao |
| T-OS-05 | iniciar e concluir no mesmo dia | tempos positivos e campos obrigatorios | unitario/API |
| T-OS-06 | atravessar meia-noite/varios dias | duracao total correta | unitario |
| T-OS-07 | termino anterior ao inicio | rejeicao 400 sem commit | API/banco |
| T-OS-08 | concluir sem obrigatorios | rejeicao e mensagem clara | API/UI |
| T-OS-09 | cancelar com motivo | sai do backlog e mantem historico/auditoria | integracao |
| T-OS-10 | reabrir autorizada | volta ao backlog com evento e justificativa | permissao/auditoria |
| T-OS-11 | tentar reabrir sem permissao | 403 e nenhum efeito | seguranca |
| T-OS-12 | anexar evidencia | metadados e objeto consistentes | storage/integracao |

## Casos de horimetro

| ID | Caso | Resultado esperado | Nivel |
|---|---|---|---|
| T-HM-01 | valor maior | grava leitura e atualiza snapshot | unitario/API |
| T-HM-02 | valor igual | aplica alerta/regra homologada | unitario/UI |
| T-HM-03 | valor menor | rejeita, salvo fluxo de correcao aprovado | API |
| T-HM-04 | data futura | rejeita | unitario/API |
| T-HM-05 | mesma data/hora | unique/conflito amigavel | banco/API |
| T-HM-06 | variacao acima do limite | alerta/bloqueio conforme parametro | unitario |
| T-HM-07 | correcao autorizada | evento compensatorio, motivo e auditoria | integracao |
| T-HM-08 | correcao nao autorizada | 403, sem mudanca | permissao |
| T-HM-09 | leitura offline repetida | idempotencia/replay sem duplicar | mobile/API |
| T-HM-10 | conflito offline | item marcado para revisao, sem corrupcao | mobile/API |
| T-HM-11 | leitura aciona faixa preventiva | situacao e horas restantes recalculadas | integracao PCM |

## Casos de preventiva

| ID | Caso | Resultado esperado | Nivel |
|---|---|---|---|
| T-PV-01 | cadastrar ciclo 500 h | proximo ciclo/previsao corretos | unitario/API |
| T-PV-02 | percorrer 500 a 6000 h | sequencia integral sem salto | parametrizado |
| T-PV-03 | concluir 6000 h | reinicio conforme configuracao aprovada | unitario |
| T-PV-04 | calcular faixas 101,100,51,50,21,20,1,0,-1 | situacao exata nos limites | unitario |
| T-PV-05 | programar | OS unica, backlog, auditoria e tela individual | integracao |
| T-PV-06 | job repetido | nao duplica OS/agenda | integracao/idempotencia |
| T-PV-07 | iniciar/concluir fora da Central | negado conforme regra aprovada | permissao/UI |
| T-PV-08 | concluir na Central | historico, realizado e proxima previsao | ponta a ponta |
| T-PV-09 | plano pausado/encerrado | nao gera nova OS | unitario/integracao |
| T-PV-10 | falta horimetro atual | aviso e tratamento definido | API/UI |

## Backlog e indicadores

| ID | Caso | Resultado esperado |
|---|---|---|
| T-BK-01 | cada status oficial | entra/sai do backlog corretamente |
| T-BK-02 | idades 7, 8, 15, 16, 30, 31, 60, 61 | faixa correta |
| T-BK-03 | concluir/cancelar | sai da lista, permanece no historico |
| T-KPI-01 | amostra manual MTTR | resultado igual a planilha aprovada |
| T-KPI-02 | amostra manual MTBF por horimetro | resultado igual a calculo aprovado |
| T-KPI-03 | periodo sem apontamento | disponibilidade segue regra oficial |
| T-KPI-04 | paradas sobrepostas | nao conta tempo duas vezes |
| T-KPI-05 | parada multi-dia | horas do periodo corretas |
| T-KPI-06 | cumprimento preventiva | programadas/realizadas/prazo/desvio corretos |
| T-KPI-07 | filtros combinados | total detalhado fecha com agregado |

## Permissoes e auditoria

Para cada acao sensivel, testar matriz permitida e negada: abrir, alterar, programar, iniciar, concluir, cancelar/reabrir OS; lancar/corrigir horimetro; programar/concluir preventiva; importar/exportar; consultar auditoria.

Cada alteracao aprovada deve gerar evento com usuario, data/hora, entidade, id, acao, antes/depois e motivo quando aplicavel. Tentativas negadas nao podem alterar dados; o registro de tentativa de seguranca deve seguir decisao arquitetural.

## Importacao

| Caso | Esperado |
|---|---|
| arquivo valido RTG | preview correto e confirmacao transacional |
| arquivo valido LBS/Spreader | vinculos e seriais reconciliados |
| cabecalho/aba invalida | lote rejeitado com relatorio |
| equipamento duplicado | conflito sem sobrescrita silenciosa |
| serial repetido | rejeicao antes do commit |
| referencia inexistente | erro por linha |
| falha no meio do lote | rollback total ou estrategia de lote aprovada |
| reprocessamento | idempotente ou conflito explicito |
| cancelar antes de confirmar | zero alteracao no mestre |

## Interface e mobile

- Desktop em resolucoes operacionais usuais, sem ocultar botoes/campos.
- Web Mobile em Android e navegadores suportados.
- Online, offline, perda de rede durante envio e sincronizacao posterior.
- QR valido, invalido e ativo inativo.
- NFC suportado, nao suportado e permissao negada.
- Mensagens simples, sem expor stack trace ou segredo.

## Base Mestre e Power BI

- IDs estaveis, uma linha por intervencao e ausencia de celulas mescladas.
- Tipos consistentes em JSON/CSV/Excel.
- Datas ISO e duracoes numericas/documentadas.
- Paginacao sem perda/duplicacao.
- Filtros fecham com totais do sistema.
- Atualizacao incremental e volume representativo.
- Usuario de consulta com menor privilegio necessario.

## Desempenho minimo a definir

Antes da Fase 7, registrar metas aprovadas para: tempo de login, abertura de tela individual, consulta de backlog, dashboard, exportacao e sincronizacao mobile. Executar com volume semelhante a producao e observar queries N+1/indices.

## Criterio de aceite por historia

Uma historia so pode ser concluida quando houver: teste automatizado pertinente, evidencia do teste manual, permissao positiva/negativa, auditoria, migration/rollback quando aplicavel, documentacao do contrato e aprovacao operacional.

# Resultado da Fase 2 - Arquitetura-alvo

Data: 17/07/2026

Status: **EXECUTADA TECNICAMENTE, COM GATE OPERACIONAL PENDENTE**.

## Objetivo executado

Consolidar os contratos de equipamento, localizacao, OS, tempos, horimetro, preventiva, backlog, KPI, permissoes, auditoria e anexos antes de qualquer mudanca funcional.

## Entregas

| Entrega | Arquivo | Resultado |
|---|---|---|
| Registro de arquitetura | `docs/pcm_auditoria/14_ADRS_ARQUITETURA_ALVO_FASE_2.md` | nove ADRs com decisao, evidencia, compatibilidade e rollback |
| De-para operacional | `docs/pcm_auditoria/15_DE_PARA_OPERACIONAL_FASE_2.md` | 25 decisoes, matriz proposta de permissoes, formulas e assinaturas |
| Resultado e gate | este documento | limites da fase e proxima acao segura |

## Resultado dos ADRs

| Situacao | Quantidade | ADRs |
|---|---:|---|
| Aceita tecnicamente | 4 | equipamento, OS unica, horimetro append-only e anexos |
| Proposta para homologacao | 2 | tempos operacionais e state machine/backlog |
| Pendente de regra operacional | 3 | ciclo preventivo, KPI e permissoes |

## Decisoes consolidadas

- O sistema atual sera evoluido, sem segundo produto.
- Desktop fica com gestao/PCM e Web Mobile com operacao.
- `Vehicle` sera a raiz tecnica de todos os ativos.
- `EquipmentFamily` sera a classificacao oficial.
- `MaintenanceWorkOrder` sera a unica OS.
- `order_number` sera o unico identificador oficial de OS.
- MTR e TRM nao serao criados.
- Backlog sera derivado das OS nao terminais.
- Leituras de horimetro confirmadas nao serao apagadas ou sobrescritas.
- Evidencias continuarao no storage e ganharao metadados/vinculos normalizados.
- APIs e campos legados serao preservados durante migrations aditivas.

## Evidencias verificadas

| Fluxo | Evidencia real |
|---|---|
| Cadastro unificado | `Vehicle.to_dict()`, `apply_equipment_profile()` e rotas `/veiculos` |
| LBS-Spreader | `EquipmentLink` e `sync_active_equipment_link()` |
| Disponibilidade | `EquipmentStatusEvent` e `build_availability_overview()` |
| Horimetro | `HourmeterReading`, `record_hourmeter()` e rotas `/equipamentos/<id>/horimetros` |
| Emergencia para OS | `convert_emergency_to_work_order()` |
| Execucao e liberacao | `start_work_order()`, `complete_repair()`, `record_operational_test()` e `release_work_order()` |
| Preventiva | `PreventivePlan`, `generate_due_preventives()` e `advance_preventive_plan_after_completion()` |
| Backlog | `build_backlog()` |
| Indicadores | `_reliability_metrics()` e `build_maintenance_intelligence_overview()` |
| Seguranca | `auth_required()` e guards de perfil nas rotas |
| Auditoria | hooks de `audit_service.py` e `record_event()` |
| Arquivos | `/upload`, `storage_service.py` e campos de evidencia dos models |

## Validacao executada

- 18 testes passaram nas sete suites de equipamento, disponibilidade, emergencia/OS, PCM, inteligencia, seguranca e upload, executadas em processos isolados.
- A execucao conjunta registrou 17 testes aprovados e uma divergencia temporaria de MTTR, 5 h contra 7,5 h.
- O mesmo teste de inteligencia passou isoladamente com MTTR de 7,5 h.
- Causa identificada: os modulos de teste alteram `DATABASE_URL` durante a importacao e podem compartilhar a configuracao do ultimo modulo coletado.
- Nenhum service ou formula foi alterado para esconder essa interferencia.
- A Fase 3 devera isolar a configuracao dos bancos por fixture/app factory antes de usar uma execucao agregada como gate de KPI.

## Riscos evitados

- Nao foi oficializada formula sem dono operacional.
- Nao foi presumida a regra depois de 6.000 h.
- Nao foi trocado o status de OS sem camada de compatibilidade.
- Nao foi criado MTR/TRM ou outro numero concorrente.
- Nao foi alterada permissao apenas na interface.
- Nao foi desenhada correcao que apaga horimetro original.
- Nao foi criada tabela de backlog duplicando OS.
- Nao foi aplicado schema sobre PostgreSQL desconhecido.

## Itens nao alterados

- Models e tabelas.
- Migrations e runtime schema.
- Services e regras de negocio.
- Rotas e contratos de API.
- Desktop e Web Mobile.
- Autenticacao e permissoes ativas.
- Dados locais ou de producao.

## Pendencias bloqueadoras

1. Comparar o schema real do PostgreSQL de producao com models e migrations.
2. Assinar o de-para operacional.
3. Definir falha qualificavel e marcos de MTTR/MTBF.
4. Aprovar disponibilidade e tratamento de restricao/manutencao.
5. Aprovar ciclo 500-6.000 h e a regra posterior.
6. Aprovar state machine, reabertura e cancelamento de OS.
7. Aprovar matriz de permissoes e segregacao de funcoes.
8. Confirmar inventario oficial de 25 ou 27 Spreaders.

## Gate da fase

| Gate | Status |
|---|---|
| ADRs tecnicos | APROVADO TECNICAMENTE |
| Rastreabilidade com o sistema atual | APROVADA TECNICAMENTE |
| Compatibilidade e rollback | DEFINIDOS |
| De-para operacional assinado | PENDENTE |
| PostgreSQL de producao comparado | BLOQUEADO |
| Liberacao de migrations da Fase 3 | **NO-GO** |

## Proximo passo permitido

Realizar uma reuniao objetiva de homologacao usando o documento 15, registrar responsaveis e aceites e obter acesso read-only ao PostgreSQL. Depois disso, decompor a Fase 3 em entregas pequenas: equipamento/localizacao, OS, horimetro e preventiva/backlog, cada uma com migration, teste e rollback proprios.

# Resultado da Fase 3A.1 - Movimento de localizacao

Data: 17/07/2026

Status: **IMPLEMENTADO E VALIDADO LOCALMENTE; PRODUCAO EM NO-GO**.

## Objetivo executado

Adicionar historico auditavel de localizacao sem remover ou substituir o cadastro atual de equipamentos.

## Estrutura implementada

| Camada | Entrega |
|---|---|
| Model | `EquipmentLocationMovement` em `backend/app/models/equipment_structure.py` |
| Tabela | `equipment_location_movements` |
| Migration | `20260717_0010`, dependente de `20260713_0009` |
| Service | `move_equipment_location()` e `build_equipment_location_history()` |
| API | `GET/POST /equipamentos/{id}/movimentos-localizacao` |
| Auditoria | evento `EQUIPMENT_LOCATION_MOVEMENT / LOCATION_MOVED` |
| Testes | fluxo de API/permissao/auditoria e upgrade/downgrade isolado |

## Dados preservados por movimento

- Equipamento.
- Local de origem, quando existente.
- Local de destino.
- Motivo obrigatorio.
- Observacao opcional.
- Origem do registro: manual, importado, automacao ou migracao.
- Data efetiva do movimento.
- Usuario responsavel.
- Data de criacao.

## Regras aplicadas

1. Somente equipamento ativo com perfil tecnico pode ser movimentado.
2. O destino deve existir e estar ativo.
3. Origem e destino nao podem ser iguais.
4. Motivo e obrigatorio e limitado a 255 caracteres.
5. Movimento futuro e rejeitado.
6. Novo movimento deve ser posterior ao ultimo movimento do ativo.
7. O perfil e bloqueado transacionalmente durante a gravacao para serializar movimentos concorrentes no PostgreSQL.
8. A escrita exige `admin` ou `gestor`; a consulta exige usuario autenticado.
9. `EquipmentProfile.operational_location_id` e `Vehicle.local` continuam atualizados para clientes legados.
10. O historico nao e apagado quando o local atual muda.

## Compatibilidade

- Nenhum campo de `vehicles` ou `equipment_profiles` foi removido.
- As rotas existentes de cadastro, locais e vinculos nao mudaram de contrato.
- Desktop e Web Mobile atuais continuam lendo o local atual como antes.
- A nova tela de historico fica para a Fase 4.
- Locais atuais anteriores a `0010` nao receberam data historica inventada; o primeiro movimento parte do local vigente.

## Migration e rollback

- `upgrade()` e idempotente: se a tabela existir, nao recria.
- `downgrade()` remove somente `equipment_location_movements`.
- Tabelas `users`, `vehicles` e `operational_locations` foram preservadas no ensaio.
- A migration nao foi aplicada ao PostgreSQL de producao.
- Se ja houver movimentos validos em producao, o rollback recomendado e voltar o codigo e manter a tabela, evitando perda de historico.

## Validacao executada

| Validacao | Resultado |
|---|---|
| API, permissao, local atual e auditoria | 4 testes aprovados |
| Migrations isoladas, incluindo upgrade duplo/downgrade de `0010` | 9 testes aprovados |
| Regressao de cadastro de veiculos | 2 testes aprovados; 2 avisos legados de `Query.get()` |
| Models versus banco temporario | 47 tabelas sem divergencia; head `20260717_0010` |
| Compilacao Python | aprovada |
| `git diff --check` | aprovado |

## Pendencias do Passo 03

| Submodulo | Situacao |
|---|---|
| 3A.1 Movimento de localizacao | CONCLUIDO LOCALMENTE |
| 3A.2 Parametros operacionais | pendente de definicao |
| 3A.3 Permissoes por capacidade | pendente de homologacao da matriz |
| 3A.4 Evidencias normalizadas | aprovado tecnicamente, ainda nao implementado |
| 3B OS e corretivas | bloqueado pelo de-para operacional |
| 3C Horimetro | bloqueado pela alcada de correcao/aprovacao |
| 3D Preventiva e backlog | bloqueado pelo ciclo depois de 6.000 h e state machine |

## Gate

O incremento 3A.1 pode seguir para revisao tecnica, mas o Passo 03 completo e o deploy de `0010` permanecem **NO-GO** ate comparar o PostgreSQL de producao, gerar backup restauravel e aprovar as decisoes operacionais correspondentes.

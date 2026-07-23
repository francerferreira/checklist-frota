# Fase 7 - Planejamento, programação e backlog

## Entrega aplicada

- Reprogramação de item agora exige um motivo informado pelo gestor.
- O motivo é salvo no item reprogramado.
- Cada reprogramação cria um evento de auditoria explícito com data anterior, nova data e justificativa.
- A interface de Manutenção passou a solicitar o motivo antes da ação em lote.

## Regras preservadas

- Planejamento, agenda, capacidade diária e backlog existentes continuam sendo reutilizados.
- Itens concluídos ou cancelados continuam fora da reprogramação em lote.
- Apenas perfis de gestão podem reprogramar.

## Banco SQLite local

Nenhuma tabela adicional foi necessária. O histórico é registrado na tabela de auditoria já existente.

## Validação

O teste cobre bloqueio sem motivo, reprogramação válida e registro de auditoria.

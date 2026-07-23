# Fase 8 - Materiais, estoque e reposição

## Entrega aplicada

- Adicionados ponto de reposição e classe ABC ao cadastro de material.
- A regra `repor` sinaliza quando o saldo fica igual ou abaixo do ponto de reposição.
- A tela de material permite configurar estoque mínimo, ponto de reposição e classe ABC.
- O SQLite local atualiza materiais existentes com ponto de reposição inicial igual ao estoque mínimo, quando aplicável.

## Regras preservadas

- Depósitos, reservas, consumo por OS, entradas, saídas e bloqueio de saldo negativo continuam no fluxo existente.
- Classe ABC aceita somente A, B ou C.
- Ponto de reposição não pode ser negativo.

## Banco SQLite local

Foram adicionadas as colunas `ponto_reposicao` e `classe_abc` à tabela `materials`.

## Validação

O teste cobre criação, atualização, sinalização de reposição e rejeição de classe ABC inválida.

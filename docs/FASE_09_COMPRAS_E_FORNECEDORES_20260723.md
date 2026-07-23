# Fase 9 - Compras e fornecedores

## Entrega aplicada

- Criado cadastro de fornecedor com contato e canal de comunicação.
- Criada solicitação de compra vinculada ao material, fornecedor opcional e prioridade.
- Aprovação restrita ao administrador.
- Recebimento parcial permitido após aprovação.
- Recebimento idempotente: a mesma chave não soma o estoque duas vezes.
- Criada tela desktop **Compras e fornecedores**.

## Banco SQLite local

Foram adicionadas as tabelas `suppliers`, `purchase_requests` e `purchase_receipts`.

O banco local passou de 51 para 54 tabelas.

## Regras preservadas

- Recebimento gera entrada de estoque com referência da solicitação.
- Solicitação concluída não pode receber acima da quantidade pedida.
- Atraso é calculado comparando a data prevista com a data atual.

## Validação

O teste cobre fornecedor, aprovação por perfil, recebimento parcial, recebimento final e repetição idempotente.

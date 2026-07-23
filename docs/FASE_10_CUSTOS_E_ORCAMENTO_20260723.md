# Fase 10 - Custos, orçamento e documentos

## Entrega aplicada

- Adicionado orçamento por ordem de serviço.
- A governança da OS agora informa orçamento, realizado, variação e percentual consumido.
- Alteração de orçamento gera auditoria explícita.
- Os cálculos usam `Decimal` antes da serialização da resposta.

## Regras já existentes preservadas

- Custos por categoria e fornecedor continuam vinculados à OS.
- Biblioteca técnica mantém código, revisão, validade e situação efetiva do documento.
- Documentos vencidos continuam identificados pelo módulo de biblioteca.

## Banco SQLite local

Foram adicionadas as colunas `budget_amount` e `budget_notes` em `maintenance_work_orders`.

## Validação

O teste cobre custo realizado, orçamento de 1.000,00 e variação positiva de 250,50, além da auditoria.

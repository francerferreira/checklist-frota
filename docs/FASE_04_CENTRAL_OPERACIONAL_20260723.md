# Fase 4 — Equipamentos e Central Operacional

**Status:** primeira entrega incremental concluída.  
**Data:** 23/07/2026.  
**Banco/migrations:** nenhuma alteração.

## Objetivo desta entrega

Disponibilizar uma visão operacional única para RTGs, LBS e demais ativos, reaproveitando o cadastro, status operacional, horímetro, OS e emergências já existentes.

## Escopo aplicado

- Nova página desktop **Central Operacional**.
- Cartões dinâmicos para total de RTGs, LBS, ativos disponíveis e ativos que exigem atenção.
- Grade com equipamento, família, status, local, criticidade, horímetro, referência de OS/emergência e último apontamento.
- Filtros locais por família e pesquisa textual.
- Acesso para `admin`, `gestor` e `mecanico`.
- Consulta aos contratos existentes de disponibilidade e ativos críticos.

## Arquivos afetados

| Arquivo | Alteração |
|---|---|
| `desktop/ui/operational_center_page.py` | Nova interface de consulta operacional |
| `desktop/ui/main_window.py` | Navegação, menu e atualização da nova página |
| `desktop/access.py` | Acesso por perfil |
| `desktop/api_client.py` | Cliente para ativos críticos existentes |
| `tests/test_desktop_navigation.py` | Cobertura da navegação e acesso |

## Dados utilizados

| Informação exibida | Fonte já existente |
|---|---|
| Ativo, família, local e criticidade | `GET /disponibilidade/visao` |
| Status e horímetro | estado operacional do equipamento |
| OS, preventiva e emergência aberta | `GET /dashboard-manutencao/ativos-criticos` |

## Regras preservadas

- A Central não cadastra, altera, exclui ou duplica equipamentos.
- `Vehicle` continua sendo o ativo técnico central.
- `SEM_APONTAMENTO` não é apresentado como disponível.
- OS e emergências continuam sendo geridas pelos módulos atuais.
- Nenhuma migration, tabela ou dado operacional foi criado.

## Validação

Foram executados os testes de navegação desktop, disponibilidade e dashboard de manutenção.

Resultado: **17 testes aprovados**.

## Próximas entregas da Fase 4

1. Ficha individual com abas de resumo, OS, preventivas, horímetro, disponibilidade, materiais, custos, documentos e auditoria.
2. QR Code e acesso mobile ao ativo.
3. Previsão de retorno, responsável e tempo parado somente depois de a regra de OS ser homologada no PostgreSQL.

Essas próximas entregas permanecem dependentes da homologação pendente da Fase 2 no PostgreSQL.

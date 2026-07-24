# Etapa 11 - Indicadores e Power BI com SQLite

## Contrato oficial

O contrato `bi.sqlite.readonly.v1` está disponível em `GET /relatorios/bi/contrato` para usuários `admin` e `gestor`.

Ele é um catálogo de consumo: informa quais conjuntos são oficiais, campos, filtros, fórmulas e limites. Não cria view SQL, não altera tabelas e não permite escrita no SQLite.

## Conjuntos disponíveis

| Conjunto | Uso | Entrega |
|---|---|---|
| `pcm_base_mestre` | OS, intervenções, equipamento, família, local e situação operacional | JSON, CSV ou XLSX por `/relatorios/base-mestre/exportar` |
| `manutencao_executiva` | MTBF, MTTR, disponibilidade, backlog, preventivas e suprimentos | JSON por `/relatorios/manutencao-executivo` |
| `pcm_programacao` | Carga, capacidade, janelas e cumprimento preventivo | JSON por `/pcm/programacao` |

## Uso recomendado no Power BI

1. Um administrador ou gestor gera a exportação CSV da Base Mestre pelo endpoint autenticado.
2. O arquivo CSV é importado no Power BI como uma cópia analítica.
3. O relatório usa `intervention_id` como chave e respeita os nomes de colunas publicados pelo contrato.
4. A atualização é manual até existir uma conta técnica autenticada e aprovada para automação.

O arquivo `backend/checklist_frota.db` não deve ser compartilhado, aberto por ODBC nem receber comandos do Power BI enquanto o backend local estiver trabalhando. Isso é equivalente a não mexer no livro-caixa enquanto outra pessoa está fazendo os lançamentos: a exportação é a cópia segura para análise.

## Indicadores homologados tecnicamente

- backlog aberto: total retornado pelo backlog operacional;
- cumprimento preventivo: concluídas em dias já ocorridos no horizonte consultado;
- MTBF: somente falhas com execuções comparáveis completas;
- MTTR: somente reparos com início, conclusão e liberação registrados.

Valores sem base registrada permanecem vazios. O sistema não estima custo, parada, metas ou indicadores de folha.

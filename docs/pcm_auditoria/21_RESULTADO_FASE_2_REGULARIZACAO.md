# Resultado da Fase 2 - Regularizacao Controlada

## Status

**ENSAIO CONCLUIDO / PRODUCAO AINDA BLOQUEADA**

A cadeia completa de migrations foi executada com sucesso em uma copia isolada do SQLite local. Nenhuma migration, importacao ou alteracao foi executada no Supabase.

## Execucao realizada

- Copia de `backend/checklist_frota.db` para `.tmp_tests/fase2_migration_rehearsal.db`.
- Execucao de `flask db upgrade --directory migrations` somente na copia.
- Aplicacao das 11 revisoes da cadeia, de `20260712_0000` ate `20260717_0010`.
- Comparacao do schema da copia apos a regularizacao.
- Comparacao de contagens entre banco original e copia.
- Nenhuma escrita no banco original, Supabase ou Storage.

## Resultado do ensaio

| Verificacao | Resultado |
|---|---:|
| Tabelas antes | 47 |
| Tabelas depois | 47 |
| Diferencas de contagem de registros | 0 |
| Revisao Alembic depois | `20260717_0010` |
| Head esperado | `20260717_0010` |
| Migrations aplicadas | 11 |
| Dados removidos | 0 |

O ensaio comprova que a cadeia consegue registrar o head e preservar os registros existentes na copia legada.

## Divergencias que permanecem

Depois das migrations, o comparador ainda encontrou 9 divergencias estruturais:

- `activities.auto_link_nc` continua nullable no banco e nao nullable no model;
- `activities` continua sem a FK de `assigned_mechanic_user_id`;
- `activities` continua sem todos os indices esperados;
- `activity_items.quantidade_peca` continua nullable no banco e nao nullable no model;
- `activity_items` continua sem a FK de `material_id`;
- `activity_items` continua sem o check positivo de `quantidade_peca`;
- `activity_items` continua sem o indice de `material_id`;
- `checklist_items` continua sem a FK de `resolved_by_user_id`;
- `checklist_items` continua sem todos os indices esperados.

Conclusao: as migrations existentes sao adequadas para criar a estrutura evolutiva ausente e registrar a versao, mas nao substituem uma migration corretiva para o legado. Essa migration corretiva depende da comparacao real do PostgreSQL e de backfill seguro.

## Carga de dados

A carga de dados de producao nao foi executada porque ainda faltam:

- contagens reais do Supabase por tabela;
- mapa de chaves entre Supabase e fontes locais;
- backup restauravel do banco e do bucket `evidencias`;
- identificacao de documentos e fotos sem objeto correspondente;
- aprovacao para escrita em producao.

Nenhum dado local foi enviado ao Supabase nesta fase.

## Liberacao para producao

Antes de executar `flask db upgrade` no Render ou no Supabase:

1. Rodar `tools/compare_database_schema.py` no Shell do Render, usando a `DATABASE_URL` real do servico.
2. Salvar o relatorio de schema e as revisoes atuais.
3. Gerar e validar backup completo.
4. Comparar contagens e duplicidades.
5. Criar migration corretiva somente para as 9 divergencias confirmadas em producao.
6. Executar primeiro em uma copia restaurada ou ambiente de homologacao.
7. Aplicar em producao com janela controlada e plano de rollback.

## Conclusao

A Fase 2 foi validada tecnicamente em uma copia sem perda de dados. A regularizacao real do Supabase e a importacao de dados permanecem pendentes de acesso read-only, backup e homologacao de producao.

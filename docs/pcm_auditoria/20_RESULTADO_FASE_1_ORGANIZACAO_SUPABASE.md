# Resultado da Fase 1 - Organizacao do Supabase

## Status

**CONCLUIDA PARCIALMENTE / NO-GO PARA IMPORTACAO EM PRODUCAO**

A auditoria read-only local foi executada. A comparacao fisica do PostgreSQL do Supabase e a reconciliacao de dados de producao continuam bloqueadas porque o ambiente local nao possui uma `DATABASE_URL` de producao ou acesso read-only ao banco.

## Escopo executado

- Validacao da API publicada.
- Identificacao da origem do banco configurado localmente.
- Comparacao do SQLite local com os 47 models.
- Comparacao do SQLite local com o head das migrations.
- Levantamento de contagens dos dados locais.
- Verificacao de relacionamentos orfaos em entidades operacionais principais.
- Nenhuma escrita no Supabase, SQLite ou Storage.

## Evidencias

| Verificacao | Resultado | Evidencia |
|---|---|---|
| API publicada | OK | `GET https://checklist-frota-qngw.onrender.com/health` retornou HTTP 200 e `status=ok` |
| Banco configurado neste computador | PostgreSQL local | `.env` aponta para `127.0.0.1:5432/checklist_frota` |
| PostgreSQL local | Indisponivel | conexao recusada em `127.0.0.1:5432` |
| SQLite local | Disponivel | `backend/checklist_frota.db`, aproximadamente 1,82 MB |
| Tabelas no SQLite | 47 | comparador `tools/compare_database_schema.py` |
| Tabelas nos models | 47 | metadata SQLAlchemy |
| Revisao Alembic no SQLite | Nao registrada | tabela `alembic_version` ausente |
| Head esperado | `20260717_0010` | cadeia em `migrations/versions/` |
| Divergencias estruturais locais | 10 | comparador ampliado |

## Contagens locais

Estas contagens sao somente da copia local e nao representam o Supabase:

| Tabela | Registros |
|---|---:|
| `vehicles` | 285 |
| `equipment_profiles` | 285 |
| `equipment_operational_states` | 285 |
| `checklist_catalog_items` | 256 |
| `wash_records` | 693 |
| `wash_queue_items` | 114 |
| `equipment_families` | 13 |
| `users` | 5 |
| `audit_logs` | 10 |

## Integridade local verificada

As consultas read-only retornaram zero registros orfaos para:

- veiculos ativos sem perfil de equipamento;
- perfis sem veiculo;
- itens de checklist sem checklist;
- documentos tecnicos sem equipamento ou familia;
- leituras de horimetro sem veiculo;
- itens de manutencao sem veiculo;
- ordens de servico sem veiculo.

## Divergencias estruturais encontradas no SQLite

O comparador encontrou 10 divergencias, concentradas em schema legado e no registro de migrations:

- `activities.auto_link_nc` esta nullable no banco, mas nao nullable no model;
- `activities` nao possui a FK de `assigned_mechanic_user_id`;
- `activities` nao possui todos os indices esperados pelo model;
- `activity_items.quantidade_peca` esta nullable no banco, mas nao nullable no model;
- `activity_items` nao possui a FK de `material_id`;
- `activity_items` nao possui o check positivo de `quantidade_peca`;
- `activity_items` nao possui todos os indices esperados;
- `checklist_items` nao possui a FK de `resolved_by_user_id`;
- `checklist_items` nao possui todos os indices esperados;
- a revisao `20260717_0010` nao esta registrada em `alembic_version`.

Essas divergencias nao devem ser corrigidas diretamente em producao antes da comparacao equivalente no PostgreSQL do Supabase. O `create_all()` e o `ensure_runtime_schema()` podem criar parte da estrutura sem registrar a revisao Alembic completa.

## Pendencias para fechar a Fase 1

1. Obter uma `DATABASE_URL` read-only do Supabase ou executar o comparador no Shell do Render.
2. Executar `tools/compare_database_schema.py` contra o PostgreSQL de producao.
3. Registrar tabelas, colunas, indices, FKs, checks e revisao `alembic_version` reais.
4. Gerar backup atual do banco e do bucket `evidencias`.
5. Comparar contagens do Supabase com as fontes locais e os backups.
6. Mapear documentos tecnicos e fotos para objetos reais do Storage.
7. Aprovar a matriz de divergencias antes de qualquer migration ou importacao.

## Gate da Fase 2

A Fase 2 fica bloqueada até que exista:

- backup restauravel;
- comparacao real do PostgreSQL;
- contagem de dados de producao;
- mapa de IDs e chaves de reconciliacao;
- classificacao de cada divergencia como manter, corrigir, importar ou arquivar;
- aceite para aplicar migrations e cargas controladas.

## Conclusao

A aplicacao esta conectada ao Supabase, mas ainda nao existe evidencia suficiente para afirmar que todos os dados e estruturas foram carregados. A Fase 1 confirmou a necessidade de uma auditoria fisica de producao e deixou a importacao segura preparada, sem alterar dados.

# Resultado da Fase 1 - Protecao e homologacao

## Status

**EXECUTADA TECNICAMENTE COM BLOQUEIOS EXTERNOS.**

As protecoes locais, o comparador, a validacao de backup, o ensaio de restauracao e a releitura das planilhas foram concluidos. Migrations e importacao real permanecem em **NO-GO** ate existir acesso read-only ao PostgreSQL de producao e aprovacao das pendencias operacionais.

## Baseline protegido

- Branch inicial: `main`.
- Commit inicial da fase: `8ff5ca8` (`docs: adiciona auditoria PCM portuaria`).
- Tag de retorno criada: `fase-1-baseline-20260717`.
- O repositorio estava limpo antes das alteracoes.
- Nenhum model, migration, endpoint, service de negocio, componente, template ou dado operacional foi alterado.

## Banco configurado e producao

| Verificacao | Resultado | Evidencia |
|---|---|---|
| `DATABASE_URL` local | PostgreSQL em `127.0.0.1:5432/checklist_frota` | `.env`, sem exposicao de senha |
| Processo/servico PostgreSQL local | nao encontrado | `Get-Service`/`Get-Process` |
| Conexao direta ao PostgreSQL configurado | recusada | `tools/compare_database_schema.py` |
| API atual `checklist-frota-qngw` | timeout apos 90 segundos | chamada `GET /health` |
| Endpoint legado `checklist-api` | HTTP 404 | chamada `GET /health` |
| `pg_dump`/`pg_restore` | nao instalados no ambiente | `Get-Command` |
| Schema PostgreSQL de producao | nao comparado | bloqueio externo |

Conclusao: a configuracao local nao fornece acesso ao PostgreSQL de producao e a API publicada nao respondeu durante a fase. Nao e seguro executar migration com esse cenario.

## Comparacao do SQLite local

O banco `backend/checklist_frota.db` foi aberto em modo `PRAGMA query_only = ON`.

- 46 tabelas no banco e 46 nos models.
- Nenhuma tabela ou coluna ausente pelo comparador basico.
- O comparador ampliado encontrou 10 divergencias estruturais.
- Divergencias concentradas em `activities`, `activity_items` e `checklist_items`.
- Foram identificadas diferencas de nulabilidade, FKs, indices e um check constraint.
- A tabela `alembic_version` nao existe no SQLite local; o head do codigo e `20260713_0009`.

Isso comprova o risco ja apontado na auditoria: `create_all()` e `ensure_runtime_schema()` conseguem deixar as colunas presentes sem registrar a mesma estrutura completa das migrations.

## Protecoes implementadas

### Comparador read-only

`tools/compare_database_schema.py` agora verifica:

- tabelas e colunas;
- tipos e nulabilidade;
- chaves primarias e estrangeiras;
- unique constraints;
- indices;
- check constraints;
- revisao `alembic_version` versus head das migrations;
- saida JSON opcional;
- erro de conexao resumido, sem stack trace e sem senha.

No PostgreSQL, a ferramenta executa `SET TRANSACTION READ ONLY`. No SQLite, executa `PRAGMA query_only = ON`.

### Backup seguro

`backup_checklist_cloud.ps1` e `.bat` foram ajustados para:

- usar a URL atual da API;
- remover a senha `123456` do codigo;
- solicitar senha como `SecureString`;
- verificar `/health` e o banco antes do login;
- validar CRC, manifesto, tabelas, contagens e anexos apos o download;
- impedir que um ZIP invalido seja usado para limpeza.

### Restauracao isolada

Foi criado `tools/restore_backup_archive.py` para validar o ZIP e restaurar em SQLite isolado, sem sobrescrever banco operacional por padrao.

| Ensaio | Tabelas | Linhas | Anexos | Resultado |
|---|---:|---:|---:|---|
| Backup historico de 20/04/2026 | 15 | 1.483 | 9 | validado e restaurado |
| Backup da copia local atual | 46 | 1.947 | 9 | validado e restaurado |

O segundo ensaio foi executado sobre copia em `.tmp_tests/`; o arquivo `backend/checklist_frota.db` nao foi usado como destino de escrita.

## Inventario revalidado

Fontes encontradas em `C:/Users/francer.ferreira/Downloads/`:

- `SPREADERS.xlsx`;
- `CONTROLE_RTG_ALFANDEGADO_MASTER.xlsx`;
- `ACOMPANHAMENTO_REUNIAO_RTG_ALFANDEGADO_DASHBOARD_TOP.xlsx`;
- `ACOMPANHAMENTO_REUNIAO_RTG_ATR_DASHBOARD_TOP.xlsx`.

| Familia | Resultado tecnico | Situacao |
|---|---|---|
| RTG | 22 codigos unicos: 12 Alfandegado e 10 ATR; 17 disponiveis e 5 indisponiveis no recorte | falta mestre tecnico com serie/fabricante/modelo/ano |
| LBS | 16 equipamentos, de LBS 01 a LBS 16, com serie/ano nos nomes das abas | local oficial precisa ser consolidado sem celulas mescladas |
| Spreader | 27 series unicas; 19 codificados e 8 sem codigo aguardando ativacao | conflito com imagem historica de total 25 |

Nenhum ativo foi importado.

## Decisoes confirmadas

- O unico identificador oficial sera o numero da OS; MTR/TRM nao sera usado.
- O sistema atual sera reaproveitado.
- Desktop permanece para gestao/PCM e Web Mobile para operacao.
- Importacao direta continua bloqueada; sera exigido staging, preview e rollback.
- Nenhuma migration destrutiva pode ocorrer sem backup e restauracao comprovados.

## Decisoes operacionais pendentes

1. Confirmar total oficial de Spreaders: 25 ou 27.
2. Fornecer codigo oficial para os 8 Spreaders sem identificador.
3. Homologar dados tecnicos dos 22 RTGs e local mestre das 16 LBS.
4. Confirmar se o ciclo 500-6000 h e igual para RTG e LBS e como reinicia apos 6000 h.
5. Aprovar eventos que iniciam/encerram MTTR, MTBF e indisponibilidade.
6. Aprovar status oficiais de OS/backlog e suas transicoes.
7. Aprovar o de-para dos perfis atuais para Supervisor, PCM, Tecnico, Administrativo e Consulta.

## Gate da fase

| Gate | Status |
|---|---|
| Git e baseline | aprovado |
| Comparador read-only | aprovado |
| Backup e restauracao isolada | aprovado |
| Inventario tecnico | parcialmente homologado |
| PostgreSQL de producao | bloqueado por falta de acesso/resposta |
| Regras operacionais | aguardando aprovacao |
| Liberacao para migrations/importacao | **NO-GO** |

## Proximo passo permitido

Obter uma `DATABASE_URL` read-only da producao ou restabelecer `/health`, executar o comparador ampliado e gerar backup atual da nuvem. Depois, resolver as sete decisoes operacionais acima. Somente entao a Fase 2 pode autorizar desenho definitivo de models e migrations.

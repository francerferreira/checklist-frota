# Fase 01 - Preparacao da limpeza segura

Data da execucao: 19/07/2026

## Resultado executivo

A Fase 01 foi concluida no PostgreSQL local sem excluir ou alterar registros do banco principal.

O alvo foi identificado como `127.0.0.1:5432/checklist_frota`. O banco publicado respondeu `200` no `/health`, com banco e auditoria saudaveis, mas as credenciais diretas do Supabase nao estao configuradas neste computador. Por isso, qualquer limpeza de producao permanece bloqueada ate existir backup proprio da producao.

## Backups gerados e validados

| Backup | Tamanho | SHA-256 | Validacao |
| --- | ---: | --- | --- |
| `backend/backups/postgres_pre_cleanup_phase1_20260719_154339.dump` | 327425 bytes | `22BEE4350AE62D56EFAADDFC9AAA944045764FAB29B6FA8EB80425BF9529B747` | 718 itens reconhecidos pelo `pg_restore` |
| `backend/backups/sqlite_pre_cleanup_phase1_20260719_154339.db` | 1822720 bytes | `85E81AC1C15C15961B0A2C7B7E1F0506F3B15F889B2BBF011887448772854BCD` | `PRAGMA integrity_check = ok` |
| `backend/backups/uploads_pre_cleanup_phase1_20260719_154339.zip` | 4623403 bytes | `83FB3BDCC9CE00C1FC708B1ABCFAB7E38AD39DF773224CF5259DDC6E61686BA0` | 9 entradas legiveis |

## Inventario que deve ser preservado

| Familia | Quantidade | Ativos | Anomalias |
| --- | ---: | ---: | ---: |
| LBS | 16 | 16 | 0 |
| RTG | 21 | 21 | 0 |
| Spreader | 25 | 25 | 0 |
| Total | 62 | 62 | 0 |

Nao foram encontrados nomes duplicados, equipamentos portuarios fora das tres familias ou ativos sem estado operacional. Todos os 62 possuem perfil tecnico e estado operacional.

O usuario `francer` existe, esta ativo e possui perfil `admin`. Sua senha atual nao corresponde a `123456`.

## Registros atuais relevantes

| Grupo | Quantidade atual | Quantidade simulada |
| --- | ---: | ---: |
| Equipamentos | 347 | 62 |
| Perfis tecnicos | 347 | 62 |
| Estados operacionais | 347 | 62 |
| Usuarios | 5 | 1 |
| Checklists | 5 | 0 |
| Itens executados de checklist | 280 | 0 |
| Registros de lavagem | 695 | 0 |
| Fila de lavagem | 114 | 0 |
| Logs de auditoria antigos | 443 | 0 |
| Materiais | 1 | 0 |
| Movimentacoes de material | 2 | 0 |

As 13 definicoes de familia e os 289 itens do catalogo de checklist foram preservados na simulacao porque sao configuracoes estruturais usadas para abrir os modulos, e nao historicos operacionais.

## Simulacao em clone

Foi criado o banco isolado `checklist_frota_cleanup_p1_20260719_154339` a partir do novo dump. A assinatura inicial do clone coincidiu com a origem: `347 veiculos | 5 usuarios | 5 checklists | 695 lavagens`.

A limpeza foi simulada dentro de uma transacao PostgreSQL. O estado-alvo obtido foi:

- 62 equipamentos;
- 62 perfis tecnicos;
- 62 estados operacionais;
- 1 usuario (`francer`);
- 0 checklists executados;
- 0 lavagens;
- 0 logs antigos;
- distribuicao final de 16 LBS, 21 RTG e 25 Spreaders.

A transacao terminou com `ROLLBACK`. Depois do rollback, o clone retornou para `347 | 5 | 5 | 695`. O banco principal permaneceu com a mesma assinatura durante toda a operacao.

## Bloqueios para a Fase 02

1. A inicializacao atual chama `ensure_auxiliary_vehicles()` e recria 11 veiculos auxiliares, mesmo sem planilha de lavagem.
2. Quando a fila fica vazia, `sync_wash_queue()` pode repopula-la automaticamente.
3. Nao existe backup direto do PostgreSQL/Supabase de producao neste computador.
4. O Storage Supabase nao esta configurado localmente; somente as evidencias locais foram arquivadas.
5. Alterar a senha de `francer` para `123456` reduziria a seguranca e precisa permanecer como decisao explicitamente aceita pelo responsavel.

## Criterios para liberar a Fase 02

- implementar e testar um modo `somente portuarios` que desative a recriacao automatica de auxiliares e lavagens;
- gerar backup restauravel do banco e do Storage de producao, caso a limpeza alcance o Supabase;
- executar novamente a simulacao depois do ajuste de inicializacao;
- confirmar a politica da senha do usuario `francer`;
- executar a limpeza primeiro no clone e validar login, API, Desktop e Web Mobile;
- somente depois liberar a transacao no banco escolhido.

## Situacao final

Fase 01 concluida no ambiente local. Fase 02 bloqueada por seguranca. Nenhuma exclusao foi executada no banco principal ou na producao.

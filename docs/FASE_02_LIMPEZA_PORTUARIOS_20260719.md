# Fase 02 - Limpeza controlada do ambiente local

Data da execucao: 19/07/2026

## Escopo executado

Esta fase foi aplicada somente no PostgreSQL local `127.0.0.1:5432/checklist_frota`. O Supabase, o Render e qualquer banco de producao permaneceram intactos.

## Protecao aplicada

Foi ativado `PORTUARY_ONLY_MODE=1` no ambiente local. O startup deixou de chamar a importacao automatica de veiculos auxiliares e a sincronizacao automatica da fila de lavagem.

Sem essa protecao, a inicializacao poderia recriar dados antigos depois da limpeza.

## Backup imediatamente anterior

| Backup | Tamanho | SHA-256 |
| --- | ---: | --- |
| `backend/backups/postgres_pre_cleanup_phase2_20260719_160000.dump` | 327425 bytes | `525811E7A10D9FA4AD2C26FA0F228A76277C04B5E38E7AE14B5AA5B54494C8BD` |
| `backend/backups/sqlite_pre_cleanup_phase2_20260719_160000.db` | 1822720 bytes | `85E81AC1C15C15961B0A2C7B7E1F0506F3B15F889B2BBF011887448772854BCD` |
| `backend/backups/uploads_pre_cleanup_phase2_20260719_160000.zip` | 4623403 bytes | `83FB3BDCC9CE00C1FC708B1ABCFAB7E38AD39DF773224CF5259DDC6E61686BA0` |

O dump PostgreSQL foi reconhecido pelo `pg_restore` com 718 itens.

## Resultado da limpeza

### Mantidos

- 62 equipamentos portuarios: 16 LBS, 21 RTG e 25 Spreaders.
- 62 perfis tecnicos.
- 62 estados operacionais.
- 1 usuario: `francer`, perfil administrador e ativo.
- 13 definicoes de familia tecnica.
- 289 itens de catalogo de checklist, preservados como configuracao estrutural.

### Removidos

- 285 equipamentos nao portuarios.
- 285 perfis tecnicos nao portuarios.
- 285 estados operacionais nao portuarios.
- 4 usuarios diferentes de `francer`.
- 5 checklists executados.
- 280 itens executados de checklist.
- 114 itens de fila de lavagem.
- 695 registros de lavagem.
- 443 logs antigos de auditoria.
- 1 material e 2 movimentacoes de material.
- Demais registros operacionais existentes nas tabelas de manutencao, inspecao, emergencia, PCM, estoque e sincronizacao.

Foi preservado 1 registro de auditoria da propria limpeza. Apos o teste de login, o banco ficou com 2 auditorias: a limpeza e o login de validacao.

## Validacao pos-limpeza

- `/health` local: `200`.
- Banco: `ok`.
- Auditoria: saudavel.
- Login `francer/123456`: `200`.
- Rota `/veiculos`: `200`.
- Equipamentos finais: `62`.
- Perfis portuarios finais: `62`.
- Usuarios finais: `1`.
- Fila de lavagem: `0`.
- Registros de lavagem: `0`.
- Checklists executados: `0`.
- Nenhum dado antigo reapareceu apos o startup.
- 15 testes direcionados passaram.

## Observacoes de seguranca

A senha `123456` foi aplicada somente ao usuario `francer` do PostgreSQL local porque isso foi solicitado. Ela e fraca e nao deve ser usada em producao. O Supabase/Render nao recebeu essa alteracao.

## Situacao final

Fase 02 concluida no ambiente local. O sistema local agora contem somente o cadastro portuario e o usuario `francer`, mantendo modulos, tabelas, familias e catalogo estrutural necessarios para o funcionamento.

O commit local deve ser revisado antes de qualquer publicacao. A producao continua sem alteracao.

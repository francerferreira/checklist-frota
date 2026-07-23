# Fase 2 — Fundação técnica e PostgreSQL

**Status:** implementação de proteção concluída; aceite PostgreSQL pendente de serviço local disponível.  
**Data:** 23/07/2026.  
**Sem alteração em produção, dados existentes ou credenciais.**

## Objetivo

Eliminar criação e alteração silenciosa de banco no startup da API. PostgreSQL passa a ser exigido nos ambientes oficiais; SQLite fica limitado ao teste automatizado e ao laboratório temporário autorizado.

## Arquivos afetados

| Arquivo | Alteração |
|---|---|
| `backend/app/config.py` | Perfis de ambiente, validação de banco e restrição de SQLite |
| `backend/app/__init__.py` | Startup sem DDL automático para PostgreSQL |
| `backend/app/services/runtime_schema_service.py` | DDL legado bloqueado fora de SQLite temporário |
| `.env.example` | Variáveis explícitas de ambiente e bootstrap |
| `tests/conftest.py` | Perfil isolado para testes descartáveis |
| `tests/test_phase2_database_governance.py` | Contratos de governança de banco |
| `README.md` | Operação oficial e limite do SQLite |

## Regras implementadas

1. `DATABASE_URL` é obrigatória.
2. SQLite não é aceito sem `CHECKLIST_ALLOW_SQLITE=1`.
3. O bootstrap legado exige simultaneamente SQLite e `CHECKLIST_LEGACY_LOCAL_BOOTSTRAP=1`.
4. `db.create_all()`, seed e `ensure_runtime_schema()` só ocorrem nesse perfil SQLite transitório.
5. PostgreSQL não recebe `CREATE TABLE`, `ALTER TABLE`, seed ou reconstrução de tabela ao iniciar a API.
6. Alterações estruturais futuras devem usar Alembic.

## Perfis

| Perfil | Banco permitido | Bootstrap legado | Uso |
|---|---|---|---|
| `test` | SQLite descartável | Sim | Testes automatizados |
| `development` | PostgreSQL | Não | Desenvolvimento oficial |
| `production` | PostgreSQL | Não | Operação |
| Laboratório Fase 1A | SQLite explícito | Sim | Protótipo temporário, sem dados oficiais |

## Validações aprovadas

- Ambiente oficial sem banco: bloqueado.
- SQLite em ambiente oficial: bloqueado.
- SQLite isolado no perfil de teste: permitido.
- Suite de configuração, migrations, segurança, disponibilidade, desktop e web mobile: **36 testes e 21 subtestes aprovados**.

## Pendência obrigatória antes do aceite da Fase 2

Durante esta fase, `DATABASE_URL` está configurada para PostgreSQL, mas a porta local `5432` não está respondendo e nenhum serviço PostgreSQL foi identificado no Windows.

Assim que o PostgreSQL estiver ativo, executar em uma base de desenvolvimento vazia e separada de produção:

```powershell
$env:PYTHONPATH="$PWD\backend"
python tools/compare_database_schema.py
py -m flask --app backend/wsgi:app db current --directory migrations
py -m flask --app backend/wsgi:app db upgrade --directory migrations
```

O comando de comparação é somente leitura. O `upgrade` só pode ocorrer após confirmação de que a `DATABASE_URL` aponta para o banco de desenvolvimento.

## Risco conhecido

A migration baseline atual marca instalações legadas, mas não constrói todas as 49 tabelas em um PostgreSQL vazio. Portanto, não foi removida nem reescrita nesta etapa sem um PostgreSQL de testes para validar upgrade, downgrade e compatibilidade com o banco existente.

## Critério de aceite restante

1. Serviço PostgreSQL local ativo.
2. Banco de desenvolvimento e banco de testes separados.
3. Backup confirmado antes de qualquer `db upgrade` fora do banco de testes.
4. Upgrade e reexecução de migration sem divergência.
5. Comparação de schema sem falhas críticas.
6. Baseline PostgreSQL reproduzível aprovada em ambiente de teste.

Até esses critérios, a Fase 2 permanece **tecnicamente implementada, mas não homologada**. Nenhuma fase funcional seguinte deve criar dados persistentes fora do PostgreSQL.

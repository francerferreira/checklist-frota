# Fase 12 - Prontidão para homologação local

## Entrega aplicada

Foi criado o comando `tools/validate_local_homologation.py` para validar o ambiente SQLite local sem publicar ou alterar PostgreSQL.

O comando executa, nesta ordem:

1. Consulta o `/health` da aplicação.
2. Confere integridade e chaves estrangeiras do banco SQLite local.
3. Cria um backup ZIP recuperável.
4. Valida o manifesto e os arquivos do backup.
5. Restaura o backup em uma pasta temporária isolada.
6. Confere a integridade da cópia restaurada e remove essa cópia temporária.

## Resultado executado em 23/07/2026

- API: `status=ok`;
- Auditoria: saudável, sem falhas registradas;
- SQLite de origem: 55 tabelas, integridade `ok`, nenhuma violação de chave estrangeira;
- Backup: 55 tabelas, 13 registros e 9 anexos;
- Restauração isolada: 55 tabelas, 13 registros e 9 anexos, integridade `ok`.

## Como executar novamente

Use o mesmo ambiente do atalho local SQLite e rode:

```powershell
$env:PYTHONPATH = "$PWD\backend"
$env:CHECKLIST_ENV = 'development'
$env:CHECKLIST_FORCE_LOCAL_DB = '1'
$env:CHECKLIST_ALLOW_SQLITE = '1'
$env:CHECKLIST_LEGACY_LOCAL_BOOTSTRAP = '1'
python tools\validate_local_homologation.py
```

## Limite de aprovação

Esta aprovação é somente para o SQLite local. A homologação de PostgreSQL, carga, concorrência, uso móvel offline e aceite operacional continuam etapas separadas e exigem ambiente e autorização próprios.

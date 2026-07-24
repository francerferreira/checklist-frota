# Melhoria P1 - Proteção de testes e backup local

## Proteção de testes

A suíte Pytest remove `CHECKLIST_FORCE_LOCAL_DB` antes de carregar a aplicação. Além disso, o perfil `CHECKLIST_ENV=test` rejeita essa variável. Assim, um teste não pode apontar para `backend/checklist_frota.db` por engano.

## Retenção de backup

Todo backup novo mantém apenas arquivos no padrão `backup-checklist-*.zip`. O padrão é conservar os **30** mais recentes.

Configure conforme a necessidade:

```env
BACKUP_RETENTION_COUNT=30
BACKUP_EXTERNAL_FOLDER=D:/BACKUP_CHECKLIST_FROTA
```

`BACKUP_EXTERNAL_FOLDER` é opcional. Quando informado, cada ZIP criado é copiado para essa pasta e recebe a mesma retenção. A pasta externa não pode ser a mesma pasta local de backups.

O processo nunca remove arquivos fora do padrão oficial de backup.

# Deploy gratuito: Render + Supabase

Este projeto esta preparado para o seguinte desenho:

```text
Frontend/PWA: Render Static Site
Backend Flask: Render Web Service
Banco: Supabase PostgreSQL
Fotos: Supabase Storage
Backups: ZIP baixado pelo admin ou pelo script local do PC
```

## 1. Supabase

1. Crie um projeto no Supabase.
2. Em `Project Settings > Database`, copie a connection string do Postgres.
3. Use no Render em formato SQLAlchemy:

```text
DATABASE_URL=postgresql+psycopg://USUARIO:SENHA@HOST:PORTA/postgres?sslmode=require
```

4. Em `Project Settings > API`, copie:

```text
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=service_role_key
```

5. Em `Storage`, crie o bucket:

```text
evidencias
```

O backend usa a service role key somente no servidor. Nao coloque essa chave no frontend.

## 2. Render Backend

Crie um `Web Service` ou use o `render.yaml`.

Configurar:

```text
Build Command:
pip install -r requirements.txt

Start Command:
gunicorn --chdir backend wsgi:app --bind 0.0.0.0:$PORT
```

Variaveis obrigatorias:

```text
SECRET_KEY=gere-uma-chave-forte
DATABASE_URL=postgresql+psycopg://...
TOKEN_MAX_AGE_SECONDS=28800
STORAGE_BACKEND=supabase
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sua-service-role-key
SUPABASE_STORAGE_BUCKET=evidencias
FREE_DB_LIMIT_MB=500
FREE_STORAGE_LIMIT_MB=1024
```

Depois do deploy, copie a URL publica do backend, por exemplo:

```text
https://checklist-api.onrender.com
```

## 3. Render Frontend/PWA

Crie um `Static Site` apontando para:

```text
Publish Directory:
web_app
```

Antes de publicar, edite:

```text
web_app/static/js/config.js
```

E coloque:

```js
window.CHECKLIST_CONFIG = {
    API_BASE_URL: "https://checklist-api.onrender.com",
};
```

## 4. Monitor de limite gratis

O sistema calcula:

```text
Banco: limite padrao 500 MB
Fotos: limite padrao 1024 MB
```

Alertas:

```text
70% = amarelo
85% = vermelho
95% = critico
```

Somente admin ve o painel `NUVEM E BACKUP` no menu do Web Mobile.

## 5. Backup

O botao `BACKUP` gera e baixa um ZIP contendo:

```text
banco/*.json
fotos/*
backup_manifesto.json
restauracao/instrucoes.txt
```

Tambem existe o script local:

```text
backup_checklist_cloud.bat
```

Edite o `API_URL` dentro dele depois que o backend estiver no Render.

## 6. Limpeza segura

O backend tem limpeza por API, mas ela exige:

```text
backup_filename
confirmation=LIMPAR_DADOS_ANTIGOS
```

Ela mantem os ultimos 14 dias por padrao e remove dados antigos ja cobertos pelo backup.

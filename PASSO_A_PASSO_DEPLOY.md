# Passo a passo: Deploy Checklist Frota

## 1. Criar conta no Supabase

### 1.1 Acesse o site
- Abra no navegador: **https://supabase.com**

### 1.2 Crie sua conta
1. Clique em **"Start your project"**
2. Escolha login com **GitHub** ou **email**
3. Se usar email:
   - Coloque seu email
   - Clique em **"Send magic link"**
   - Verifique seu email e clique no link

### 1.3 Crie um novo projeto
1. Na página inicial, clique em **"New project"**
2. Preencha os dados:
   - **Organization**: `checklist-frota` (ou seu nome)
   - **Name**: `checklist-frota`
   - **Database Password**: crie uma senha forte (ex: `Checklist2026!`)
   - **Region**: `N Virginia` (mais próximo do Brasil)
3. Clique em **"Create new project"**
4. Aguarde ~2 minutos até criar

### 1.4 Pegue as credenciais
Após criar, você verá o painel do projeto. Anote:

1. **Project URL** (no topo):
   - Exemplo: `https://abc123.supabase.co`
   - Você vai usar isso na variável `SUPABASE_URL`

2. **Service Role Key** (para storage):
   - Vá em **Settings** (ícone de engrenagem) → **API**
   - Em **Service Role Key**, clique em **"Copy"**
   - Essa chave vai na variável `SUPABASE_SERVICE_ROLE_KEY`

3. **Connection String** (para o banco):
   - Na mesma página **Settings → Database**
   - Em **Connection string**, clique em **"Copy"**
   - Formato: `postgresql+psycopg://postgres:[SUA_SENHA]@db.xxx.supabase.co:5432/postgres`
   - Essa string vai na variável `DATABASE_URL`

### 1.5 Crie o bucket de storage
1. No menu à esquerda, vá em **Storage**
2. Clique em **"New bucket"**
3. Configure:
   - **Name**: `evidencias`
   - **Public bucket**: ✅ Marque essa opção
4. Clique em **"Create bucket"**

---

## 2. Criar conta no Render

### 2.1 Acesse o site
- Abra no navegador: **https://render.com**

### 2.2 Crie sua conta
1. Clique em **"Sign Up"**
2. Escolha **"Continue with GitHub"**
3. Se não tiver GitHub, crie uma conta em **https://github.com** primeiro
4. Autorize o Render a acessar seu GitHub

### 2.3 Conecte seu repositório
1. Após login, vá em **"New +"** → **"Web Service"**
2. Na página "Connect a repository":
   - Clique em **"Configure account"** se pedir
   - Selecione seu repositório GitHub
   - Se ainda não tem repositório, volte e faça o passo 3 primeiro

---

## 3. Criar repositório no GitHub

### 3.1 Acesse o GitHub
- Abra: **https://github.com**

### 3.2 Crie o repositório
1. Clique no botão **"+"** → **"New repository"**
2. Configure:
   - **Repository name**: `checklist-frota`
   - **Description**: "Sistema de checklist de frota"
   - **Public/Private**: Private
   - **Add a README file**: ✅ Marque
3. Clique em **"Create repository"**

### 3.3 Faça upload do código
Na página do repositório vazio:

1. Clique em **"uploading an existing file"**
2. Arraste todos os arquivos da pasta do projeto
3. Clique em **"Commit changes"**

---

## 4. Deploy no Render

### 4.1 Crie o Web Service
1. No Render, vá em **"New +"** → **"Web Service"**
2. Selecione seu repositório `checklist-frota`
3. Configure:
   - **Name**: `checklist-api`
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --chdir backend wsgi:app --bind 0.0.0.0:$PORT`
4. Clique em **"Create Web Service"**

### 4.2 Configure as variáveis de ambiente
Após criar, vá em **"Environment"** e adicione:

| Variável | Valor |
|----------|-------|
| `SECRET_KEY` | Gere uma chave forte (ex: uma senha aleatória) |
| `DATABASE_URL` | A connection string do Supabase |
| `SUPABASE_URL` | A URL do seu projeto Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | A service role key |
| `SUPABASE_STORAGE_BUCKET` | `evidencias` |
| `STORAGE_BACKEND` | `supabase` |
| `TOKEN_MAX_AGE_SECONDS` | `28800` |
| `FREE_DB_LIMIT_MB` | `500` |
| `FREE_STORAGE_LIMIT_MB` | `1024` |

5. Clique em **"Save Changes"**

### 4.3 Aguarde o deploy
- O Render vai baixar o código e instalar dependências
- Aguarde ~3-5 minutos
- Quando terminar, você verá uma URL como: `https://checklist-api.onrender.com`

### 4.4 Copie a URL do backend
- Anote a URL pública (ex: `https://checklist-api.onrender.com`)
- Você vai precisar para o frontend

---

## 5. Deploy do Frontend (Web App)

### 5.1 Atualize o config.js
1. Edite o arquivo: `web_app/static/js/config.js`
2. Altere a linha:
   ```js
   API_BASE_URL: "https://checklist-api.onrender.com",
   ```
   (coloque sua URL do backend)

### 5.2 Faça commit da mudança
1. No GitHub, vá no repositório
2. Edite o arquivo `web_app/static/js/config.js`
3. Faça o commit

### 5.3 Crie o Static Site no Render
1. No Render, vá em **"New +"** → **"Static Site"**
2. Selecione o repositório
3. Configure:
   - **Name**: `checklist-web`
   - **Build Command**: (deixe vazio)
   - **Publish directory**: `web_app`
4. Clique em **"Create Static Site"**

### 5.4 Aguarde e pegue a URL
- Após ~2 minutos, terá uma URL como: `https://checklist-web.onrender.com`
- Essa é a URL do seu sistema!

---

## 6. Testar o sistema

1. Abra a URL do frontend no navegador
2. Faça login (use o usuário admin criado localmente ou crie um novo)
3. Teste criar um checklist
4. Tire uma foto e veja se salva no Supabase Storage

---

## Problemas comuns

### "Build failed"
- Verifique se o `requirements.txt` está no diretório raiz
- Verifique se o `backend/wsgi.py` existe

### "Database connection failed"
- Verifique se a `DATABASE_URL` está correta
- Verifique se o banco Supabase está ativo

### "Fotos não salvam"
- Verifique se o bucket `evidencias` foi criado
- Verifique se a `SUPABASE_SERVICE_ROLE_KEY` está correta
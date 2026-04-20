# Sistema de Checklist de Frota Portuaria

Sistema corporativo completo para checklist de manutencao de frota portuaria com:

- Backend Flask + SQLAlchemy pronto para PostgreSQL em nuvem
- App desktop em PySide6 com visual moderno
- Web app responsivo para motoristas em celular
- Gestao de nao conformidades com foto antes/depois
- Cadastro de equipamentos com foto, edicao e retirada
- Importacao inicial de cavalos e carretas a partir do Excel de inventario
- Gerenciamento de logins com perfil admin
- Controle de pecas, filtros e relatorios macro/micro
- Estrutura preparada para gerar `.exe` com PyInstaller

## Estrutura

```text
backend/
desktop/
web_app/
requirements.txt
```

## Funcionalidades principais

- Login simples por usuario (`motorista` ou `gestor`)
- Cadastro e listagem de veiculos
- Checklist validado por tipo:
  - `cavalo`: 65 itens
  - `carreta`: 19 itens
- Itens de checklist configuraveis pelo sistema, com foto de referencia opcional
- Nao conformidade com:
  - observacao
  - foto antes obrigatoria
  - foto depois opcional
  - codigo e descricao de peca
  - status de resolucao
- Relatorios:
  - dashboard
  - macro por item
  - micro por veiculo
  - consulta detalhada por item

## Usuarios padrao

Criados automaticamente na primeira inicializacao:

- Admin: `admin` / `123456`
- Gestor: `gestor` / `123456`
- Motorista: `motorista` / `123456`

O desktop agora abre com `admin / 123456` preenchido por padrao.

## Inventario da frota

O backend procura automaticamente o arquivo:

```text
INVENTÁRIO FROTA 2026.xlsx
```

nas pastas `OneDrive*/Documentos` do usuario atual e importa as abas:

- `CARRETAS`
- `CAVALOS`

Campos importados:

- frota
- tipo
- placa
- ano
- chassi
- configuracao
- modelo
- atividade
- status
- local
- descricao

Tambem e possivel disparar a importacao manualmente pela tela `Equipamentos` no desktop.

## Banco de dados

O projeto esta preparado para PostgreSQL via `DATABASE_URL`.

Exemplo:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/checklist_frota
```

Para subir rapidamente em desenvolvimento, o backend faz fallback para SQLite local se `DATABASE_URL` nao estiver definida. Em producao, use PostgreSQL.

Se voce ja tiver rodado a versao anterior com o banco SQLite antigo, recrie o arquivo `backend/checklist_frota.db` ou aplique migracao antes de usar esta nova versao, porque o schema de equipamentos foi ampliado.

## Instalacao

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Executando o backend

```powershell
cd backend
python run.py
```

Backend padrao local: `http://127.0.0.1:5000`
Backend padrao em nuvem: `https://checklist-frota-qngw.onrender.com`

Uploads ficam em `backend/uploads/`.

## Executando o app desktop

Com o backend rodando:

```powershell
python desktop/main.py
```

Use a URL da API no login. O desktop ja abre com a API em nuvem por padrao, mas voce pode trocar para `http://127.0.0.1:5000` se quiser testar localmente.

No desktop voce tera:

- `Equipamentos`: cadastrar, editar, retirar, anexar foto e importar inventario
- `Logins`: criar e gerenciar acessos

## Executando o web app mobile

Sirva a pasta `web_app` localmente:

```powershell
cd web_app
python -m http.server 5500
```

Depois abra no celular ou navegador:

```text
http://SEU-IP:5500
```

Na tela de login do web app, informe a URL do backend.

## API principal

### Auth

- `POST /login`

### Veiculos

- `GET /veiculos`
- `POST /veiculos`
- `PUT /veiculos/<id>`
- `DELETE /veiculos/<id>`
- `POST /veiculos/importar-inventario`

### Usuarios

- `GET /usuarios`
- `POST /usuarios`
- `PUT /usuarios/<id>`

### Checklist

- `GET /config/checklists`
- `GET /checklist-itens`
- `POST /checklist-itens`
- `PUT /checklist-itens/<id>`
- `DELETE /checklist-itens/<id>`
- `POST /checklist`
- `GET /checklist`
- `GET /checklist/<veiculo>`

### Nao conformidades

- `GET /nao_conformidades`
- `GET /nao_conformidades?tipo=farol`
- `GET /nao_conformidades?veiculo=CV800`
- `PUT /nao_conformidade/<id>/resolver`

### Upload

- `POST /upload`
- `GET /uploads/<arquivo>`

### Relatorios

- `GET /relatorios/dashboard`
- `GET /relatorios/macro`
- `GET /relatorios/micro`
- `GET /relatorios/item?item=farol`

## Exemplo de payload de checklist

```json
{
  "vehicle_id": 1,
  "itens": [
    {
      "item_nome": "Farol alto",
      "status": "OK"
    },
    {
      "item_nome": "Farol baixo",
      "status": "NC",
      "observacao": "Lampada queimada",
      "foto_antes": "/uploads/cv800_farol_baixo_motorista_2026-04-11-103000.jpg"
    }
  ]
}
```

Observacao:
- O backend exige o conjunto completo de itens do tipo do veiculo.
- Para itens `NC`, `foto_antes` e obrigatoria.

## Producao

- Use PostgreSQL gerenciado e variavel `DATABASE_URL`
- Troque `SECRET_KEY`
- Sirva o backend com `waitress` ou outro servidor WSGI
- Coloque `backend/uploads` em storage persistente ou volume dedicado
- Proteja o acesso a arquivos e ajuste CORS para o dominio real

Exemplo com Waitress:

```powershell
cd backend
waitress-serve --host=0.0.0.0 --port=5000 run:app
```

## Gerar executavel `.exe`

Com o ambiente virtual ativo:

```powershell
pyinstaller desktop/ChecklistFrota.spec --noconfirm
```

Saida esperada:

```text
dist/ChecklistFrotaDesktop.exe
```

O executavel herda o endereco da API por padrao de `CHECKLIST_API_URL` e, sem variavel definida, usa a nuvem:

```text
https://checklist-frota-qngw.onrender.com
```

## Observacoes de arquitetura

- `backend` concentra modelo de dados, regras e API
- `desktop` consome a API e foca no fluxo de gestao
- `web_app` consome a API e foca no checklist mobile
- A regra de checklist por tipo de veiculo fica centralizada em `backend/app/services/checklist_catalog.py`

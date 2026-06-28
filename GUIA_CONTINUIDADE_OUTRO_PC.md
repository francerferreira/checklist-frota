# GUIA DE CONTINUIDADE DO SISTEMA EM OUTRO PC

Data de referencia: 2026-06-28

## 1. Objetivo deste guia

Este arquivo foi criado para servir como ponto unico de continuidade do projeto em outro computador.

Pense nele como a pasta tecnica do sistema:

- o que o sistema e
- quais pecas ele usa
- onde cada parte mora
- como instalar
- como executar
- como publicar
- quais arquivos consultar quando for manter ou evoluir

## 2. Resumo executivo do sistema

Nome do projeto:
- `SISTEMA DE CHECKLIST FROTA`

Arquitetura geral:
- `backend/` = motor do sistema
- `desktop/` = painel administrativo completo
- `web_app/` = operacao mobile/web

Analogia simples:
- `backend` e o motor e a caixa de regras
- `banco` e a memoria do veiculo
- `API` e o chicote que leva os comandos
- `desktop` e o painel completo da cabine
- `web_app` e a prancheta de campo para uso rapido

## 3. Stack real do projeto

Backend:
- Python
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-Cors
- SQLAlchemy
- Waitress
- Gunicorn

Desktop:
- Python
- PySide6
- Requests
- PyInstaller

Web mobile:
- HTML
- CSS
- JavaScript puro
- localStorage
- IndexedDB
- service worker preparado

Relatorios e apoio:
- ReportLab
- OpenPyXL

Dependencias declaradas:
- ver `requirements.txt`

## 4. Estrutura de pastas principal

Raiz do projeto:

```text
backend/
desktop/
web_app/
tests/
tools/
data/
exports/
build/
dist/
README.md
requirements.txt
render.yaml
.env.example
```

Pastas mais importantes:

- `backend/`
  - API, modelos, servicos, upload e regras
- `desktop/`
  - app de gestao em PySide6
- `web_app/`
  - interface mobile/web
- `tests/`
  - testes automatizados
- `tools/`
  - scripts de geracao e manutencao
- `dist/`
  - saidas de empacotamento

## 5. Pontos de entrada do sistema

Backend local:
- `backend/run.py`

WSGI de deploy:
- `wsgi.py`
- `backend/wsgi.py`

App factory:
- `backend/app/__init__.py`

Desktop:
- `desktop/main.py`

Web mobile:
- `web_app/index.html`

## 6. Como o sistema sobe

### 6.1 Backend

Fluxo:
1. `backend/run.py` chama `create_app()`
2. `backend/app/__init__.py` carrega `.env`
3. aplica configuracao de `backend/app/config.py`
4. inicializa banco, migrate e CORS
5. registra blueprints
6. cria tabelas
7. aplica ajustes de schema em tempo de execucao
8. faz seed inicial
9. sobe endpoint `/health`

Endpoint de saude:
- `GET /health`

Resposta esperada:

```json
{"status":"ok"}
```

### 6.2 Desktop

Fluxo:
1. `desktop/main.py` cria o `QApplication`
2. aplica tema global
3. instancia `APIClient`
4. tenta subir backend embutido se a URL for local
5. abre `LoginWindow`
6. apos login abre `MainWindow`

Arquivo importante:
- `desktop/embedded_backend.py`

Comportamento:
- se o desktop estiver apontando para `127.0.0.1` ou `localhost`
- e o backend nao responder
- ele tenta subir o backend embutido com banco local

### 6.3 Web mobile

Fluxo:
1. abre `web_app/index.html`
2. carrega `web_app/static/js/config.js`
3. carrega `web_app/static/js/app.js`
4. resolve a URL da API
5. autentica
6. carrega modulos e dados

## 7. Configuracao e variaveis de ambiente

Arquivo base:
- `.env.example`

Variaveis encontradas:

- `SECRET_KEY`
- `DATABASE_URL`
- `TOKEN_MAX_AGE_SECONDS`
- `API_BASE_URL`
- `INVENTORY_FILE`
- `WASH_CONTROL_FILE`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET`
- `STORAGE_BACKEND`
- `FREE_DB_LIMIT_MB`
- `FREE_STORAGE_LIMIT_MB`
- `BACKUP_FOLDER`

Comportamentos importantes:

- sem `DATABASE_URL`, o backend cai para SQLite local
- com `CHECKLIST_FORCE_LOCAL_DB=1`, o backend tambem usa banco local
- com `STORAGE_BACKEND=supabase` e credenciais validas, uploads vao para Supabase
- sem isso, uploads vao para pasta local

## 8. Banco de dados e persistencia

Arquivo central:
- `backend/app/config.py`

Modo local:
- SQLite em arquivo local

Modo producao:
- PostgreSQL por `DATABASE_URL`

Normalizacao da URL:
- o sistema converte formatos `postgres://`, `postgresql://` e `postgresql+psycopg://` para `postgresql+psycopg2://`

Persistencia local relevante:
- banco SQLite local
- uploads locais
- backups locais

Persistencia em nuvem relevante:
- PostgreSQL
- Supabase Storage

## 9. Seed inicial do sistema

Arquivo:
- `backend/app/services/seed_service.py`

Usuarios criados automaticamente se nao existirem:
- `admin / 123456`
- `gestor / 123456`
- `motorista / 123456`
- `mecanico / 123456`
- `francer / 123456`

Tambem acontece no seed:
- criacao do catalogo base de checklist
- tentativa de importar inventario inicial se a base estiver vazia
- sincronizacao inicial da fila de lavagem

## 10. Modulos de negocio encontrados

### 10.1 Frota / equipamentos

Arquivos principais:
- `backend/app/routes/vehicles.py`
- `backend/app/models/vehicle.py`
- `desktop/ui/equipment_page.py`

Responsabilidade:
- cadastro
- edicao
- retirada
- historico
- importacao de inventario

### 10.2 Usuarios e acesso

Arquivos principais:
- `backend/app/routes/auth.py`
- `backend/app/routes/users.py`
- `backend/app/models/user.py`
- `desktop/ui/login_window.py`
- `desktop/ui/users_page.py`

Responsabilidade:
- login
- logout
- gestao de usuarios
- troca da propria senha
- perfis

Perfis observados:
- `admin`
- `gestor`
- `motorista`
- `mecanico`

### 10.3 Checklist

Arquivos principais:
- `backend/app/routes/checklist.py`
- `backend/app/models/checklist.py`
- `backend/app/models/checklist_catalog_item.py`
- `backend/app/services/checklist_catalog.py`
- `desktop/ui/checklist_items_page.py`
- `desktop/ui/checklist_history_page.py`
- `web_app/static/js/app.js`

Responsabilidade:
- catalogo de itens
- checklist por veiculo
- historico
- matriz historica
- agrupamento e validacao de itens

### 10.4 Nao conformidades

Arquivos principais:
- `backend/app/routes/non_conformities.py`
- `backend/app/routes/mechanic_non_conformities.py`
- `backend/app/models/mechanic_non_conformity.py`
- `desktop/ui/non_conformities_page.py`

Responsabilidade:
- registrar problemas
- evidencias antes/depois
- resolucao
- central de acompanhamento

### 10.5 Inspecoes em massa / atividades

Arquivos principais:
- `backend/app/routes/activities.py`
- `backend/app/models/activity.py`
- `desktop/ui/activities_page.py`

Responsabilidade:
- abrir inspecao em lote
- aplicar em varios equipamentos
- auditar item por item
- vincular material e evidencias

### 10.6 Materiais / estoque

Arquivos principais:
- `backend/app/routes/materials.py`
- `backend/app/models/material.py`
- `desktop/ui/materials_page.py`

Responsabilidade:
- cadastro de materiais
- saldo
- estoque minimo
- movimentos
- ajustes
- consumo ligado a atividades e manutencao

### 10.7 Manutencao

Arquivos principais:
- `backend/app/routes/maintenance.py`
- `backend/app/models/maintenance.py`
- `desktop/ui/maintenance_page.py`
- `backend/app/services/maintenance_pdf_export_service.py`

Responsabilidade:
- programacao
- agenda
- mecanico responsavel
- materiais
- ordem de servico
- relatorios PDF

### 10.8 Lavagens

Arquivos principais:
- `backend/app/routes/washes.py`
- `backend/app/models/wash.py`
- `desktop/ui/washes_page.py`
- `backend/app/services/wash_service.py`
- `backend/app/services/wash_pdf_export_service.py`

Responsabilidade:
- fila operacional
- programacao mensal
- preventiva
- bloqueio de dias
- historico
- valores
- comprovacao da lavagem

### 10.9 Relatorios

Arquivos principais:
- `backend/app/routes/reports.py`
- `backend/app/services/report_service.py`
- `desktop/ui/reports_page.py`
- `desktop/services/export_service.py`

Responsabilidade:
- dashboard
- macro
- micro
- produtividade
- item detalhado

### 10.10 Pacotes de resolucao

Arquivos principais:
- `backend/app/routes/resolution_packages.py`
- `backend/app/models/resolution_package.py`
- `backend/app/services/resolution_package_service.py`

Responsabilidade:
- agrupar nao conformidades relacionadas
- sugerir e criar pacotes de tratativa

### 10.11 Auditoria

Arquivos principais:
- `backend/app/models/audit_log.py`
- `backend/app/services/audit_service.py`
- `backend/app/routes/admin.py`
- `desktop/ui/audit_logs_page.py`

Responsabilidade:
- registrar alteracoes relevantes
- expor visualizacao administrativa

### 10.12 Regras administrativas

Arquivos principais:
- `backend/app/routes/admin.py`
- `backend/app/services/intelligent_rules_service.py`
- `desktop/ui/admin_rules_page.py`

Responsabilidade:
- status de armazenamento
- regras inteligentes
- compatibilidade
- homologacao
- backup
- limpeza administrativa

## 11. Modelos de dados principais

Modelos exportados em `backend/app/models/__init__.py`:

- `User`
- `Vehicle`
- `Checklist`
- `ChecklistItem`
- `ChecklistCatalogItem`
- `MechanicNonConformity`
- `Activity`
- `ActivityItem`
- `ActivityNonConformityLink`
- `Material`
- `MaterialMovement`
- `MaintenanceSchedule`
- `MaintenanceScheduleItem`
- `MaintenanceMaterial`
- `MaintenanceWorkOrder`
- `ResolutionPackage`
- `ResolutionPackageLink`
- `AuditLog`
- `SystemSetting`
- `WashQueueItem`
- `WashRecord`
- `WashPlanConfig`
- `WashBlockedDay`
- `WashScheduleDecision`

Leitura pratica:
- `Vehicle` = cadastro base da frota
- `Checklist` e `ChecklistItem` = execucao do checklist
- `Material` = estoque
- `Maintenance*` = planejamento e execucao da manutencao
- `Wash*` = fila e cronograma de lavagem
- `AuditLog` = trilha do que mudou

## 12. Rotas e grupos da API

Blueprints registrados:

- `auth`
- `vehicles`
- `users`
- `activities`
- `maintenance`
- `materials`
- `checklist`
- `mechanic_non_conformities`
- `non_conformities`
- `resolution_packages`
- `upload`
- `reports`
- `washes`
- `admin`

Rotas principais por grupo:

Auth:
- `POST /login`
- `POST /logout`

Veiculos:
- `GET /veiculos`
- `GET /veiculos/<id>/historico`
- `POST /veiculos`
- `PUT /veiculos/<id>`
- `DELETE /veiculos/<id>`
- `POST /veiculos/importar-inventario`

Usuarios:
- `GET /usuarios`
- `GET /usuarios/mecanicos`
- `PUT /usuarios/me/senha`
- `POST /usuarios`
- `PUT /usuarios/<id>`
- `DELETE /usuarios/<id>`

Checklist:
- `GET /config/checklists`
- `GET /checklist-itens`
- `POST /checklist-itens`
- `PUT /checklist-itens/<id>`
- `DELETE /checklist-itens/<id>`
- `POST /checklist`
- `GET /checklist`
- `GET /checklist/historico-matriz`
- `GET /checklists/<id>`
- `GET /checklist/<veiculo>`

Nao conformidades:
- `GET /nao_conformidades`
- `PUT /nao_conformidade/<id>/resolver`
- `POST /nao_conformidade/<id>/atividade`

Nao conformidades do mecanico:
- `GET /mecanico/nao_conformidades`
- `POST /mecanico/nao_conformidades`
- `PUT /mecanico/nao_conformidades/<id>/resolver`

Atividades:
- `GET /atividades`
- `GET /atividades/<id>`
- `POST /atividades`
- `POST /atividades/nao_conformidades/lote`
- `PUT /atividades/<id>/itens/<item_id>`
- `PUT /atividades/<id>/materiais`

Materiais:
- `GET /materiais`
- `GET /materiais/relatorio`
- `POST /materiais`
- `PUT /materiais/<id>`
- `DELETE /materiais/<id>`
- `GET /materiais/<id>/movimentos`
- `POST /materiais/<id>/ajustar_estoque`

Manutencao:
- `GET /manutencao/visao`
- `GET /manutencao/mecanico`
- `GET /manutencao/programacoes`
- `GET /manutencao/relatorio/pdf`
- `GET /manutencao/os/<id>/pdf`
- `POST /manutencao/programacoes`
- `POST /manutencao/sugestao-responsavel`
- `POST /manutencao/sugestao-agenda`
- `GET /manutencao/programacoes/<id>/sugestao-peca`
- `POST /manutencao/programacoes/sincronizar-nc`
- `POST /manutencao/programacoes/<id>/materiais`
- `PUT /manutencao/programacoes/<id>/cronograma`
- `PUT /manutencao/itens/<id>/reprogramar`
- `PUT /manutencao/itens/<id>`

Lavagens:
- `GET /lavagens/visao`
- `GET /lavagens/relatorio/pdf`
- `PUT /lavagens/valores`
- `POST /lavagens/sincronizar`
- `POST /lavagens/reclassificar`
- `POST /lavagens/registrar`
- `PUT /lavagens/fila/<id>/indisponivel`
- `PUT /lavagens/fila/<id>/disponivel`
- `PUT /lavagens/preventiva`
- `PUT /lavagens/plano`
- `PUT /lavagens/plano/bloqueio`
- `GET /lavagens/mensagem-amanha`
- `PUT /lavagens/cronograma/decisao`
- `PUT /lavagens/cronograma/reeditar`

Relatorios:
- `GET /relatorios/dashboard`
- `GET /relatorios/produtividade`
- `GET /relatorios/macro`
- `GET /relatorios/micro`
- `GET /relatorios/item`

Upload:
- `POST /upload`
- `GET /uploads/supabase/<path>`
- `GET /uploads/<path>`

Admin:
- `GET /admin/audit-logs`
- `GET /admin/storage/status`
- `GET /admin/intelligent-rules`
- `PUT /admin/intelligent-rules`
- `GET /admin/compatibility-status`
- `GET /admin/homologation-status`
- `POST /admin/backups/create`
- `GET /admin/backups/<path>/download`
- `POST /admin/cleanup/old-records`

## 13. Desktop: modulos visiveis para o usuario

Pela janela principal (`desktop/ui/main_window.py`), o desktop expoe:

Cadastro:
- Frota
- Logins

Tabelas:
- Checklist
- Materiais

Movimento:
- Inspecoes
- Lavagens
- Manutencao

Relatorios:
- Relatorios
- Produtividade
- Historico Checklist

Utilitarios:
- Dashboard
- Central de Resolucao
- Backup
- Logs de Auditoria
- Configuracao Administrativa

## 14. Web mobile: comportamento funcional observado

Arquivo central:
- `web_app/static/js/app.js`

Recursos observados:
- login
- selecao de equipamento
- checklist por modulo
- obrigatoriedade de evidencia em `NC`
- upload de imagem
- fila offline de checklist
- sincronizacao quando a conexao volta
- IndexedDB para rascunhos e fila
- encerramento de sessao por inatividade apos 30 minutos
- leitura e formatacao no fuso `America/Manaus`

Arquivo de configuracao:
- `web_app/static/js/config.js`

API padrao configurada:
- `https://checklist-frota-qngw.onrender.com`

## 15. Uploads e evidencias

Arquivo central:
- `backend/app/services/storage_service.py`

Extensoes aceitas:
- `.jpg`
- `.jpeg`
- `.png`
- `.webp`

Backends de armazenamento:
- `local`
- `supabase`

Logica:
- se Supabase estiver configurado corretamente, usa nuvem
- senao, salva localmente

## 16. Importacao inicial de inventario

Arquivo central:
- `backend/app/services/inventory_import_service.py`

Planilha esperada:
- abas `CARRETAS` e `CAVALOS`

Comportamento:
- importa novos veiculos
- atualiza veiculos existentes
- preserva foto existente

## 17. Scripts e atalhos encontrados

Atalhos Windows:
- `abrir_checklist_frota.bat`
- `abrir_desktop_nuvem.bat`
- `abrir_web_mobile.bat`
- `gerar_portable_checklist_frota.bat`
- `migrar_frota_para_nuvem.bat`
- `backup_checklist_cloud.bat`

Scripts PowerShell / Python:
- `backup_checklist_cloud.ps1`
- `tools/build_portable_desktop.ps1`
- `tools/generate_system_manual.py`
- `tools/generate_nc_flow_manual.py`
- `tools/migrate_vehicles_to_cloud.py`
- `backend/tools/force_seed_aux_checklists.py`

## 18. Deploy atual identificado

Arquivo:
- `render.yaml`

Servicos declarados:

API:
- nome: `checklist-api`
- tipo: web
- start: `gunicorn wsgi:app --bind 0.0.0.0:$PORT`

Web:
- nome: `checklist-web`
- tipo: static
- publica `web_app`

Variaveis importantes no Render:
- `SECRET_KEY`
- `TOKEN_MAX_AGE_SECONDS`
- `STORAGE_BACKEND=supabase`
- `SUPABASE_STORAGE_BUCKET=evidencias`
- `FREE_DB_LIMIT_MB`
- `FREE_STORAGE_LIMIT_MB`
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

URL padrao encontrada no projeto:
- `https://checklist-frota-qngw.onrender.com`

## 19. Como preparar outro PC

### 19.1 Passos minimos

1. Instalar Python compatível com o projeto.
2. Copiar ou clonar o repositorio.
3. Criar ambiente virtual.
4. Instalar dependencias.
5. Criar `.env` a partir de `.env.example`.
6. Escolher se vai usar:
   - nuvem existente
   - backend local com SQLite
   - backend local com PostgreSQL

### 19.2 Comandos base

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

### 19.3 Rodar backend local

```powershell
cd backend
python run.py
```

### 19.4 Rodar desktop

```powershell
python desktop/main.py
```

### 19.5 Rodar web mobile

```powershell
cd web_app
python -m http.server 5500
```

## 20. Modos praticos de continuidade no outro PC

### Modo A: so continuar usando a nuvem existente

Use quando:
- voce quer trabalhar rapido
- nao quer subir backend local

Como:
- deixe o desktop apontando para a API em nuvem
- ou use `abrir_desktop_nuvem.bat`
- no web mobile, a configuracao padrao ja aponta para a API em nuvem

### Modo B: desenvolver local com banco local

Use quando:
- quer testar sem depender da internet
- quer rodar tudo no proprio PC

Como:
- subir `backend/run.py`
- usar SQLite local
- apontar desktop e web para `http://127.0.0.1:5000`

### Modo C: desenvolver local com PostgreSQL

Use quando:
- quer ambiente mais proximo da producao

Como:
- definir `DATABASE_URL`
- subir backend
- apontar clientes para a API local

## 21. Testes encontrados

Arquivos de teste presentes:

- `tests/test_audit_service.py`
- `tests/test_checklist_catalog_group_rules.py`
- `tests/test_checklist_grouped_submission.py`
- `tests/test_checklist_grouping_schema.py`
- `tests/test_checklist_history_matrix.py`
- `tests/test_desktop_navigation.py`
- `tests/test_export_service.py`
- `tests/test_external_file_discovery.py`
- `tests/test_message_service.py`
- `tests/test_severity_service.py`
- `tests/test_timezone.py`
- `tests/test_upload_security.py`
- `tests/test_vehicle_routes.py`
- `tests/test_web_mobile_playwright.py`
- `tests/test_web_mobile_shell_contract.py`

Leitura pratica:
- ha cobertura em backend
- ha cobertura em servicos
- ha validacao de contrato web mobile
- ha teste de navegacao desktop

## 22. Documentos ja existentes no projeto

Arquivos de apoio encontrados:

- `README.md`
- `MAPA_GERAL_DO_SISTEMA.md`
- `ARQUITETURA_MODELO_CHECKLIST_FROTA.txt`
- `PASSO_A_PASSO_DEPLOY.md`
- `DEPLOY_RENDER_SUPABASE.md`
- `MANUAL_DE_INSTRUCAO_SISTEMA_CHECKLIST_FROTA.pdf`
- `MANUAL_FLUXO_NAO_CONFORMIDADE.pdf`
- `web_app/HOMOLOGACAO_WEB_MOBILE.md`
- `desktop/docs/FASE0_CHECKLIST_REGRESSAO_FUNCIONAL.md`
- `desktop/docs/FASE7_HOMOLOGACAO_GO_LIVE.md`

Sugestao pratica:
- use este guia como ponto inicial
- e os documentos acima como apoio por tema

## 23. Arquivos mais importantes para manutencao

Se precisar entender o sistema rapido, leia nesta ordem:

1. `README.md`
2. `GUIA_CONTINUIDADE_OUTRO_PC.md`
3. `backend/app/__init__.py`
4. `backend/app/config.py`
5. `backend/app/routes/__init__.py`
6. `backend/app/models/__init__.py`
7. `desktop/main.py`
8. `desktop/ui/main_window.py`
9. `desktop/api_client.py`
10. `web_app/static/js/config.js`
11. `web_app/static/js/app.js`
12. `render.yaml`

## 24. Riscos operacionais para troca de PC

Pontos de atencao:

- `.env` precisa acompanhar o ambiente certo
- `DATABASE_URL` muda o modo de persistencia
- upload local nao substitui Supabase automaticamente
- se o outro PC nao tiver acesso ao mesmo banco, vai parecer sistema vazio
- o desktop pode estar apontando para nuvem ou local, conforme a URL usada
- portable em `dist/` nao substitui o codigo fonte para manutencao

Analogia simples:
- levar o projeto para outro PC sem levar configuracao e como trocar o motorista mas esquecer a chave, o documento e a rota

## 25. Checklist de transferencia para outro PC

1. Confirmar se vai usar nuvem existente ou ambiente local.
2. Levar a pasta do projeto ou clonar do Git.
3. Criar `.venv`.
4. Instalar `requirements.txt`.
5. Criar `.env`.
6. Validar `DATABASE_URL`.
7. Validar `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` se usar nuvem.
8. Subir backend e testar `/health`.
9. Abrir desktop e validar login.
10. Abrir web mobile e validar login e checklist.

## 26. Resumo final

Este projeto nao e um sistema unico e simples. Ele e um ecossistema com tres frentes:

- API/backend
- desktop administrativo
- web mobile operacional

Para continuar em outro PC sem se perder:

- use este guia como mapa principal
- use o `README.md` para subir rapido
- use `desktop/ui/main_window.py` para ver o menu do produto
- use `backend/app/routes/` para ver as entradas da API
- use `backend/app/models/` para ver os dados
- use `web_app/static/js/app.js` para ver o comportamento operacional mobile

Se a comparacao ajudar:
- o backend e o motor
- o desktop e o painel completo
- o web mobile e a prancheta de campo
- este arquivo e o manual de transferencia da oficina

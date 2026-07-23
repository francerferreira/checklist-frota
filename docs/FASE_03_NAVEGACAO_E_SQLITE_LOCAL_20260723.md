# Fase 3 - Navegação e SQLite local

## Entrega executada

- Criada uma nova base SQLite local em `backend/checklist_frota.db`, com 49 tabelas e sem reaproveitar a base anterior.
- Mantido o backup da base anterior em `backend/backups/checklist_frota_pre_rebuild_20260723_155944.db`.
- Adicionado `abrir_backend_sqlite_local.bat` para iniciar o backend em modo local de forma explícita.
- Reorganizada a navegação desktop por fluxo operacional: Operação, Manutenção e PCM, Ativos e suprimentos, Gestão e histórico e Administração.
- Incluída busca de módulos na barra lateral e indicação da tela ativa na barra de status.

## Limites preservados

- SQLite é somente para desenvolvimento local. PostgreSQL permanece o destino de homologação e produção.
- Nenhuma API, permissão, regra de negócio ou dado externo foi alterado nesta fase.
- A busca apenas filtra as telas já autorizadas ao perfil logado; ela não concede acessos novos.

## Como validar

1. Execute `abrir_backend_sqlite_local.bat`.
2. Abra o desktop e entre com `http://127.0.0.1:5000`.
3. Pesquise `central` na navegação e confirme que somente a Central Operacional permanece visível.
4. Abra uma tela e confirme o caminho exibido na barra inferior.

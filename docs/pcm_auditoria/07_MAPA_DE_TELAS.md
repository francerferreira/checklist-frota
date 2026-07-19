# Mapa de telas

## Regra de canais

- Desktop: cadastro, planejamento, controle, auditoria e decisao gerencial.
- Web Mobile/PWA: apontamento em campo, checklist, inspecao, horimetro, emergencia e execucao da OS.
- Nao foi encontrada uma segunda aplicacao PCM separada; as duas interfaces consomem a mesma API e o mesmo banco.

## Desktop

As paginas sao criadas por `MainWindow._build_pages()` em `desktop/ui/main_window.py` e filtradas por `PAGE_ACCESS_BY_ROLE` em `desktop/access.py`.

| Tela | Rota/chave | Publico atual | Dados consumidos | Acoes | API principal | Situacao | Lacuna PCM |
|---|---|---|---|---|---|---|---|
| Dashboard | `dashboard` | todos | resumo checklist/frota | consultar | `/relatorios/dashboard` | Implementada | ampliar cards e graficos portuarios |
| Central de Resolucao | `nc` | admin/gestor/mecanico | NC e pacotes | resolver/agrupar | `/nao_conformidades`, `/pacotes_resolucao` | Implementada | integrar origem/tipo de OS |
| Produtividade | `productivity` | admin/gestor/mecanico | usuarios/checklists | consultar | `/relatorios/produtividade` | Implementada | fora do nucleo PCM |
| Historico Checklist | `checklist_history` | admin/gestor | checklists | filtrar/consultar | `/checklist/historico-matriz` | Implementada | preservar |
| Relatorios | `reports` | admin/gestor | macro/micro/item/Base Mestre via API | consultar/exportar | `/relatorios/*` | Implementada | tela dedicada da Base Mestre e KPIs homologados |
| Frota/Equipamentos | `equipment` | admin/gestor | vehicles/perfis/familias/locais | criar/editar/inativar/importar | `/veiculos`, `/equipamentos/estrutura` | Parcial PCM | tela individual consolidada e movimentos |
| Checklist | `checklist_items` | admin/gestor | catalogo e itens | configurar | `/checklist-itens` | Implementada | preservar |
| Templates Tecnicos | `inspection_templates` | admin/gestor | modelos/versionamento | criar/publicar/versionar | `/inspecoes-tecnicas/modelos` | Implementada | preservar/reusar por familia |
| Materiais | `materials` | admin/gestor | materiais/movimentos | CRUD/estoque | `/materiais` | Implementada | integrar reserva por OS |
| Lavagens | `washes` | admin/gestor | fila/plano/registro | programar/registrar | `/lavagens/*` | Implementada | fora do escopo PCM; nao apagar |
| Inspecoes/Atividades | `activities` | admin/gestor/mecanico | atividades/itens | criar/executar | `/atividades` | Implementada | classificar conversao em OS |
| Disponibilidade | `availability` | admin/gestor/mecanico | estado/eventos/horimetro | status/consulta | `/disponibilidade/visao`, `/equipamentos/*` | Parcial | falta grade diaria e correcao de horimetro |
| Emergenciais e OS | `emergencies` | admin/gestor/mecanico | emergencias/OS | triagem, converter, acompanhar | `/emergenciais`, `/ordens-servico` | Implementada | cancelar/reabrir e campos completos |
| Manutencao | `maintenance` | admin/gestor/mecanico | agenda/itens/OS/materiais | programar, reprogramar, executar | `/manutencao/*` | Implementada parcial | tipo oficial e fluxo completo de OS |
| PCM | `pcm` | admin/gestor | planos, agenda, backlog | criar plano, gerar vencidas | `/pcm/*` | Implementada parcial | ciclos 500-6000, faixas e execucao central |
| Suprimentos e Biblioteca | `supply_library` | admin/gestor | depositos, reserva, documentos | gerenciar | `/suprimentos/*`, `/biblioteca-tecnica` | Implementada | anexos normalizados |
| Logins | `users` | admin | usuarios | CRUD/senha | `/usuarios` | Implementada | novos perfis e matriz granular |
| Backup | `cloud_backup` | admin | storage/banco | criar/baixar backup | `/admin/backups/*` | Implementada | ensaio de restauracao PostgreSQL |
| Logs de Auditoria | `audit_logs` | admin | audit_logs | consultar | `/admin/audit-logs` | Implementada | motivo/contexto por evento PCM |
| Configuracao Administrativa | `admin_rules` | admin/gestor | regras/saude | configurar | `/admin/intelligent-rules`, status | Implementada parcial | centralizar parametros PCM |

## Web Mobile/PWA

As telas estao em `web_app/index.html`; o comportamento esta em `web_app/static/js/app.js` e a operacao offline usa IndexedDB/Service Worker.

| Tela | Rota/id | Publico | Dados consumidos | Acoes | API | Situacao | Lacuna |
|---|---|---|---|---|---|---|---|
| Login | `login-screen` | usuario | credenciais | autenticar | `/login` | Implementada | manter |
| Inicio | `home-screen` | autenticado | perfil/sincronizacao | navegar/sincronizar | varias | Implementada | manter operacional |
| Equipamentos | `vehicles-screen` | autenticado | ativos | selecionar, QR, NFC | `/veiculos`, `/operacao-mobile/ativos/*` | Implementada parcial | cartao individual PCM incompleto |
| Checklist | `checklist-screen` | motorista/operacao | catalogo | preencher/foto/enviar | `/config/checklists`, `/checklist` | Implementada | preservar |
| Historico | `checklist-history-screen` | autenticado | historico | filtrar/consultar | `/checklist/historico-matriz` | Implementada | preservar |
| Inspecoes | `activities-screen` e detalhe | workspace | atividades | consultar/executar | `/atividades` | Implementada | preservar |
| Lavagens | `washes-screen` | perfis permitidos | cronograma/fila | registrar/consultar | `/lavagens/*` | Implementada | fora do PCM RTG/LBS |
| Central de Resolucao | `non-conformities-screen` | workspace | NCs | consultar/resolver | `/nao_conformidades`, `/mecanico/*` | Implementada | preservar |
| Manutencao | `maintenance-screen` | workspace | itens do mecanico | executar/apontar | `/manutencao/mecanico`, `/manutencao/itens/*` | Implementada | estados oficiais incompletos |
| Disponibilidade e Horimetro | `availability-screen` | autenticado | ativos/estado/leitura | alterar status/lancar horimetro | `/disponibilidade/visao`, `/equipamentos/*` | Implementada | alertas e correcao ausentes |
| Inspecao Tecnica | `technical-inspections-screen` | autenticado | templates | executar | `/inspecoes-tecnicas/*` | Implementada | preservar |
| Emergencial e OS | `emergencies-screen` | workspace | emergencia/OS | abrir, iniciar, reparar, testar, liberar | `/emergenciais`, `/ordens-servico/*` | Implementada | campos oficiais e cancelar/reabrir |
| Biblioteca Tecnica | `technical-library-screen` | autenticado | documentos | consultar | `/biblioteca-tecnica` | Implementada | filtros por ativo/familia |

## Onde o usuario opera horimetro e preventiva hoje

### Horimetro

1. No Web Mobile, entrar em **Disponibilidade e Horimetro**.
2. `makeAvailabilityCard()` monta o cartao do ativo.
3. `submitHourmeter()` envia a leitura.
4. Online: API de horimetro. Offline: `MOBILE_OPERATION_QUEUE_STORE` e posterior `/operacao-mobile/sincronizar`.
5. Backend: `record_hourmeter()` valida e grava `HourmeterReading`, atualizando `EquipmentOperationalState`.

Nao existe hoje uma tela Desktop central para digitacao diaria em lote.

### Preventiva

1. No Desktop, abrir **PCM**.
2. `PreventivePlanDialog` cadastra equipamento, titulo, gatilho, periodicidade, proxima data/horimetro, prioridade e mecanico.
3. `PCMPage` lista planos e backlog.
4. O botao **Gerar preventivas vencidas** chama `generate_due_preventives()`.
5. A execucao/conclusao ocorre na tela **Manutencao**, nao integralmente na tela PCM.

## Permissoes visuais atuais

| Perfil | Acesso PCM relevante |
|---|---|
| `admin` | todas as paginas, usuarios, backup e auditoria |
| `gestor` | operacao/gestao, inclusive PCM, sem usuarios/backup/audit logs |
| `mecanico` | dashboard, NC, produtividade, atividades, manutencao, disponibilidade, emergenciais |
| `motorista` | somente dashboard Desktop; operacao principal ocorre no Web Mobile conforme APIs |

## Decisao de UX recomendada

- Expandir `PCMPage` como Central de Preventivas.
- Expandir `AvailabilityPage` com modo de lancamento diario central.
- Criar uma unica tela individual dinamica, acessivel do cadastro e pelo QR/NFC.
- Reusar `MaintenancePage` para corretivas programadas e execucao de OS.
- Nao levar planejamento completo ao Web Mobile; manter o mobile simples para apontamento.

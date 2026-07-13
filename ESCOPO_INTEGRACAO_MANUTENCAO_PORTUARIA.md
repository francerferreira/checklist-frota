# Escopo de Integração - Sistema de Manutenção Portuária

Data do levantamento: 12/07/2026  
Projeto-base: Sistema de Checklist de Frota

## 1. Entendimento:

O projeto atual será ampliado para se tornar um único Sistema de Manutenção Portuária. Não será criado um segundo sistema e nenhuma função atual será apagada.

A arquitetura continuará híbrida, usando a mesma API e o mesmo banco:

| Superfície | Responsabilidade principal |
|---|---|
| Desktop PySide6 | Cadastro mestre, administração, engenharia, PCM, planejamento, dashboard executivo, auditoria e relatórios |
| Web/mobile | Operação em campo, checklists, inspeções, fotos, horímetros, emergenciais, execução de OS e atualização de disponibilidade |
| Backend Flask | Regras de negócio, autenticação, permissões, API, relatórios, automações e integrações |
| PostgreSQL/Supabase | Base central e única de produção |

Analogia simples: o desktop será a sala de controle; o web/mobile será a prancheta de campo; o backend e o banco serão o motor e a memória compartilhados pelos dois.

## 2. Objetivo:

Transformar o cadastro e os fluxos atuais de frota em uma plataforma unificada para Frota, RTG, LBS, Spreaders e equipamentos de apoio, preservando IDs, usuários, checklists, evidências, não conformidades, relatórios e histórico existentes.

O resultado esperado é um fluxo único:

`Equipamento -> disponibilidade/horímetro -> checklist ou inspeção -> falha -> emergência ou OS -> planejamento PCM -> execução -> teste/liberação -> histórico -> indicadores`

## 3. Escopo:

### 3.1 Distribuição entre desktop e web/mobile

| Módulo | Desktop | Web/mobile |
|---|---|---|
| Dashboard Executivo | Visão completa, filtros, gráficos e relatórios | Resumo operacional somente leitura |
| Equipamentos | Cadastro, edição, famílias, criticidade, documentos e vínculos | Consulta, identificação e histórico resumido |
| Disponibilidade | Configuração, auditoria e análise histórica | Alteração operacional com motivo, foto e horário |
| Horímetros | Correção autorizada, histórico e regras | Registro em campo com evidência |
| Checklists | Modelos, itens, famílias e versões | Execução e sincronização offline |
| Inspeções Técnicas | Modelos, programação e análise | Execução, medições, fotos e apontamentos |
| Emergenciais | Triagem, prioridade e conversão em OS | Abertura e atualização em campo |
| Ordens de Serviço | Planejamento, recursos, custos, aprovação e encerramento | Aceite, execução, materiais, evidências, teste e conclusão |
| Preventivas e corretivas | Planos, agenda, backlog e programação PCM | Fila de serviços atribuídos |
| Materiais e estoque | Cadastro, estoque, movimentação, reservas e relatórios | Consulta, solicitação e consumo em OS |
| Biblioteca técnica | Cadastro, revisão, validade e vínculos | Consulta por equipamento/família |
| Automações | Configuração e monitoramento | Exibição de alertas e tarefas geradas |
| Auditoria | Consulta completa | Registro automático das ações |
| Relatórios | Emissão gerencial PDF/XLSX/CSV | Consultas e PDFs operacionais essenciais |

### 3.2 Tratamento das RTGs, LBSs e Spreaders

As imagens recebidas serão usadas como referência de organização visual, não como fonte automática de cadastro. Os dados reais deverão vir de inventário validado.

| Família | Organização operacional proposta |
|---|---|
| LBS | Agrupamento por píer e berço, com disponibilidade atual e motivo da indisponibilidade |
| RTG | Agrupamento por pátio e área, incluindo ATR e Alfandegado |
| Spreader | Cadastro individual por patrimônio/número de série/ano, com vínculo temporal à LBS como titular ou reserva |

O spreader não será apenas um texto dentro da LBS. Ele será um equipamento próprio, porque pode trocar de LBS, entrar em manutenção, ter checklist, OS, documentos, custos e histórico próprios.

### 3.3 Módulos incluídos

| Módulo solicitado | Escopo funcional mínimo |
|---|---|
| Dashboard Executivo | Disponibilidade, indisponíveis, OS abertas/atrasadas, backlog, preventivas vencidas, NC abertas, MTBF, MTTR e filtros |
| Cadastro unificado | Frota, RTG, LBS, Spreaders e apoio no mesmo cadastro lógico |
| Disponibilidade operacional | Estado atual e histórico por equipamento, família, área, berço e pátio |
| Horímetros | Leituras, validação crescente, evidência, origem e integração com preventiva |
| Inspeções técnicas | Modelos versionados, itens, medições, criticidade, evidências e geração de falha |
| Emergenciais | Abertura rápida, severidade, parada, responsável, cronologia e conversão em OS |
| Ordens de serviço | Tipo, prioridade, diagnóstico, serviço, equipe, materiais, tempos, testes, liberação e custos |
| Preventivas | Planos por tempo e/ou horímetro, tarefas, periodicidade, tolerância e geração de OS |
| Corretivas programadas | Priorização, janela, recursos, materiais, programação e execução |
| Agenda PCM | Calendário consolidado de OS e preventivas, capacidade e responsáveis |
| Backlog | Consulta derivada das OS abertas, com idade, prioridade, bloqueios e SLA; sem tabela duplicada |
| Biblioteca técnica | Manuais, diagramas, procedimentos, revisões, validade e vínculo por família/equipamento |
| Materiais e estoque | Reaproveitamento do cadastro e movimentações, ampliando aplicação, depósitos, reservas e vínculo com OS |
| MTBF e MTTR | Cálculo com falhas classificadas, horímetro e períodos reais de indisponibilidade |
| Automações | Regras de evento/condição/ação, alertas, geração controlada de OS e histórico de execução |
| Auditoria | Preservação da auditoria atual e inclusão das novas entidades e ações críticas |
| Relatórios gerenciais | Disponibilidade, falhas, manutenção, PCM, materiais, custos, produtividade, MTBF e MTTR |

## 4. Itens verificados:

### 4.1 Arquitetura e tecnologias

| Camada | Situação atual |
|---|---|
| Backend | Python, Flask, SQLAlchemy, Flask-Migrate, Flask-Cors e API REST |
| Desktop | PySide6, cliente HTTP próprio, componentes reutilizáveis, tema corporativo e empacotamento PyInstaller |
| Web/mobile | HTML, CSS e JavaScript puro, responsivo, IndexedDB, localStorage e estrutura de PWA |
| Banco | PostgreSQL por `DATABASE_URL`; SQLite local como fallback |
| Nuvem | Render para API/web e Supabase para PostgreSQL/Storage |
| Arquivos | Upload local ou Supabase Storage, com JPG/JPEG/PNG/WEBP |
| Exportações | PDF, XLSX e CSV; mensagens para WhatsApp/e-mail |

### 4.2 Banco e models

O SQLite local foi consultado em modo somente leitura. Ele possui 24 tabelas, 285 equipamentos, 5 usuários, 256 itens de catálogo, 693 registros de lavagem e 114 itens de fila de lavagem. A base de produção em nuvem não foi inspecionada nesta etapa.

Models atuais:

`User`, `Vehicle`, `Checklist`, `ChecklistItem`, `ChecklistCatalogItem`, `Activity`, `ActivityItem`, `ActivityNonConformityLink`, `MechanicNonConformity`, `ResolutionPackage`, `ResolutionPackageLink`, `MaintenanceSchedule`, `MaintenanceScheduleItem`, `MaintenanceMaterial`, `MaintenanceWorkOrder`, `Material`, `MaterialMovement`, `WashQueueItem`, `WashRecord`, `WashPlanConfig`, `WashBlockedDay`, `WashScheduleDecision`, `AuditLog` e `SystemSetting`.

Distribuição local atual dos equipamentos:

| Tipo | Quantidade |
|---|---:|
| Carreta | 171 |
| Cavalo | 100 |
| Ambulância | 4 |
| Carro simples | 4 |
| Cavalo auxiliar | 3 |
| Caminhão-pipa | 1 |
| Ônibus | 1 |
| Van | 1 |

Não existem tipos RTG, LBS ou Spreader na base local.

### 4.3 Rotas e APIs

Foram identificados 92 endpoints distribuídos entre autenticação, veículos, usuários, checklist, não conformidades, inspeções/atividades, pacotes de resolução, manutenção, OS, materiais, lavagens, relatórios, uploads, auditoria, regras e backup.

Somente `POST /login` é público. Os demais endpoints usam autenticação e guardas de administrador, gestão, mecânico ou usuário autenticado.

### 4.4 Telas atuais

Desktop atual:

`Dashboard`, `Ocorrências`, `Produtividade`, `Equipamentos`, `Checklist`, `Histórico Checklist`, `Materiais`, `Lavagens`, `Inspeções`, `Manutenção`, `Relatórios`, `Logins`, `Backup`, `Logs de Auditoria` e `Regras`.

Web/mobile atual:

`Login`, `Menu`, `Equipamentos`, `Checklist`, `Histórico`, `Inspeções`, `Lavagens`, `Central de Resolução`, `Não Conformidade do Mecânico`, `Manutenção` e alteração de senha.

### 4.5 Autenticação e permissões

Perfis atuais: `admin`, `gestor`, `mecanico` e `motorista`.

A autenticação usa token assinado com expiração. O desktop mantém o token na sessão HTTP; o web/mobile armazena token e usuário no `localStorage`. O logout registra auditoria, mas o token não possui lista de revogação no servidor.

### 4.6 Checklists e não conformidades

O catálogo possui nove tipos fixos e regras de agrupamento. O checklist exige todos os itens da família e foto antes para NC. O fluxo atual permite resolver NC, criar inspeção/atividade, agrupar ocorrências, programar manutenção, gerar OS, consumir material e anexar foto depois.

### 4.7 Relatórios e integrações

Existem relatórios macro, micro, item, produtividade, equipamento, checklist, inspeção, lavagem, material, manutenção e OS. Há exportação PDF/XLSX/CSV, textos de WhatsApp/e-mail, importação de inventário Excel, controle de lavagem Excel, upload no Supabase Storage, backup e fila offline de checklists no web/mobile.

### 4.8 Validação automatizada

Resultado do conjunto atual:

`63 testes passaram, 1 falhou, 12 subtestes passaram e 52 avisos foram emitidos.`

A falha é uma divergência de texto: o teste espera `atividade em massa`, enquanto o produto passou a usar `inspeção em massa`. Também existem avisos de uso legado de `Query.get()` no SQLAlchemy.

O `/health` da API publicada não respondeu em duas tentativas, com limites de 25 e 60 segundos. A disponibilidade externa não foi confirmada.

## 5. Diagnóstico:

### 5.1 Matriz de reaproveitamento

| Capacidade | Estado atual | Decisão |
|---|---|---|
| Arquitetura desktop + mobile + API | Pronta | Manter |
| Cadastro de equipamentos | Pronto para frota, rígido por tipo | Ampliar de forma aditiva |
| Checklist | Maduro para frota | Reaproveitar e vincular a famílias configuráveis |
| Não conformidades | Maduro | Reaproveitar como origem de emergência/OS |
| Inspeções | Parcial, focada em inspeção em massa | Reusar telas e criar modelo técnico versionado |
| Manutenção/agenda | Parcial | Reaproveitar programação, calendário e bloqueios |
| OS | Parcial, gerada por item de programação | Ampliar ciclo de vida, tempos, custos e tipos |
| Preventiva | Parcial e manual | Criar planos recorrentes por data/horímetro |
| Backlog | Parcial por contadores de itens/OS | Criar consulta gerencial derivada, sem duplicar dados |
| Materiais | Funcional para frota | Reaproveitar e remover limitação cavalo/carreta |
| Auditoria | Ampla e automática | Manter e fortalecer criticidade/consulta |
| Regras inteligentes | Parcial, parâmetros e sugestões | Evoluir para automações auditáveis |
| Disponibilidade | Apenas `ON/OFF` e indisponibilidade de lavagem | Criar estado operacional e histórico temporal |
| Horímetro | Inexistente | Criar |
| Biblioteca técnica | Inexistente | Criar |
| MTBF/MTTR | Inexistente | Calcular após dados confiáveis de falha/parada |
| Dashboard executivo portuário | Inexistente | Criar sobre dados consolidados |

### 5.2 Riscos identificados antes da implementação

| Prioridade | Risco | Tratamento obrigatório |
|---|---|---|
| Crítica | Não há migrations versionadas no repositório; o app usa `db.create_all()` e alterações SQL na inicialização | Criar baseline Alembic e parar de depender de alteração estrutural automática |
| Crítica | Desktop pode cair para SQLite local enquanto mobile usa nuvem | Produção deve fixar uma API/banco central; fallback local somente em modo explicitamente controlado |
| Crítica | API publicada não respondeu ao health check | Validar Render, logs, banco, cold start e monitoramento antes de liberar novos módulos |
| Alta | Senhas padrão `123456`, chave de desenvolvimento como fallback e CORS liberado para qualquer origem | Endurecer segurança sem invalidar usuários existentes |
| Alta | Tipos de checklist e aplicação de materiais estão presos a listas fixas | Migrar para famílias relacionais e manter colunas legadas durante transição |
| Alta | OS não guarda diagnóstico, início/fim de falha, início/fim de reparo, teste, liberação e custos | Ampliar OS antes de calcular disponibilidade, MTBF e MTTR |
| Alta | PWA está desativada e o offline cobre principalmente checklist | Definir quais novos fluxos podem operar offline e como resolver conflitos |
| Média | Auditoria é persistida após o commit principal em melhor esforço | Criar monitoramento de falha de auditoria para ações críticas |
| Média | Não há workflow de CI versionado | Criar pipeline de testes e validação de migration antes do deploy |
| Média | Um teste está falhando e há avisos de SQLAlchemy legado | Corrigir baseline antes da Fase 1 |

### 5.3 Dependências de negócio

Antes de cadastrar dados reais, será necessário validar:

- Inventário mestre de Frota, RTG, LBS, Spreaders e apoio, com patrimônio, série, ano e situação.
- Hierarquia oficial de terminal, área, píer, berço e pátio.
- Regra oficial de disponibilidade, restrição, manutenção e indisponibilidade.
- Motivos padronizados de parada e classificação do que conta como falha para MTBF.
- Ponto inicial/final usado para medir MTTR.
- Frequência e fonte do horímetro de cada família.
- Modelos de checklist e inspeção por família.
- Matriz de criticidade, SLA e prioridade.
- Perfis e permissões de Operação, Mecânica, PCM, Almoxarifado, Gestão e Administração.
- Fluxo de aprovação, teste e liberação do equipamento.
- Cadastro de materiais, depósitos, fornecedores e documentos técnicos.

### 5.4 Migrations necessárias

As migrations serão aditivas e executadas uma por fase, sempre sobre cópia homologada antes da produção.

| Migration | Alteração proposta |
|---|---|
| M000 - Baseline | Capturar o schema real de produção, alinhar com os 24 models/tabelas atuais e iniciar versionamento Alembic |
| M001 - Famílias e locais | Criar `equipment_families` e `operational_locations`; adicionar FKs opcionais em `vehicles`; preservar `frota`, `tipo` e `local` |
| M002 - Vínculos de ativos | Criar `equipment_links` para LBS/Spreader titular/reserva com início, fim e histórico |
| M003 - Disponibilidade e horímetro | Criar `equipment_status_events` e `hourmeter_readings`; manter status atual como cache compatível |
| M004 - Inspeções e emergenciais | Criar templates/versionamento de inspeção, execuções, itens e `emergency_events` vinculados à NC/OS |
| M005 - OS e PCM | Ampliar `maintenance_work_orders`; criar planos/tarefas/execuções preventivas; reaproveitar agendas atuais |
| M006 - Materiais e biblioteca | Criar aplicação material-família, depósitos/reservas e documentos/revisões/vínculos técnicos |
| M007 - Permissões e automações | Adicionar permissões granulares, regras de automação e histórico de execução sem remover `users.tipo` |

Regras de migration:

- Não renomear nem apagar `vehicles` na primeira etapa.
- Não alterar IDs atuais.
- Não remover endpoints `/veiculos` durante a transição.
- Fazer backfill em lotes e registrar o resultado.
- Criar backup verificável antes de cada migration.
- Testar upgrade e rollback em cópia do PostgreSQL.
- Bloquear deploy se model e schema estiverem divergentes.

## 6. Ação aplicada:

Foi realizado levantamento somente leitura de arquitetura, banco local, models, constraints, rotas, APIs, serviços, telas desktop, telas web/mobile, autenticação, permissões, checklists, não conformidades, manutenção, materiais, relatórios, integrações, testes e estado do Git.

Nenhum código, banco, API, tela, autenticação, permissão ou migration foi alterado nesta etapa.

### Plano de integração por fases

| Fase | Entrega | Reaproveitamento principal | Validação de saída |
|---|---|---|---|
| 0 - Estabilização | Baseline Alembic, backup, contrato de API, segurança mínima, teste verde e API monitorada | App factory, testes e backup atuais | Migration sobe/desce em cópia; testes 100%; health estável |
| 1 - Cadastro unificado | Famílias, locais, RTG, LBS, Spreader, criticidade e vínculos | Tela Equipamentos, `Vehicle`, `/veiculos` e upload | 285 registros preservados; novo ativo cadastra e aparece desktop/mobile |
| 2 - Disponibilidade e horímetro | Painéis por berço/pátio, status histórico e leituras | Dashboard, cards mobile, auditoria e fotos | Mudança de status auditada; cálculo de disponibilidade confere manualmente |
| 3 - Checklist e inspeção | Catálogos por família, templates técnicos e execução mobile | Checklist atual, Inspeções/Activities e offline | RTG/LBS/Spreader executam modelos corretos sem afetar frota |
| 4 - Emergenciais e OS | Emergência, severidade, parada, conversão, execução, teste e liberação | NC, pacotes de resolução, manutenção, OS e PDFs | Fluxo ponta a ponta gera histórico único e restaura disponibilidade |
| 5 - PCM | Preventivas por tempo/horímetro, corretivas, agenda, capacidade e backlog | `MaintenanceSchedule`, calendário, sugestões e bloqueios | Vencimentos, backlog e geração de OS validados por cenário |
| 6 - Suprimentos e biblioteca | Aplicação por família, depósitos, reservas, documentos e revisões | Materiais, movimentações, Storage e relatórios | Consumo por OS atualiza saldo; documento correto aparece por ativo |
| 7 - Inteligência | Dashboard executivo, MTBF, MTTR, automações e relatórios gerenciais | Relatórios, auditoria, regras e componentes visuais | Indicadores reconciliados com amostra manual e automações auditadas |

Cada fase será uma entrega independente com migration, backend, desktop, web/mobile, testes, homologação, commit e push próprios.

## 7. Itens alterados:

- Criado somente este documento de levantamento e escopo.
- Nenhum arquivo funcional foi alterado.
- Nenhum dado foi criado, atualizado ou removido.

## 8. Impacto:

Impacto atual no sistema: nenhum. O documento não muda o funcionamento do desktop, web/mobile, backend ou banco.

Impacto futuro planejado: evolução aditiva do sistema atual, com uma única identificação por equipamento e uma única fonte de dados para todas as áreas.

Princípio de compatibilidade: tudo que funciona hoje continuará funcionando durante a expansão. Recursos legados somente poderão ser retirados em uma etapa futura, após homologação e autorização explícita.

## 9. Validação recomendada:

Antes da Fase 0:

1. Confirmar que o PostgreSQL de produção é a fonte oficial para desktop e web/mobile.
2. Gerar e testar restauração de backup do banco e das evidências.
3. Comparar schema local, schema de produção e models atuais.
4. Corrigir o teste de nomenclatura e executar os 64 testes com resultado verde.
5. Investigar a indisponibilidade do `/health` no Render.
6. Homologar a matriz `módulo x perfil x ação`.
7. Entregar inventário validado de RTG, LBS e Spreaders.
8. Homologar as regras de disponibilidade, MTBF, MTTR e horímetros.

Critérios obrigatórios para cada fase:

- Backup e rollback definidos.
- Migration versionada e testada.
- API compatível com clientes atuais.
- Testes unitários e de integração do módulo.
- Teste visual desktop e mobile.
- Teste ponta a ponta com perfil autorizado e não autorizado.
- Auditoria das ações críticas.
- Homologação com dados controlados, sem inventar dados de produção.
- Commit e push somente após validação da fase.

## 10. Resumo final:

É viável transformar o Checklist de Frota no Sistema de Manutenção Portuária sem criar outro sistema. A base atual já entrega aproximadamente metade da fundação necessária: arquitetura híbrida, cadastro, checklist, NC, inspeções em massa, manutenção parcial, OS básica, materiais, auditoria, relatórios, evidências e mobile.

O caminho seguro começa pela Fase 0 e pela Fase 1. Primeiro será organizada a fundação do banco; depois o cadastro atual será ampliado para receber RTG, LBS e Spreaders. Só então disponibilidade, horímetro, manutenção e indicadores serão construídos sobre dados confiáveis.

### Melhorias de Crescimento

Itens recomendados após o núcleo estar estável:

- QR Code/NFC para abrir o equipamento diretamente no mobile.
- Integração futura com PLC, telemetria ou coleta automática de horímetro.
- Lista técnica de peças por família e equipamento.
- Assinatura digital de execução, teste e liberação.
- Alertas por e-mail, Teams ou WhatsApp corporativo.
- Custos por OS, equipamento, família e centro de custo.
- Indicadores por terminal, área, berço, pátio, turno e período.
- Data warehouse/BI somente quando o volume justificar.

Modelo recomendado para o próximo Start: **ALTÍSSIMA**, porque a Fase 0 envolve banco de produção, migrations, segurança e compatibilidade entre desktop e web/mobile.

# Etapa 01 - Mapa de lacunas para evolução com SQLite

## Decisão de arquitetura

O banco principal desta evolução será o **SQLite local**. PostgreSQL, migrations de PostgreSQL e publicação em produção não fazem parte desta trilha.

O arquivo SQLite deve ficar sob responsabilidade de uma única instalação do backend. Desktop e web/mobile devem acessar o sistema pela API; não devem abrir ou copiar o arquivo `.db` diretamente enquanto o backend estiver em execução.

## Fontes comparadas

1. `Refatoração Completa do Sistema de Manutenção Portuária.docx`.
2. `Módulo de Gerenciamento de RH.docx`.
3. `Arquitetura de Navegação do Sistema.docx`.
4. Telas registradas em `desktop/ui/main_window.py`.
5. Models, rotas e documentação já presentes no repositório.

## Base já existente

| Área | Evidência no sistema | Situação |
|---|---|---|
| Operação | Dashboard, Central Operacional, disponibilidade, emergenciais e OS | Parcialmente atendida |
| Ativos | Equipamentos, checklist, inspeções e histórico | Parcialmente atendida |
| Manutenção e PCM | Manutenção, PCM, agenda, preventivas, backlog e reprogramação | Parcialmente atendida |
| Materiais e suprimentos | Materiais, recursos, compras, fornecedores e biblioteca técnica | Parcialmente atendida |
| Gestão | Relatórios, produtividade, não conformidades e auditoria | Parcialmente atendida |
| Administração | Usuários, regras, backup e logs de auditoria | Atendida como base |
| Navegação | Menu por perfil, busca de telas, favoritos e recentes | Parcialmente atendida |
| Web/mobile | Web responsiva, fila offline e API de sincronização já existem | Parcialmente atendida; requer homologação de campo |
| Backup local | Backup ZIP, restauração isolada e validador de homologação | Atendida para SQLite local |

O desktop possui atualmente 23 páginas registradas, distribuídas em cinco grupos: Operação; Manutenção e PCM; Ativos e suprimentos; Gestão e histórico; Administração.

## Lacunas confirmadas

| Prioridade | Lacuna | Situação atual | Próxima etapa responsável |
|---|---|---|---|
| P0 | Regras operacionais do SQLite | Backup existe, mas falta formalizar operação de arquivo único, concorrência e rotina de recuperação | Etapa 02 |
| P0 | Cadastro de colaboradores | Não há model, rota ou tela de RH | Etapa 03 |
| P0 | Frequência e ocorrências | Não há frequência, faltas, atrasos, atestados, férias, DSR ou folgas | Etapa 04 |
| P0 | Proteção de dados de RH | Não há permissões específicas para CPF, saúde ocupacional e documentos de colaboradores | Etapa 05 |
| P1 | Documentos e treinamentos de RH | Não há histórico funcional, certificados, vencimentos ou alertas de RH | Etapa 05 |
| P1 | Dashboards e relatórios de RH | Não há indicadores de efetivo, absenteísmo ou treinamentos | Etapa 06 |
| P1 | Navegação por registros | Há busca de telas, favoritos e recentes; faltam breadcrumbs, pesquisa global de registros e atalhos rápidos | Etapa 07 |
| P1 | Alertas contextuais | Há alertas pontuais, mas não uma central que abra diretamente o registro relacionado | Etapa 07 |
| P1 | Detalhamento operacional | Parte das abas solicitadas para equipamento, OS, compras e documentos ainda precisa ser comparada e completada sem duplicar telas | Etapa 08 |
| P2 | Mobile de RH | O mobile atual não possui frequência, faltas, atestados ou consulta de colaborador | Etapa 10 |
| P2 | Power BI com SQLite | Há exportações/Base Mestre; falta contrato de consumo somente leitura para SQLite/ODBC e homologação de indicadores | Etapa 11 |
| P2 | Homologação operacional | Faltam testes de campo, carga, concorrência, treinamento e aceite dos responsáveis | Etapa 12 |

## Itens que não serão copiados do escopo PostgreSQL

Os documentos pedem views SQL e migrations PostgreSQL. Nesta trilha, esses itens serão substituídos por:

- schema SQLite versionado e testado;
- backup ZIP e restauração isolada antes de qualquer mudança estrutural;
- consultas e exportações somente leitura para indicadores;
- conexão Power BI por exportação controlada ou driver SQLite, sem acesso direto de escrita;
- API como único ponto de acesso para desktop e mobile.

## Roteiro aprovado para SQLite

| Etapa | Entrega | Critério de aceite |
|---|---|---|
| 01 | Mapa de lacunas | Este documento, prioridades e ausência de alteração no banco |
| 02 | Fundação SQLite | Rotina segura de operação, backup, recuperação e teste de concorrência local |
| 03 | RH - cadastro | Colaborador, função, equipe, turno, foto, situação e vínculo opcional com usuário |
| 04 | RH - frequência | Presença, falta, atraso, atestado, férias, DSR, folga e auditoria |
| 05 | RH - documentos | Documentos, treinamentos, histórico funcional e acesso restrito |
| 06 | RH - gestão | Painel, alertas, relatórios e exportações permitidas |
| 07 | Navegação completa | Breadcrumbs, busca global, atalhos e alertas contextuais |
| 08 | Manutenção detalhada | Completar abas e detalhes sem criar módulos paralelos |
| 09 | PCM e programação | Capacidade, agenda, janelas, backlog e cumprimento operacional |
| 10 | Mobile local | Fluxos RH e manutenção pela API, com validação offline em campo |
| 11 | Indicadores e Power BI | Contrato somente leitura, relatórios e homologação de indicadores |
| 12 | Homologação local | Testes ponta a ponta, backup restaurado, treinamento e aceite operacional |

## Regras obrigatórias nas próximas etapas

1. Não duplicar usuários e colaboradores: um colaborador poderá ter vínculo opcional com um usuário de login.
2. Não apagar frequência, faltas ou documentos: correções devem gerar histórico e auditoria.
3. Não gravar no `.db` por compartilhamento de arquivo ou planilha; toda alteração passa pela API.
4. Não iniciar uma etapa sem backup restaurável validado.
5. Não tratar dados médicos ou CPF como informação comum: visualização e exportação serão restritas por perfil.
6. Não declarar homologação final sem teste real de usuários, dispositivos e restauração.

## Saída da Etapa 01

A base de manutenção deve ser preservada. A próxima implementação é a **Etapa 02 - Fundação SQLite**, seguida do módulo de RH. Não há mudança no banco nesta etapa.

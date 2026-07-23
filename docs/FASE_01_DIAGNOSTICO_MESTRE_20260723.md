# Fase 1 — Diagnóstico mestre e arquitetura atual

**Data:** 23/07/2026  
**Escopo:** inventário técnico, interfaces, dados, APIs, riscos e ordem segura de evolução.  
**Regra:** este documento não cria tabela, migration, usuário, perfil, dado ou tela.

## 1. Decisão de arquitetura

O projeto atual deve continuar sendo o único sistema. A evolução deve preservar o que já funciona e ocorrer por mudanças aditivas, compatíveis e reversíveis.

Arquitetura confirmada:

```text
Desktop PySide6 ─┐
                 ├─ API Flask + SQLAlchemy ─ PostgreSQL oficial
Web mobile/PWA ──┘                         └─ Alembic
                                      └───── Storage local ou Supabase
```

SQLite pode apoiar somente a preparação visual e testes unitários descartáveis da Fase 1A. Ele não é base oficial nem critério de aceite para a Fase 2.

## 2. Inventário técnico

| Área | Implementação atual | Situação |
|---|---|---|
| Backend | Flask 3, SQLAlchemy 2, Flask-Migrate e CORS | Reaproveitável |
| Banco | 49 models e 49 tabelas declaradas | Reaproveitável; requer governança de migrations |
| Migrations | 11 revisões Alembic de `20260712_0000` a `20260717_0010` | Parcial; baseline não constrói banco vazio |
| Desktop | PySide6, tema próprio, `api_client.py`, componentes e páginas | Reaproveitável |
| Mobile | Web responsivo/PWA em HTML, CSS e JavaScript | Reaproveitável; não é app nativo |
| API | 24 blueprints e 170 endpoints | Reaproveitável; precisa de contrato consolidado |
| Testes | 42 arquivos de teste | Boa base, sem cobertura PostgreSQL local confirmada |
| Deploy | Render para API/web e suporte a Supabase Storage | Integração existente; produção não foi modificada |

Entradas principais:

- `backend/run.py` e `backend/wsgi.py`: API.
- `desktop/main.py`: aplicação de gestão.
- `web_app/index.html`: aplicação de campo.
- `migrations/`: evolução de schema.
- `tools/`: backup, comparação de schema, restauração e empacotamento.

## 3. Mapa funcional atual

| Domínio | Modelos/tabelas principais | Interfaces e serviços existentes | Reaproveitamento |
|---|---|---|---|
| Identidade | `users`, `revoked_tokens`, `audit_logs` | login, usuários, alteração de senha, auditoria | Alto |
| Ativos | `vehicles`, `equipment_*`, localizações e vínculos | Equipamentos, estrutura, histórico, disponibilidade | Alto |
| Checklist | `checklists`, `checklist_items`, catálogo | Desktop e mobile para checklist e não conformidade | Alto |
| Manutenção | atividades, agendas, itens, OS, custos e execução | manutenção, emergências, central de resolução | Alto |
| PCM | `preventive_plans`, agenda e backlog derivado | tela PCM e API de preventivas | Médio/alto |
| Confiabilidade | status operacional, eventos e horímetros | disponibilidade, horímetro, inteligência | Médio; fórmulas pendentes de homologação |
| Materiais | materiais, movimentos, depósitos, estoque e reservas | materiais e biblioteca de suprimentos | Alto |
| Inspeções | templates e execuções técnicas | modelos e execução de inspeções | Alto |
| Evidências | campos de caminho e upload | fotos, documentos, storage local/Supabase | Médio; metadados estão dispersos |
| Lavagens | fila, registros, planos e bloqueios | desktop e web mobile | Alto, como módulo especializado |
| Relatórios | consultas, PDF, CSV e Excel | relatórios desktop e API | Médio; Power BI ainda não possui views oficiais |

## 4. Mapa de interfaces e navegação

### Desktop

O desktop possui navegação por `MainWindow`, componentes reutilizáveis e, entre outras, as áreas: Dashboard, Não Conformidades, Produtividade, Relatórios, Histórico de Checklist, Equipamentos, Itens de Checklist, Inspeções, Materiais, Lavagens, Atividades, Manutenção, Disponibilidade, Emergências, PCM, Suprimentos, Usuários, Backup em nuvem, Auditoria e Regras administrativas.

Há 24 arquivos de interface no diretório `desktop/ui` e 34 diálogos identificados. O tema, ícones, cartões, diálogos de confirmação, carregamento e exportação devem ser preservados como base do design system.

### Web mobile

O mobile atual é uma aplicação web responsiva, voltada ao campo. Possui login, checklist, fotos, não conformidades, manutenção, disponibilidade/horímetro, inspeção técnica, emergências/OS, biblioteca técnica e lavagens. Há fila offline no cliente; a sincronização exige validação de conflito e idempotência antes de ampliar seu uso.

### Perfis atuais

Os perfis atuais são `admin`, `gestor`, `mecanico` e `motorista`. O controle já existe no desktop e no backend, mas é amplo. A matriz futura deve ser por capacidade, tela, ação, campo sensível e exportação, sem depender apenas de ocultar botões.

## 5. Banco e migrations

O modelo atual já cobre ativos, checklist, OS, preventivas, estoque, inspeções, auditoria e operações mobile. `Vehicle` é a raiz técnica atual dos ativos e deve continuar com ID estável durante a transição.

### Estado encontrado

- A variável de PostgreSQL está configurada e o fallback local não está forçado.
- A porta local `5432` não estava escutando durante este diagnóstico; não foi feita alteração de banco.
- A migration baseline `20260712_0000` é intencionalmente vazia: ela marca bancos legados, mas não monta um PostgreSQL novo do zero.
- O startup executa `db.create_all()`, seed e `ensure_runtime_schema()`.
- `ensure_runtime_schema()` executa alterações de tabela e, para SQLite, reconstrói tabela de catálogo. Esse comportamento é incompatível com a governança desejada.

### Decisão para a Fase 2

Alembic deve se tornar a única forma de criar e alterar schema. O startup não poderá executar DDL, recriar tabela ou aplicar alterações estruturais automaticamente. Seeds devem ser explícitos, idempotentes e separados por ambiente.

## 6. APIs e integrações

Os blueprints atuais cobrem autenticação, usuários, veículos, disponibilidade, estrutura de ativos, emergências, atividades, manutenção, dashboard de manutenção, inspeções, inteligência, materiais, operações mobile, checklist, não conformidades, PCM, pacotes de resolução, suprimentos, upload, relatórios e lavagens.

Integrações identificadas:

- Render para publicação da API e web mobile.
- Supabase Storage opcional para evidências.
- Planilha Excel de inventário para importação controlada.
- PDF, CSV e Excel para relatórios.

Não foi identificada uma integração Power BI pronta no código. A Fase 10 deverá criar views PostgreSQL versionadas e aprovadas, sem ligar Power BI diretamente às tabelas operacionais.

## 7. Reaproveitamentos obrigatórios

1. Desktop PySide6, tema, componentes, ícones e diálogos atuais.
2. Web mobile existente, mantendo a API como meio de acesso ao banco.
3. Modelos de ativos, checklist, OS, materiais, inspeções e auditoria já existentes.
4. Migrations aditivas existentes como histórico técnico.
5. Testes de rotas, migrations, navegação e contratos web.
6. Relatórios, exportações e storage de evidências já implementados.

## 8. Riscos e pendências priorizados

| Prioridade | Risco | Impacto | Tratamento na fase seguinte |
|---|---|---|---|
| Crítico | PostgreSQL local indisponível na porta configurada | Não há validação real de migration e integração | Confirmar serviço, banco de desenvolvimento e banco de testes separados |
| Crítico | DDL automático no startup | Schema pode mudar sem revisão ou rollback | Remover gradualmente após baseline PostgreSQL reproduzível |
| Alto | Baseline Alembic vazio | Banco novo não é criado apenas por migrations | Criar cadeia controlada, sem tocar dados existentes |
| Alto | Fallback SQLite silencioso | Desenvolvimento pode aceitar comportamento diferente do PostgreSQL | Falhar explicitamente nos perfis oficiais |
| Alto | Perfis amplos | Ações críticas podem ficar sem granularidade | Matriz de capacidades backend-first |
| Alto | Evidências distribuídas em vários campos `*_path` | Auditoria, retenção e autorização ficam inconsistentes | Catálogo de anexo aditivo e backfill posterior |
| Médio | Lógica e commits espalhados entre rotas e serviços | Transações complexas ficam difíceis de testar | Definir fronteiras de serviço e transação por domínio |
| Médio | Versões JavaScript legadas no repositório | Aumenta ruído e risco de manutenção | Inventariar, congelar e retirar somente após homologação |
| Médio | Indicadores PCM sem homologação operacional | MTBF, MTTR e disponibilidade podem ser interpretados incorretamente | Versionar fórmulas e aprovar com PCM/Operação |

## 9. Validação executada

Sem alteração de dados ou schema:

- `tests/test_phase1_protection_tools.py`
- `tests/test_phase2_migration.py`
- `tests/test_phase3_migration.py`
- `tests/test_phase11_migration.py`

Resultado: **6 testes aprovados**.

Também permanecem aprovados no novo local os testes de navegação desktop e contrato web mobile: **23 testes e 21 subtestes**.

## 10. Critério de aceite da Fase 1

A Fase 1 está tecnicamente diagnosticada quando:

1. O documento atual é aprovado como mapa de partida.
2. O PostgreSQL de desenvolvimento e de testes estão acessíveis e separados de produção.
3. É definido se a Fase 2 começa pelo pacote de banco/configuração ou pelo contrato de permissões.
4. As decisões operacionais pendentes de fórmula, status de OS e correção de horímetro possuem responsáveis de homologação.

## 11. Proposta fechada para a Fase 2

**Objetivo:** criar uma fundação segura, sem entregar novos módulos de negócio.

Escopo permitido:

- perfis explícitos de ambiente;
- bloqueio do fallback SQLite nos ambientes oficiais;
- baseline capaz de construir PostgreSQL de desenvolvimento vazio;
- retirada progressiva do DDL automático de startup;
- comando explícito de seed;
- teste PostgreSQL de migrations, chaves estrangeiras, unicidade, datas e decimais;
- contrato inicial de capacidades e auditoria para ações críticas.

Escopo proibido nesta fase:

- apagar ou renumerar dados;
- redesenhar o desktop;
- criar tabelas duplicadas;
- migrar produção;
- implementar os módulos de Equipamentos, OS, PCM, RH ou Compras previstos para fases posteriores.

## 12. Ordem das fases seguintes

1. Diagnóstico, inventário e arquitetura — concluída neste documento.
2. Fundação técnica e PostgreSQL.
3. Design system e navegação desktop.
4. Equipamentos e central operacional.
5. OS e execução.
6. PCM, planejamento e backlog.
7. Preventivas, horímetros e falhas.
8. Materiais, estoque, compras e fornecedores.
9. RH e gestão de pessoas.
10. Dashboards, indicadores e Power BI.
11. Integração desktop, mobile, API e sincronização.
12. Segurança, testes de ponta a ponta, migração e implantação.

O detalhamento técnico das 12 fases permanece em `docs/PLANO_NOVO_SISTEMA_12_FASES_POSTGRESQL.md`; ambos os documentos usam a mesma sequência operacional.

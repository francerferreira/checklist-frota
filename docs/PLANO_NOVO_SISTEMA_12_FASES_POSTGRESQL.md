# Plano do Novo Sistema — 12 Fases com PostgreSQL

## 1. Decisão de arquitetura

O novo sistema usará PostgreSQL como banco de dados oficial em desenvolvimento,
testes, homologação e produção.

SQLite não será usado como fallback automático. Se a conexão PostgreSQL estiver
ausente ou incorreta, a aplicação deverá parar com uma mensagem clara, sem criar
outro banco silenciosamente.

SQLite poderá ser usado somente como bancada descartável na preparação inicial
da Fase 1, conforme as regras da seção 3. Ele não aprova a Fase 1 e não poderá
ser usado como persistência da Fase 2.

A arquitetura continuará separada em:

- Backend Flask responsável por regras, segurança, banco e API;
- Interface gerencial principal;
- Interface web/mobile para execução em campo;
- PostgreSQL como fonte única dos dados.

Na Fase 1 deverá ser confirmada uma única interface gerencial principal. A opção
de menor risco com a base atual é manter PySide6 para gestão e o web/mobile para
campo. Uma terceira interface web gerencial não deverá ser criada sem decisão
expressa, pois duplicaria telas, testes e manutenção.

## 2. Situação encontrada em 23/07/2026

- A variável `DATABASE_URL` está configurada para PostgreSQL local;
- O endereço configurado é `127.0.0.1:5432`;
- Não existe processo ouvindo na porta 5432;
- Não foi detectado serviço PostgreSQL, `psql`, `pg_isready` ou instalação no
  caminho padrão do Windows;
- A conexão retornou `connection refused`;
- Nenhuma alteração foi executada no PostgreSQL;
- O SQLite vazio criado durante a preparação foi removido;
- O SQLite anterior foi retirado do caminho ativo e mantido somente como backup
  local de recuperação em `backend/backups/`, pasta ignorada pelo Git.

Esse diagnóstico torna a preparação correta do PostgreSQL o primeiro bloqueio
da implementação.

## 3. Uso transitório do SQLite

O SQLite fica limitado à **Fase 1A**, uma preparação interna da Fase 1.

| Momento | Regra |
|---|---|
| Preparação inicial da Fase 1 | SQLite permitido como banco descartável |
| Aceite e conclusão da Fase 1 | PostgreSQL obrigatório |
| Fase 2 em diante | Persistência somente em PostgreSQL |
| Testes unitários rápidos | SQLite permitido quando o teste não depender do dialeto |
| Testes de integração e migrations | PostgreSQL obrigatório |

### Permitido com SQLite

- Mudança da pasta do projeto;
- Mapa mestre;
- Protótipos visuais;
- Menu, navegação e componentes usando fixtures;
- Contratos de API sem persistência definitiva;
- Regras puras;
- Testes unitários rápidos.

### Proibido consolidar em SQLite

- Login, usuários e permissões persistentes;
- Auditoria;
- Comentários e anexos persistentes;
- Migrations oficiais;
- Equipamentos, horímetros e disponibilidade;
- OS, preventivas e planejamento;
- Estoque, compras, custos e concorrência;
- Dados que precisem ser migrados para produção.

O modo SQLite deverá ser explícito, nunca automático. Seu arquivo temporário não
deverá ficar dentro do repositório ou da Área de Trabalho sincronizada pelo
OneDrive. Quando necessário, deverá usar uma pasta local descartável fora da
sincronização, por exemplo sob `%LOCALAPPDATA%`.

Todo dado criado nesse modo será considerado descartável. Antes de iniciar a
persistência da Fase 2, será obrigatório concluir os critérios PostgreSQL da
Fase 1.

## 4. Regras obrigatórias para o desenvolvimento

1. Nunca desenvolver diretamente no banco de produção.
2. Manter bancos separados para desenvolvimento, testes e homologação.
3. Usar usuários PostgreSQL diferentes por ambiente e sem privilégio de
   superusuário na aplicação.
4. Separar o usuário proprietário/migration do usuário runtime. O usuário da
   aplicação não poderá executar DDL.
5. Não executar `DROP DATABASE`, `DROP SCHEMA`, limpeza geral ou reset sem uma
   trava explícita de ambiente.
6. Toda alteração estrutural deverá ser feita por migration versionada.
7. A aplicação não deverá executar `db.create_all()` nem alterar tabelas durante
   a inicialização normal após a conclusão da Fase 1.
8. Seeds deverão ser executados por comando controlado, ser idempotentes e conter
   somente dados técnicos necessários.
9. Testes automatizados deverão usar banco exclusivo de testes.
10. Cada fase deverá funcionar ponta a ponta: banco, API, interface e testes.
11. Cada fase aprovada deverá terminar com commit e push próprios.
12. Contratos existentes só poderão ser removidos depois da migração dos
    consumidores e de um caminho de rollback.
13. Nenhuma fase seguinte começa enquanto os critérios de aceite da anterior
    estiverem pendentes.

## 5. Ambientes PostgreSQL obrigatórios

| Ambiente | Finalidade | Regra de proteção |
|---|---|---|
| Desenvolvimento | Implementação manual | Pode receber migrations e dados locais controlados |
| Testes | Testes automatizados | Exclusivo da suíte; nunca compartilhar com desenvolvimento |
| Homologação | Aceite dos usuários | Cópia controlada ou dados anonimizados |
| Produção | Operação real | Sem reset; migrations somente com backup e plano de retorno |

Antes de qualquer comando destrutivo, o processo deverá validar:

- `APP_ENV=development` ou `APP_ENV=test`;
- Driver PostgreSQL;
- Host e porta esperados;
- Nome exato do banco permitido;
- Usuário permitido;
- Ausência de indicadores de produção;
- Resultado real de `current_database()`, `current_user`, endereço e porta do
  servidor conectado;
- Backup quando existir dado relevante;
- Variável explícita de autorização para reset.

## 6. Padrão de entrega de cada fase

Cada fase deverá produzir:

- Migration PostgreSQL;
- Models e regras de domínio;
- Endpoints da API;
- Interface correspondente;
- Permissões;
- Auditoria;
- Testes unitários, de integração e de fluxo;
- Documentação curta;
- Evidência de validação;
- Commit e push.

---

# Fase 1 — Fundação PostgreSQL e mapa mestre

## Objetivo

Criar uma fundação reproduzível e segura para o novo sistema.

## Escopo

- Corrigir o PostgreSQL usado em desenvolvimento ou, mediante autorização
  explícita, instalar uma instância local;
- Confirmar a instância e criar bancos separados de desenvolvimento e testes;
- Criar usuário proprietário/migration e usuário runtime com privilégios
  mínimos e responsabilidades separadas;
- Proteger produção contra comandos de desenvolvimento;
- Disponibilizar, se necessário, o modo SQLite Fase 1A de forma explícita,
  descartável e fora do OneDrive;
- Criar o mapa mestre:
  `módulo → tela → subtela → aba → rota → perfil → model → API → reaproveitamento`;
- Definir a interface gerencial principal;
- Consolidar uma baseline de migrations capaz de construir o banco vazio;
- Remover gradualmente `db.create_all()` e alterações estruturais em runtime;
- Criar comando controlado de seed;
- Padronizar respostas e erros da API.

## Banco

- Baseline PostgreSQL versionada;
- Constraints, índices, chaves estrangeiras e convenções de nomes;
- Tabelas técnicas mínimas;
- Nenhum dado operacional inventado;
- Registro correto da revisão Alembic.

## Entregáveis

- PostgreSQL de desenvolvimento acessível;
- PostgreSQL de testes isolado;
- Modo SQLite bootstrap incapaz de ser ativado silenciosamente;
- Migration do zero até o head;
- Comando seguro de upgrade;
- Comando seguro de seed;
- `/health` validando banco e versão;
- Mapa mestre aprovado.

## Critérios de aceite

- `pg_isready` ou verificação equivalente retorna sucesso;
- Banco vazio recebe todas as migrations sem intervenção manual;
- Executar upgrade novamente não duplica estrutura nem dados;
- Testes não acessam o banco de desenvolvimento;
- Produção não é acessada;
- `/health` retorna HTTP 200;
- A inicialização não cria SQLite;
- A inicialização não altera schema automaticamente.

## Dependências

Nenhuma.

---

# Fase 2 — Navegação, identidade, permissões e componentes

## Objetivo

Criar o padrão técnico e visual usado por todos os módulos.

## Escopo funcional

- Login e encerramento de sessão;
- Usuários, perfis e permissões;
- Administração e configurações básicas;
- Menu hierárquico;
- Breadcrumbs;
- Cabeçalho;
- Atalhos;
- Estados vazio, carregando e erro;
- Componentes de tabela, filtros, formulário, modal, painel lateral e status;
- Infraestrutura genérica de comentários e anexos, sem criar a biblioteca
  documental completa;
- Auditoria base.

## Banco

- Usuários;
- Perfis;
- Permissões por módulo, tela e ação;
- Preferências;
- Parâmetros;
- Comentários genéricos;
- Metadados de anexos;
- Auditoria.

## API

- Autenticação;
- Usuários;
- Perfis;
- Permissões;
- Parâmetros;
- Auditoria;
- Catálogo de módulos e rotas disponíveis.

## Critérios de aceite

- A API e a interface aplicam a mesma permissão;
- Usuário sem acesso recebe HTTP 403;
- Menu não mostra funções proibidas;
- Ações relevantes geram auditoria;
- Comentários e anexos respeitam entidade, autor e permissão;
- Nenhuma tela implementada precisa recriar componentes básicos.

## Dependências

Fase 1.

---

# Fase 3 — Equipamentos, Central Operacional e Disponibilidade

## Objetivo

Criar a fonte única da frota e da situação operacional.

## Escopo funcional

- Equipamentos;
- Famílias;
- Localizações;
- Vínculos;
- Criticidade;
- Horímetros;
- Status operacional;
- Indisponibilidades;
- Previsões de retorno;
- Linha do tempo;
- Central Operacional de RTGs, LBS e outros equipamentos.

## Banco

- Equipamento;
- Família;
- Localização;
- Movimento de localização;
- Vínculo entre equipamentos;
- Leitura de horímetro;
- Estado operacional;
- Evento de status;
- Previsão de retorno.

## API e interfaces

- CRUD de equipamento;
- Registro de horímetro;
- Mudança de status;
- Registro de indisponibilidade;
- Atualização de previsão;
- Lista, cadastro e detalhes do equipamento;
- Cards da Central Operacional;
- Histórico e disponibilidade.

## Critérios de aceite

- Código do equipamento é único;
- Status segue transições válidas;
- Horímetro não retrocede sem correção auditada;
- Tempo parado é calculado corretamente;
- Mudanças aparecem imediatamente no card e na linha do tempo.

## Dependências

Fases 1 e 2.

---

# Fase 4 — Ordens de Serviço, Falhas e Planos de Ação

## Objetivo

Entregar o fluxo completo de manutenção corretiva.

## Escopo funcional

- Registro de falha;
- Abertura guiada da OS;
- Triagem;
- Prioridade;
- Diagnóstico;
- Planejamento inicial;
- Execução, pausas e retomadas;
- Teste;
- Liberação;
- Encerramento;
- Análise de causa;
- Reincidência e Pareto;
- 5 Porquês;
- 5W2H;
- Evidências;
- Planos de ação.

## Banco

- Falha;
- Ordem de serviço;
- Histórico de status;
- Histórico de previsão;
- Execução;
- Apontamento;
- Análise de causa;
- Plano de ação;
- Evidência;
- Comentário e anexo.

## Critérios de aceite

- Falha pode gerar uma OS sem duplicidade;
- Transições inválidas são bloqueadas;
- Encerramento exige os dados definidos;
- Liberação atualiza a disponibilidade;
- Histórico e auditoria preservam todas as mudanças;
- Plano de ação vencido é identificado.

## Dependências

Fase 3.

---

# Fase 5 — Preventivas e checklists técnicos

## Objetivo

Controlar manutenção preventiva por calendário e horímetro.

## Escopo funcional

- Planos preventivos;
- Frequências;
- Tolerâncias;
- Itens obrigatórios;
- Estimativas de necessidade de material e recurso, sem reserva nesta fase;
- Vencimentos;
- Geração de OS;
- Execução de checklist;
- Histórico;
- Próximo vencimento.
- Configurações de tolerância, frequência e geração.

## Banco

- Plano preventivo;
- Item do plano;
- Execução;
- Resposta;
- Vencimento.

## Critérios de aceite

- Cálculo funciona por data, horímetro ou ambos;
- Geração de OS é idempotente;
- Item obrigatório não pode ser ignorado;
- Próximo vencimento é calculado após conclusão;
- Execução offline sincroniza sem duplicar.

## Dependências

Fases 3 e 4.

---

# Fase 6 — Equipes, Ferramentas, Recursos e Janelas

## Objetivo

Disponibilizar pessoas e recursos para o planejamento.

## Escopo funcional

- Equipes;
- Colaboradores;
- Especialidades;
- Turnos;
- Capacidade;
- Agenda;
- Apontamentos;
- Ferramentas;
- Instrumentos;
- Calibrações;
- Reservas;
- Janelas operacionais;
- Comentários em solicitações e alterações de janelas;
- Integração de recursos e equipes com OS e preventivas.

## Banco

- Equipe;
- Colaborador;
- Especialidade;
- Turno;
- Recurso;
- Calibração;
- Reserva;
- Janela operacional;
- Aprovação e cancelamento.

## Critérios de aceite

- Não existe reserva sobreposta;
- Capacidade considera turno e especialidade;
- Recurso indisponível não pode ser alocado;
- Calibração vencida bloqueia uso quando aplicável;
- Aprovação respeita o perfil autorizado.

## Dependências

Fase 5.

---

# Fase 7 — Planejamento, Programação e Backlog

## Objetivo

Transformar demandas em programação executável.

## Escopo funcional

- Planejamento anual, mensal, semanal e diário;
- Calendário;
- Gantt;
- Kanban;
- Capacidade;
- Programação por equipamento e equipe;
- Serviços não executados;
- Reprogramações;
- Cumprimento;
- Backlog;
- Envelhecimento;
- Dependências e bloqueios genéricos;
- Configurações de PCM, faixas de backlog e regras de programação;
- Comentários de planejamento e reprogramação.

As visões específicas “aguardando material” e “aguardando terceiro” serão
ativadas respectivamente nas Fases 8 e 9, quando essas entidades existirem.

## Banco

- Atividade planejada;
- Dependência;
- Alocação;
- Programação;
- Publicação;
- Reprogramação;
- Motivo de pendência;
- Histórico.

## Critérios de aceite

- OS e preventivas entram no backlog correto;
- Capacidade impede sobrecarga não autorizada;
- Dependências são respeitadas;
- Reprogramação exige motivo e gera auditoria;
- Cumprimento confere com as atividades executadas.

## Dependências

Fase 6.

---

# Fase 8 — Materiais e Estoque

## Objetivo

Controlar o material desde a necessidade até o consumo.

## Escopo funcional

- Catálogo;
- Categorias;
- Aplicações por equipamento;
- Depósitos;
- Saldo;
- Reserva;
- Entrada;
- Saída;
- Devolução;
- Ajuste;
- Inventário;
- Estoque baixo;
- Curva ABC;
- Movimentação por OS.
- Configurações de estoque mínimo, ponto de reposição, reserva e Curva ABC;
- Comentários vinculados a materiais e inventários;
- Ativação da visão de backlog “aguardando material”.

## Banco

- Material;
- Categoria;
- Aplicação;
- Depósito;
- Saldo;
- Movimento;
- Reserva;
- Inventário.

## Regras PostgreSQL

- Movimentações dentro de transação;
- Constraints impedindo saldo negativo;
- Bloqueio de linha quando houver concorrência;
- Idempotência em integrações e sincronização;
- Valores e quantidades com tipos adequados.

## Critérios de aceite

- Reserva reduz o disponível;
- Saída reduz o saldo;
- Devolução recompõe o saldo;
- Concorrência não gera estoque negativo;
- Toda movimentação registra origem e usuário.

## Dependências

Fase 7.

---

# Fase 9 — Compras e Fornecedores

## Objetivo

Tratar a falta de material ou serviço até o recebimento.

## Escopo funcional

- Fornecedores;
- Contatos;
- Avaliações;
- Solicitação de compra;
- Cotação;
- Aprovação;
- Pedido;
- Transporte;
- Recebimento;
- Compras críticas;
- Compras atrasadas;
- Comunicação e documentos.
- Comentários vinculados a compras e fornecedores;
- Ativação da visão de backlog “aguardando terceiro”.

## Banco

- Fornecedor;
- Contato;
- Avaliação;
- Solicitação;
- Cotação;
- Aprovação;
- Pedido;
- Remessa;
- Recebimento.

## Critérios de aceite

- Falta de material pode gerar solicitação;
- Alçadas de aprovação são respeitadas;
- Recebimento parcial é permitido e auditado;
- Recebimento atualiza estoque uma única vez;
- Atrasos são calculados pelas datas reais.

## Dependências

Fase 8.

---

# Fase 10 — Custos e Documentos

## Objetivo

Consolidar impactos financeiros e evidências técnicas.

## Escopo funcional

- Custos por equipamento, família, OS, tipo, categoria e fornecedor;
- Orçado versus realizado;
- Biblioteca técnica;
- Documentos por equipamento e fornecedor;
- Revisões;
- Validades;
- Visualização e download;
- Associação com OS.

## Banco

- Lançamento de custo;
- Orçamento;
- Rateio;
- Documento;
- Revisão;
- Validade;
- Vínculos.

## Critérios de aceite

- Totais conferem com os lançamentos;
- Dinheiro usa tipo decimal, nunca ponto flutuante;
- Rateios preservam o total;
- Documento mantém versão e histórico;
- Download respeita permissão;
- Documento vencido é identificado.

## Dependências

Fases 6 e 9.

---

# Fase 11 — Início, Dashboards, Relatórios e experiência global

## Objetivo

Transformar os registros operacionais em informação útil.

## Escopo funcional

- Visão Geral;
- Minhas Atividades;
- Alertas;
- Agenda;
- Dashboards;
- Modo TV;
- Relatórios;
- Pesquisa global;
- Favoritos;
- Recentes;
- Notificações contextuais;
- Exportações.
- Configurações de indicadores e notificações.

## Banco

- Preferências de dashboard;
- Favoritos;
- Registros recentes;
- Notificações;
- Relatórios salvos;
- Agendamentos.

## Regras PostgreSQL

- Índices definidos por evidência de consulta;
- Paginação feita no banco;
- Pesquisa sempre filtrada pela permissão;
- Views ou materialized views somente após medição;
- Consultas pesadas verificadas com `EXPLAIN ANALYZE`.

## Critérios de aceite

- Indicadores conferem com os registros de origem;
- Pesquisa não revela informação proibida;
- Notificação abre o registro correto;
- Exportação respeita filtros;
- Dashboard atende a meta de tempo definida na fase.

## Dependências

Fase 10.

---

# Fase 12 — Integração, segurança, desempenho e homologação

## Objetivo

Preparar o sistema completo para entrada controlada em operação.

## Escopo

- Fluxos ponta a ponta;
- Offline mobile;
- Responsividade;
- Acessibilidade;
- Segurança;
- Desempenho;
- Observabilidade;
- Backup e restauração;
- Plano de migração ou início sem legado;
- Homologação;
- Preparação de go-live e rollback.

O go-live e qualquer alteração em produção dependerão de autorização explícita
do usuário após a homologação.

## Validações obrigatórias

- Provisionamento de um banco PostgreSQL vazio até o head;
- Backup restaurado em banco separado;
- Testes E2E de corretiva, preventiva, PCM, materiais e compras;
- Testes de permissão;
- Testes de concorrência do estoque;
- Testes de carga nas consultas críticas;
- Verificação de logs sem segredos;
- Testes do web/mobile online e offline;
- Comparação dos indicadores com consultas independentes;
- Homologação pelos responsáveis.

## Critérios de aceite

- Todas as migrations passam do zero;
- Backup e restauração funcionam;
- Não existe defeito bloqueador;
- Fluxos críticos passam integralmente;
- Produção possui plano de retorno;
- Usuários responsáveis homologam;
- Release recebe tag, commit e push finais.

## Dependências

Fase 11.

---

## 7. Mapa de cobertura dos 24 módulos

| Módulo solicitado | Fase |
|---|---:|
| Início | 11 |
| Central Operacional | 3 |
| Equipamentos | 3 |
| Ordens de Serviço | 4 |
| Planejamento | 7 |
| Programação | 7 |
| Preventivas | 5 |
| Backlog | 7 |
| Disponibilidade | 3 |
| Falhas | 4 |
| Materiais | 8 |
| Estoque | 8 |
| Compras | 9 |
| Fornecedores | 9 |
| Custos | 10 |
| Equipes | 6 |
| Ferramentas e Recursos | 6 |
| Janelas Operacionais | 6 |
| Planos de Ação | 4 |
| Documentos | 10 |
| Dashboards | 11 |
| Relatórios | 11 |
| Administração | 2 |
| Configurações | 2, 5, 7, 8 e 11 |

## 8. Ordem de execução aprovada

```text
Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6
       → Fase 7 → Fase 8 → Fase 9 → Fase 10 → Fase 11 → Fase 12
```

O primeiro código do novo sistema deverá começar somente na Fase 1, resolvendo
o PostgreSQL de desenvolvimento e tornando as migrations a fonte única do
schema.

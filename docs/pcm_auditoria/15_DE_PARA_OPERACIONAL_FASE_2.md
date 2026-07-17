# De-para operacional para homologacao - Fase 2

Data: 17/07/2026

Status: **PENDENTE DE ASSINATURA OPERACIONAL**.

Este documento separa o que ja foi confirmado do que ainda depende de PCM, Manutencao, Operacao, TI ou Seguranca. Uma linha `PENDENTE` nao autoriza migration nem mudanca de regra.

## Decisoes de arquitetura e operacao

| ID | Tema | Como funciona hoje | Arquitetura-alvo | Responsavel pelo aceite | Status |
|---|---|---|---|---|---|
| D-01 | Produto | Checklist de Frota com modulos integrados | evoluir o mesmo sistema, sem criar produto paralelo | Patrocinador | CONFIRMADA |
| D-02 | Canais | Desktop e Web Mobile usam a API | Desktop para gestao/PCM e Mobile para operacao | Patrocinador | CONFIRMADA |
| D-03 | Ativo | `Vehicle` com `EquipmentProfile` | `Vehicle.id` sera a raiz tecnica de todo equipamento | TI | CONFIRMADA TECNICAMENTE |
| D-04 | Familia | `Vehicle.tipo` + `EquipmentFamily` | familia relacional oficial; `tipo` como compatibilidade | TI + PCM | CONFIRMADA TECNICAMENTE |
| D-05 | Local | local atual sem movimento historico | hierarquia Terminal/Area/Pier/Berco/Patio e movimentos temporais | Operacao | PENDENTE |
| D-06 | LBS-Spreader | vinculo temporal existente | LBS pai, Spreader filho, um vinculo ativo por Spreader | Operacao + Manutencao | PENDENTE |
| D-07 | Numero de OS | `OS-000000` | `order_number` sera o unico identificador oficial | Patrocinador + PCM | CONFIRMADA |
| D-08 | MTR/TRM | nao faz parte do fluxo oficial | nao criar MTR ou TRM | Patrocinador | CONFIRMADA |
| D-09 | Origem x tipo | origem esta misturada com programacao | origem, tipo e modo de execucao separados conforme ADR-002 | PCM | PENDENTE |
| D-10 | Falha oficial | qualquer execucao emergencial pode entrar no KPI | somente evento classificado `counts_as_failure` | Manutencao + PCM | PENDENTE |
| D-11 | Inicio/fim MTTR | calculo atual usa inicio do reparo ate liberacao | manter essa proposta ou aprovar outro par de fatos | Manutencao + PCM | PENDENTE |
| D-12 | Inicio/fim MTBF | calculo atual usa intervalo de calendario | usar horimetro entre liberacao anterior e proxima falha | Manutencao + PCM | PENDENTE |
| D-13 | Disponibilidade | `DISPONIVEL` e `RESTRICAO` contam como disponiveis | confirmar universo, exclusoes e tratamento de restricao | Operacao + PCM | PENDENTE |
| D-14 | Parada | evento de status pode nascer manual ou automatico | periodo de status sera fonte da indisponibilidade | Operacao + Manutencao | PENDENTE |
| D-15 | Horimetro | leitura crescente sem correcao formal | original imutavel, correcao referenciada e aprovada | Operacao + PCM | PENDENTE |
| D-16 | Frequencia | registro sob demanda | definir frequencia por familia e turno | Operacao + PCM | PENDENTE |
| D-17 | Ciclo 500-6000 h | plano usa intervalo simples | passos versionados por familia | Manutencao + PCM | PENDENTE |
| D-18 | Depois de 6.000 h | nao definido | escolher reinicio, continuidade ou outra regra | Manutencao + PCM | PENDENTE CRITICA |
| D-19 | Gatilho `AMBOS` | data ou horimetro podem vencer o plano | proposta: vencer no primeiro limite atingido | Manutencao + PCM | PENDENTE |
| D-20 | OS e backlog | status da OS espelha item da agenda | state machine da ADR-006 e backlog pelas OS nao terminais | PCM | PENDENTE |
| D-21 | Reabertura | nao existe fluxo oficial | permitir com motivo e autorizacao, gerando evento | PCM + Auditoria | PENDENTE |
| D-22 | Cumprimento preventivo | sem formula oficial | concluidas no limite / vencidas no periodo | PCM | PENDENTE |
| D-23 | Permissoes | `admin`, `gestor`, `mecanico`, `motorista` | capacidades por perfil com de-para legado | Gestao + Seguranca | PENDENTE |
| D-24 | Anexos | caminhos espalhados nos models | catalogo imutavel de arquivo + vinculos por entidade | TI + Auditoria | CONFIRMADA TECNICAMENTE |
| D-25 | Inventario Spreader | planilha possui 27 series; imagem informa 25 | definir total oficial e codigo dos 8 sem identificador | Operacao + Patrimonio | PENDENTE CRITICA |

## Matriz proposta de permissoes

Legenda: `P` = permitido na proposta; `-` = nao permitido. Esta matriz ainda nao esta ativa.

| Acao | Admin | Supervisor | PCM | Tecnico | Operacao | Administrativo | Consulta |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Consultar ativo e historico | P | P | P | P | P | P | P |
| Editar cadastro mestre | P | P | P | - | - | - | - |
| Mover local/vincular Spreader | P | P | P | - | - | - | - |
| Registrar status operacional | P | P | P | P | P | - | - |
| Registrar horimetro | P | P | P | P | P | - | - |
| Solicitar correcao de horimetro | P | P | P | P | P | - | - |
| Aprovar correcao de horimetro | P | P | P | - | - | - | - |
| Abrir emergencia | P | P | P | P | P | - | - |
| Triar e direcionar emergencia | P | P | P | - | - | - | - |
| Abrir/classificar OS | P | P | P | - | - | - | - |
| Programar/priorizar OS | P | P | P | - | - | - | - |
| Executar OS direcionada | P | P | P | P | - | - | - |
| Registrar teste | P | P | P | P | - | - | - |
| Liberar equipamento | P | P | P | - | - | - | - |
| Cancelar/reabrir OS | P | P | P | - | - | - | - |
| Gerenciar planos preventivos | P | P | P | - | - | - | - |
| Consultar agenda/backlog | P | P | P | P | - | P | P |
| Reservar/ajustar estoque | P | - | P | - | - | P | - |
| Consumir material pela OS | P | P | P | P | - | P | - |
| Consultar/exportar relatorios | P | P | P | - | - | P | P |
| Consultar auditoria sensivel | P | P | - | - | - | - | - |
| Administrar usuarios/permissoes | P | - | - | - | - | - | - |
| Executar importacao homologada | P | - | P | - | - | - | - |
| Aprovar lote de importacao | P | P | - | - | - | - | - |

Regras obrigatorias da matriz:

1. O aprovador de correcao de horimetro nao pode ser o solicitante.
2. Tecnico somente executa OS direcionada a ele ou a equipe autorizada.
3. Registro de teste por Tecnico nao equivale a liberacao do ativo.
4. Importacao exige separacao entre executor e aprovador.
5. Botoes do cliente nao substituem validacao no backend.
6. Negacao de acao critica deve ser auditada quando houver tentativa autenticada.

## De-para dos perfis atuais

| Perfil atual | Capacidades temporarias | Perfil-alvo proposto | Risco da transicao |
|---|---|---|---|
| `admin` | acesso total | Administrador | baixo, manter como superusuario auditado |
| `gestor` | gestao ampla | Supervisor + PCM temporariamente | alto, precisa separar aprovacao e execucao |
| `mecanico` | area mecanica e resolucao | Tecnico | medio, limitar por OS/equipe direcionada |
| `motorista` | operacao/checklist | Operacao | medio, definir status e horimetro permitidos |
| inexistente | sem equivalente | Administrativo | pendente de criacao |
| inexistente | sem equivalente | Consulta | pendente de criacao |

## Homologacao de formulas

| Formula | Proposta | Amostra obrigatoria | Aceite |
|---|---|---|---|
| Disponibilidade | `(DISPONIVEL + RESTRICAO) / periodo coberto` | ao menos 3 ativos e um periodo com troca de status | PENDENTE |
| MTTR | media de `released_at - repair_started_at` | ao menos 5 falhas classificadas | PENDENTE |
| MTBF | horas de horimetro entre falhas qualificadas | ao menos 2 intervalos por ativo | PENDENTE |
| Cumprimento preventiva | concluidas no limite / vencidas | um ciclo com pontual, atrasada e nao executada | PENDENTE |
| Idade do backlog | hoje - abertura da OS | cinco faixas de idade | PENDENTE |

## Assinaturas necessarias

| Area | Responsavel | Decisoes | Data | Aceite |
|---|---|---|---|---|
| Patrocinador | a definir | D-01, D-02, D-07, D-08 | - | PENDENTE |
| Operacao | a definir | D-05, D-06, D-13, D-14, D-16, D-25 | - | PENDENTE |
| Manutencao | a definir | D-06, D-10 a D-19 | - | PENDENTE |
| PCM | a definir | D-04, D-09 a D-23 | - | PENDENTE |
| Seguranca/Auditoria | a definir | D-21, D-23, D-24 | - | PENDENTE |
| TI | a definir | aderencia aos ADRs e viabilidade de rollback | - | CONCLUIDA TECNICAMENTE |

## Gate de saida

O pacote tecnico da Fase 2 esta pronto, mas o gate `de-para operacional assinado` permanece **NO-GO**. A Fase 3 nao pode aplicar migrations nem ativar novas regras enquanto as decisoes criticas D-10 a D-23 e D-25 estiverem pendentes e o PostgreSQL de producao nao tiver sido comparado em modo read-only.

# Etapa 04 - RH: frequência e ocorrências

## Entrega aplicada

- Criada a tabela `employee_attendance_records` no SQLite local.
- Criada a tela **Frequência e ocorrências** para admin e gestor.
- Cada colaborador possui no máximo um lançamento por dia.
- Não existem rotas de exclusão física para esses lançamentos.

## Tipos de ocorrência

- Presente;
- Falta;
- Atraso;
- Atestado;
- Férias;
- DSR;
- Folga;
- Curso;
- Afastado;
- Serviço externo.

## Regras operacionais

- Atraso calcula automaticamente os minutos entre horário previsto e chegada.
- Atestado, férias e afastamento podem registrar um período e gerar um lançamento por dia.
- Correção exige motivo e não pode trocar o colaborador ou a data original.
- Cancelamento exige motivo, altera somente o status para `CANCELADO` e preserva o lançamento.
- O upload de documento usa a estrutura de arquivos já existente.
- Criações, correções e cancelamentos passam pelos hooks de auditoria já instalados.

## Rotas

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/rh/frequencia` | Listar lançamentos por colaborador, data ou tipo |
| POST | `/rh/frequencia` | Criar lançamento diário ou período permitido |
| PUT | `/rh/frequencia/<id>` | Corrigir lançamento com motivo obrigatório |
| POST | `/rh/frequencia/<id>/cancelar` | Cancelar sem apagar o histórico |

## Validação

- 6 testes de RH aprovados: cadastro, vínculo, atraso, período de atestado, correção, cancelamento e permissão.
- Regressão da navegação desktop aprovada.
- SQLite local confirmou a tabela de frequência e total de 57 tabelas.

## Limite desta etapa

CPF, saúde ocupacional, documentos funcionais, treinamentos e dashboards de RH continuam fora desta entrega para evitar expor dados sensíveis antes da regra de permissões específica.

## Próxima etapa

Etapa 05 - RH: documentos, treinamentos, histórico funcional e proteção de dados sensíveis.

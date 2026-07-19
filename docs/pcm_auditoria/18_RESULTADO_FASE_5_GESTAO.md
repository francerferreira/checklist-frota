# Resultado da Fase 5 - Gestao

Data: 19/07/2026

## Status

Entrega tecnica concluida para a Base Mestre e seus formatos de exportacao. A homologacao manual de indicadores e o consumo real pelo Power BI permanecem pendentes.

## Entregas realizadas

- `GET /relatorios/base-mestre` consolidando uma linha por `MaintenanceScheduleItem`.
- Filtros por familia, equipamento, local, status, origem, busca, periodo e ativos.
- Paginacao deterministica com total, paginas e flags de navegacao.
- Identificador estavel `INTERVENCAO-00000000` baseado no item de intervencao.
- `GET /relatorios/base-mestre/exportar?formato=json|csv|xlsx`.
- Contrato versionado `pcm.base_mestre.v1`.
- Exportacao limitada a 5.000 registros por requisicao, com indicador `truncated`.
- Auditoria do evento de exportacao em `AuditLog`.

## Fonte dos dados

| Campo | Fonte real |
|---|---|
| Intervencao | `maintenance_schedule_items.id` |
| Ordem de servico | `maintenance_work_orders` quando vinculada |
| Equipamento | `vehicles` |
| Familia | `equipment_profiles` e `equipment_families` |
| Local | `operational_locations` pelo perfil do equipamento |
| Estado/horimetro | `equipment_operational_states` |

O endpoint e somente leitura para os dados operacionais. A exportacao registra apenas o evento de auditoria; nao altera OS, horimetro, preventiva ou cadastro.

## Validacao tecnica

- Teste de contrato, paginacao, filtros e permissao: 3 aprovados.
- Exportacao CSV validada com cabecalho e dado do equipamento.
- Exportacao XLSX validada como arquivo Office valido.
- Testes do incremento 3A e migration: 5 aprovados.
- PostgreSQL de producao: nao acessado e nao alterado.

## Pendencias de gestao

- Reconciliar MTBF, MTTR, disponibilidade e cumprimento com amostra manual aprovada.
- Homologar consumo no Power BI com credencial somente leitura e sem acesso direto ao banco.
- Criar graficos adicionais somente depois do aceite das formulas.
- Integrar a consulta a uma tela Desktop dedicada, caso a homologacao de UX confirme necessidade; o contrato ja esta disponivel para reuso.

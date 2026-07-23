# Fase 6 - Recursos, calibração e reservas

## Entrega aplicada

- Criado o cadastro de recursos para ferramentas, instrumentos e equipamentos de apoio.
- Criada a reserva por intervalo de data e hora, opcionalmente vinculada a uma OS.
- Bloqueada a sobreposição de reservas do mesmo recurso.
- Bloqueado o uso de recurso inativo ou com calibração vencida.
- Adicionada a tela desktop **Recursos e ferramentas** para cadastro e reserva.

## Banco SQLite local

Foram adicionadas as tabelas `maintenance_resources` e `maintenance_resource_reservations`.

O banco local passou de 49 para 51 tabelas. Nenhum dado externo foi importado ou removido.

## Limites preservados

- Gestão de recursos é restrita a `admin` e `gestor`.
- Mecânico não pode criar, reservar ou cancelar recursos pela API.
- A reserva cancelada libera o mesmo intervalo para uma nova reserva.

## Validação

Executado `python -m pytest tests/test_resource_routes.py tests/test_pcm_page.py -q`.

Resultado: 4 testes aprovados.

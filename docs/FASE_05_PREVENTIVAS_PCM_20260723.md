# Fase 5 - Preventivas e PCM

## Entrega aplicada

- A tela de criação de plano preventivo passou a expor descrição, tolerância por data, tolerância por horímetro e duração estimada.
- Os campos de calendário e horímetro agora são habilitados somente quando compatíveis com o gatilho selecionado.
- O payload enviado ao backend contém apenas os parâmetros válidos para o tipo de plano escolhido.
- A suíte PCM foi isolada do ambiente de desenvolvimento: os testes usam SQLite descartável e criam seu próprio administrador de teste.

## Regras já preservadas

- Planos por calendário, horímetro ou ambos.
- Geração idempotente de programação e OS preventiva.
- Avanço do próximo vencimento após a conclusão da preventiva.
- Controle de prioridade, duração estimada e responsável técnico.

## Banco

Nenhuma tabela adicional foi necessária nesta entrega. A estrutura SQLite local já contém os campos de tolerância, frequência, descrição e duração estimada do plano preventivo.

## Validação

Executado `python -m pytest tests/test_pcm_page.py tests/test_pcm_routes.py -q`.

Resultado: 4 testes aprovados. Foram emitidos 2 avisos legados de `Query.get()` do SQLAlchemy, sem falhas.

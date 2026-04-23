# Fase 6 - Performance Visual e Microinteracoes (Desktop)

Data: 2026-04-23
Status: concluida

## Objetivo
Melhorar desempenho de renderizacao e fluidez visual mantendo microinteracoes discretas, sem alterar logica de negocio.

## Melhorias aplicadas
- `LoadingOverlay` mais leve:
  - reducao de opacidade de fundo
  - remocao de sombra pesada no card
  - simplificacao visual do orb (sem gradiente pesado)
  - fade-in/fade-out mais curtos (90ms/80ms)
  - pulso textual com menor frequencia (`320ms`)

- `TableSkeletonOverlay` otimizado:
  - remoção de shimmer continuo (sem loop de animacao)
  - fade curto para entrada/saida (90ms/80ms)
  - visual estatico de carregamento com baixo custo

- `MainWindow` com transicoes leves:
  - animacao de troca de tela curta (`90ms`)
  - opacidade inicial suave (`0.88 -> 1.0`)
  - sem animar quando a pagina ativa nao muda
  - desligamento do estado loading antecipado (timers reduzidos)

## Arquivos alterados
- `desktop/components/loading_overlay.py`
- `desktop/components/table_skeleton.py`
- `desktop/ui/main_window.py`

## Garantias preservadas
- Sem alteracao de banco de dados.
- Sem alteracao de regras de negocio.
- Sem alteracao de modulos e integracoes.
- Navegacao funcional mantida.

## Validacao
- `python -m pytest -q tests/test_desktop_navigation.py tests/test_severity_service.py`
- Resultado: `8 passed`

Observacao:
- `py_compile` falhou por permissao de escrita em `__pycache__` no ambiente OneDrive (`WinError 5`), sem impacto na validacao funcional dos testes.


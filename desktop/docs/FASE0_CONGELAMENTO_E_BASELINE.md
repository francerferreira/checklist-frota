# Fase 0 - Congelamento e Baseline (Desktop)

Data: 2026-04-23
Projeto: Sistema de Checklist de Frota (Desktop)

## 1) Objetivo da Fase 0
Estabelecer uma linha de seguranca antes da modernizacao visual, sem alterar regras de negocio, banco, modulos ou integracoes.

## 2) Premissas congeladas (obrigatorias)
- Nao alterar banco de dados (schema, tabelas, migracoes, rotinas de carga).
- Nao alterar regras de negocio (fluxos, validacoes funcionais, calculos e estados).
- Nao alterar modulos existentes.
- Nao alterar atalhos atuais.
- Nao alterar navegacao funcional atual.
- Nao alterar contratos de API e integracoes.
- Modernizacao restrita a camada visual desktop (tema, componentes, estilo, icones, layout visual).

## 3) Escopo visual permitido
- Tela principal MDI.
- Menu superior.
- TreeView lateral.
- Formularios secundarios.
- Tabelas e grids.
- Botoes.
- Campos de texto.
- Combobox.
- Checkboxes.
- Abas.
- Alertas.
- Graficos.
- Dashboard inicial.
- Icones.
- Tema geral.

## 4) Fora de escopo (Fase 0 e fases visuais)
- Criacao de novos modulos funcionais.
- Alteracao de endpoints backend.
- Alteracao de consultas SQL e estrutura de persistencia.
- Mudanca de permissao, perfil ou seguranca funcional.
- Mudanca de integracoes externas.

## 5) Baseline visual exigido
Antes de qualquer ajuste amplo de estilo, devemos registrar capturas PRE com:
- Shell principal desktop.
- Dashboard.
- Cada tela principal de modulo.
- Dialogos/formularios secundarios representativos.
- Grids e tabelas com dados.
- Calendarios/quadros de programacao (lavagem/manutencao).

Referencias:
- Inventario de capturas: `desktop/baseline_visual/fase0/BASELINE_INVENTARIO.md`
- Pasta PRE: `desktop/baseline_visual/fase0/pre`
- Pasta POST: `desktop/baseline_visual/fase0/post`

## 6) Gate de saida da Fase 0
A Fase 0 so fecha quando:
- Premissas congeladas estiverem aprovadas.
- Inventario PRE estiver preenchido com capturas.
- Checklist de regressao funcional estiver criado e validado.

Checklist de regressao:
- `desktop/docs/FASE0_CHECKLIST_REGRESSAO_FUNCIONAL.md`


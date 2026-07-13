# Homologacao do Inventario Portuario - Fase 1

Data da verificacao: 12/07/2026

## Fontes verificadas

- `SPREADERS.xlsx`
- `CONTROLE_RTG_ALFANDEGADO_MASTER.xlsx`
- `ACOMPANHAMENTO_REUNIAO_RTG_ALFANDEGADO_DASHBOARD_TOP.xlsx`
- `ACOMPANHAMENTO_REUNIAO_RTG_ATR_DASHBOARD_TOP.xlsx`
- Imagens de disponibilidade e distribuicao enviadas no escopo

## Resultado

Status: **PARCIALMENTE HOMOLOGADO - IMPORTACAO AUTOMATICA BLOQUEADA**.

| Familia | Registros identificados | Resultado |
|---|---:|---|
| RTG | 22 codigos unicos | 12 Alfandegado e 10 ATR; faltam serie, fabricante e ano na fonte consolidada |
| LBS | 16 equipamentos | As 16 abas individuais possuem numero de serie; a visao consolidada usa celulas mescladas e repete codigos na leitura tabular |
| Spreader | 19 codigos e 19 series unicas | A planilha atual lista 19, mas a imagem anterior informa total 25 |

## Validacoes realizadas

- Os 22 codigos de RTG sao unicos, de `RTG 01` a `RTG 22`.
- A planilha de RTG registra 17 disponiveis e 5 indisponiveis no recorte analisado.
- As 16 abas de LBS identificam `LBS 01` a `LBS 16` com series individuais.
- Os 19 Spreaders da planilha possuem codigo e serie sem duplicidade.
- Os 19 vinculos de localizacao dos Spreaders apontam para codigos de LBS reconheciveis.
- A planilha registra 13 Spreaders disponiveis e 6 indisponiveis.

## Pendencias para liberacao da importacao

1. Definir se a fonte oficial de Spreaders possui 19 ou 25 equipamentos.
2. Entregar os seis registros ausentes, caso o total oficial seja 25.
3. Confirmar serie, fabricante, modelo e ano dos 22 RTGs.
4. Confirmar o berco/local oficial de cada LBS, sem depender de celulas mescladas.
5. Definir se `SPREADER`, `RESERVA` e `RESERVA ITA` sao familias ou papeis de vinculo.
6. Aprovar uma planilha mestre unica com identificacao, familia, serie, ano, local e status cadastral.

## Decisao aplicada

Nenhum RTG, LBS ou Spreader foi importado para o banco. A Fase 1 entrega a estrutura para receber esses ativos, mas a carga real permanece bloqueada ate a resolucao das pendencias acima.

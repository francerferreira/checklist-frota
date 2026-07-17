# Homologacao do Inventario Portuario - Fase 1

Data da verificacao original: 12/07/2026

Revalidacao tecnica: 17/07/2026

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
| Spreader | 27 series unicas | 19 possuem codigo; 8 estao sem codigo e aguardando ativacao; a imagem anterior informa total 25 |

## Validacoes realizadas

- Os 22 codigos de RTG sao unicos, de `RTG 01` a `RTG 22`.
- A planilha de RTG registra 17 disponiveis e 5 indisponiveis no recorte analisado.
- As 16 abas de LBS identificam `LBS 01` a `LBS 16` com series individuais.
- Os 19 Spreaders codificados possuem codigo e serie sem duplicidade.
- Existem mais 8 registros com serie, ano e local, mas sem codigo de equipamento e marcados como `AGUARDANDO ATIVACAO`.
- As 27 linhas possuem series distintas.
- Os 19 Spreaders codificados possuem localizacoes reconheciveis; parte esta acoplada a LBS e parte esta em base operacional.
- Entre os 19 codificados, a planilha registra 13 disponiveis e 6 indisponiveis.

## Pendencias para liberacao da importacao

1. Definir se a fonte oficial possui 25 ou 27 Spreaders.
2. Atribuir codigo oficial aos 8 registros que possuem serie, mas aparecem apenas como `SPREADER`.
3. Explicar a diferenca entre a imagem historica com total 25 e a planilha atual com 27 series.
4. Confirmar serie, fabricante, modelo e ano dos 22 RTGs.
5. Confirmar o berco/local oficial de cada LBS, sem depender de celulas mescladas.
6. Definir se `SPREADER`, `RESERVA` e `RESERVA ITA` sao familias ou papeis de vinculo.
7. Aprovar uma planilha mestre unica com identificacao, familia, serie, ano, local e status cadastral.

## Decisao aplicada

Nenhum RTG, LBS ou Spreader foi importado para o banco. A Fase 1 entrega a estrutura para receber esses ativos, mas a carga real permanece bloqueada ate a resolucao das pendencias acima.

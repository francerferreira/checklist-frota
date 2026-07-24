# Etapa 08 - Detalhamento operacional nas telas existentes (SQLite)

## Entrega

Esta etapa completa a leitura operacional sem criar um segundo cadastro para o mesmo assunto.

- **Equipamentos:** a ficha individual passou a reunir resumo, historico operacional, status, horimetro, documentos tecnicos e vinculos.
- **Compras:** a solicitacao selecionada abre uma ficha com material, fornecedor, prioridade, aprovacao, saldo e todos os recebimentos.
- **Manutencao:** a tela existente continua como ponto unico para planejamento, servicos, OS, responsaveis, pecas, custos e PDF de OS; nenhum fluxo paralelo foi criado.

## Navegacao

Na tela de Equipamentos, abra a ficha pelo duplo clique. Em Compras e fornecedores, selecione a solicitacao e use **Ver detalhes**, ou de duplo clique na linha.

## Regras preservadas

- informacoes apresentadas sao somente leitura nas fichas;
- alteracoes continuam usando os fluxos ja auditados de equipamento, compra, recebimento e manutencao;
- recebimentos permanecem idempotentes e nao repetem saldo;
- nao foi criada tabela, migration ou banco paralelo.

## Validacao prevista

- ficha de compra retorna criador, aprovador e recebimentos;
- recebimento parcial/final e saldo continuam consistentes;
- ficha do equipamento consulta somente APIs ja existentes e tolera ausencia de historico ou documento.

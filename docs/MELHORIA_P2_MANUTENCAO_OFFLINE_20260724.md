# P2 — Atualização de manutenção offline

## Entrega

O mecânico pode registrar pelo celular a instalação ou a não execução de um item de manutenção mesmo sem conexão. O lançamento é guardado no aparelho e sincronizado quando a rede voltar.

## Proteções

- Cada lançamento tem identificador único: reenviar o mesmo lançamento não repete a baixa de material nem altera o item duas vezes.
- O servidor valida que o mecânico está vinculado ao item ou à programação.
- O canal móvel aceita somente `INSTALADO` e `NAO_EXECUTADO`.
- Reprogramação de data continua restrita à gestão e não é enviada pela fila móvel.
- Itens aguardando sincronização ficam bloqueados na tela para evitar lançamento duplicado.

## Limite deste corte

Esta entrega não inclui assinatura eletrônica, cálculo de capacidade por turno nem publicação automática no Power BI. Esses são cortes independentes do P2 e devem ser implantados e validados separadamente.

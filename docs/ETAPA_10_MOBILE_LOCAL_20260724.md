# Etapa 10 - Mobile local: RH e manutenção

## Entrega

A PWA existente recebeu a tela **Minha jornada**. Ela consulta somente os dados do colaborador associado ao login autenticado:

- identificação funcional, equipe e turno;
- últimos registros de frequência;
- treinamentos vencidos ou vencendo nos próximos 30 dias.

A consulta usa `GET /operacao-mobile/minha-jornada`. O endpoint não retorna anotações, documentos, certificados nem dados de outros colaboradores.

## Funcionamento offline

As últimas consultas válidas de **Minha jornada** e da agenda de **Manutenção** ficam no navegador. Quando não houver rede, a PWA exibe essa cópia como consulta, com aviso claro de que ela pode não ser a mais recente.

Lançamentos de manutenção continuam exigindo conexão e o fluxo atual autorizado. A etapa não cria apontamentos de RH pelo celular, não cria dados fictícios e não acessa o arquivo SQLite diretamente.

## Banco e segurança

Não houve nova tabela, migration ou alteração no SQLite. Desktop e PWA continuam usando a API como porta única do banco. Se o login não estiver vinculado a um colaborador, a consulta retorna uma mensagem de orientação sem expor registros de RH.

## Validação executada

- contrato da PWA mobile;
- rota de operações mobile, incluindo projeção individual de RH;
- navegação desktop como regressão;
- validador local do SQLite com backup e restauração.

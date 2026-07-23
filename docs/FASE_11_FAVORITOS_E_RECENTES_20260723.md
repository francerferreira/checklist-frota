# Fase 11 - Favoritos e recentes

## Entrega aplicada

- Cada usuário pode marcar as telas permitidas como favoritas.
- O sistema registra as últimas seis telas acessadas por usuário.
- A navegação desktop mostra as seções dinâmicas **Favoritos** e **Recentes**.
- O botão da barra inferior permite favoritar ou desfavoritar a tela aberta.

## Segurança preservada

- Um perfil só pode salvar ou acessar atalhos para telas liberadas a ele.
- A API devolve erro 403 quando um perfil tenta gravar uma tela não autorizada.
- Preferências são isoladas por usuário.

## Banco SQLite local

- Criada a tabela `user_navigation_preferences`.
- Banco local validado com 55 tabelas.

## Validação

- Testado o registro de recente, favorito e bloqueio de perfil sem permissão.
- Testada a troca de tela no desktop sem atualização indevida de páginas.

# Etapa 07 - Navegacao completa e alertas contextuais (SQLite)

## Entrega

Foram adicionados recursos de navegacao para reduzir o tempo entre identificar uma pendencia e chegar ao local correto para tratativa:

- breadcrumb no rodape: `Inicio > Area > Tela`;
- busca global por `Ctrl+K`;
- abertura direta de resultado para a tela e registro correspondente;
- duplo clique em alerta automatico do dashboard para abrir seu contexto;
- atalhos existentes preservados: `F9` para ocultar ou mostrar navegacao.

## Busca global e permissoes

A busca consulta telas e, quando o perfil possui acesso, equipamentos, materiais, colaboradores e alertas automaticos. Cada resultado ja traz a tela de destino permitida. Motorista continua limitado ao dashboard e nao recebe resultados de cadastro, estoque ou RH.

## Alertas contextuais

Alertas automaticos de estoque abrem Materiais; preventivas vencidas abrem PCM; emergenciais abrem a tela de Emergenciais e OS. Para equipamento, material e colaborador, a tela de destino recebe o identificador e seleciona o registro localizado.

## Limites de seguranca

Busca exige pelo menos 2 caracteres, aceita no maximo 80 e retorna no maximo 50 resultados. Nao pesquisa arquivos, observacoes ou documentos sensiveis de RH.

## Validacao prevista

- busca de equipamento, material e colaborador para administrador;
- restricao de busca para motorista;
- alerta automatico apontando para tela autorizada;
- navegacao desktop, breadcrumb e atalhos.

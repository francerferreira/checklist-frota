# Fase 0 - Checklist de Regressao Funcional (Desktop)

Data base: 2026-04-23
Regra: esta lista valida que nenhuma alteracao visual quebre comportamento funcional.

## 1) Login e sessao
- [ ] Login com usuario valido.
- [ ] Login com usuario invalido (mensagem de erro permanece correta).
- [ ] Encerrar sessao.
- [ ] Troca de ambiente/API sem quebrar acesso.

## 2) Navegacao principal
- [ ] Abrir janela principal sem erro.
- [ ] Navegar por todos os modulos visiveis no menu.
- [ ] Abrir e fechar telas sem travamento.
- [ ] Atalhos atuais continuam funcionando.
- [ ] Contexto de usuario/perfil continua correto.

## 3) Modulos (fluxo minimo por tela)
- [ ] Dashboard carrega dados.
- [ ] Ocorrencias: listar, filtrar, abrir item.
- [ ] Produtividade: listar indicadores.
- [ ] Frota: listar e editar cadastro.
- [ ] Checklist: listar itens e manter operacao.
- [ ] Materiais: listar/filtrar e manter operacao.
- [ ] Lavagens: fila, cronograma, confirmacao OK/X.
- [ ] Atividades: listar, criar e atualizar.
- [ ] Manutencao: programacao, execucao e calendario.
- [ ] Relatorios: filtros e geracao/exportacao.
- [ ] Logins (admin): listar/editar conforme permissao.
- [ ] Backup (admin): abrir tela e executar fluxo.

## 4) Operacoes de dados
- [ ] Criar registro.
- [ ] Editar registro.
- [ ] Excluir registro.
- [ ] Salvar com validacao obrigatoria.
- [ ] Pesquisar e filtrar.
- [ ] Ordenar tabela/grid.
- [ ] Paginacao/rolagem funciona onde aplicavel.

## 5) Dialogos e feedback
- [ ] Dialogos de confirmacao abrem e respondem.
- [ ] Alertas de sucesso/erro continuam coerentes.
- [ ] Mensagens de validacao sem perda de contexto.

## 6) Exportacoes e anexos
- [ ] Exportacao PDF (quando disponivel).
- [ ] Exportacao XLSX (quando disponivel).
- [ ] Upload/visualizacao de imagem/foto (quando aplicavel).

## 7) Integracoes e estabilidade
- [ ] Chamadas de API continuam respondendo.
- [ ] Sem erro novo de permissao no fluxo principal.
- [ ] Sem queda de desempenho perceptivel na navegacao.

## 8) Resultado final da regressao
- [ ] Aprovado sem regressao.
- [ ] Pendencias registradas e priorizadas.


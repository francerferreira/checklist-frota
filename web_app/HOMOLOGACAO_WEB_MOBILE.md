# Homologação Web Mobile

## Objetivo
Validar os fluxos críticos do frontend mobile antes de liberar nova rodada para operação.

## Ambiente mínimo
- 1 celular Android real
- 1 navegador desktop em largura até 430 px para apoio
- API acessível
- Usuário `admin` ou `gestor`
- Usuário `motorista`
- Usuário `mecanico`
- Cenário com internet normal e cenário com internet instável

## Checklist de homologação

### 1. Acesso e sessão
- [ ] Login com credencial válida entra no sistema e abre o menu correto.
- [ ] Login inválido mostra erro claro sem travar o botão.
- [ ] Logout volta para a tela de entrada e limpa a sessão visível do operador.
- [ ] Alteração de senha abre o modal, valida campos e fecha com feedback de sucesso.

### 2. Checklist principal
- [ ] Selecionar equipamento abre o checklist com módulos e contador coerentes.
- [ ] Marcar `OK` avança para o próximo item pendente sem perder contexto.
- [ ] Marcar `NÃO CONFORMIDADE` abre observação e evidência no mesmo card.
- [ ] `Enter` na observação da NC leva para o campo de evidência.
- [ ] Evidência anexada aparece como restaurada ou válida no card.
- [ ] Rascunho é salvo durante o preenchimento.
- [ ] Ao sair e voltar, o sistema oferece restauração do rascunho com data e hora.
- [ ] Envio com item pendente destaca o card com problema e leva o foco ao ponto faltante.
- [ ] Reset do checklist limpa respostas, evidência e rascunho do equipamento atual.

### 3. Histórico de checklist
- [ ] Tela abre com estado de carregamento visível.
- [ ] Filtros por tipo e período aplicam sem quebrar a matriz.
- [ ] Resumo superior mostra período, datas e total de checklists.
- [ ] Toque na frota expande a leitura da linha sem desalinhamento grave.

### 4. Atividades
- [ ] Tela abre com estado de carregamento e depois lista as atividades.
- [ ] Abrir atividade mostra resumo e itens com responsividade aceitável.
- [ ] Salvar item com evidência e observação retorna feedback visual claro.

### 5. Lavagens
- [ ] Calendário mensal continua íntegro.
- [ ] Tabela e painel do dia permanecem utilizáveis sem regressão de layout.
- [ ] Alternância entre `TODOS`, `MANHÃ` e `TARDE` funciona corretamente.
- [ ] Salvar parecer de lavagem continua possível com foto e observação.
- [ ] PDF mensal continua acessível para usuário com permissão.

### 6. Não conformidades
- [ ] Resumo mostra abertas, resolvidas, pendências e percentual de resolução.
- [ ] Filtros `ABERTAS` e `RESOLVIDAS` funcionam nos blocos esperados.
- [ ] Abrir NC interna continua possível com item, observação e evidência.
- [ ] Resolver NC mostra peça, observação e foto de depois sem sobreposição ruim no mobile.

### 7. Manutenção
- [ ] Tela abre com estado de carregamento visível.
- [ ] Resumo do mês mostra pendentes, instalados, não executados e capacidade.
- [ ] Selecionar dia no calendário atualiza o painel e os cards daquele dia.
- [ ] Cards bloqueados ou aguardando material aparecem sinalizados.
- [ ] Reprogramar e concluir item mantém feedback claro e sem desalinhamento no mobile.

### 8. Offline e recuperação
- [ ] Indicador `ONLINE/OFFLINE` responde corretamente à perda de conexão.
- [ ] Checklist enviado offline entra na fila local.
- [ ] Ao voltar a conexão, a sincronização consegue reenviar a fila pendente.
- [ ] Limpeza de cache do app não remove comportamento básico do sistema após recarga.

## Critério de aceite
- Sem travamento em fluxo principal.
- Sem perda de rascunho em operação normal.
- Sem quebra visual crítica em largura de até 380 px.
- Lavagens mantidas com a estrutura de tabela/calendário intacta.
- Falhas restantes devem estar documentadas com tela, perfil de usuário e passo de reprodução.

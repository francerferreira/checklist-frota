Arquivo canonico ativo do Web Mobile:
- app.js

Arquivos mantidos apenas como historico de evolucao:
- legacy/app-20260419-12.js ate legacy/app-20260419-25.js

Regra de manutencao:
- novas alteracoes do frontend mobile devem entrar em app.js
- index.html e paginas auxiliares devem apontar para app.js
- os arquivos versionados antigos nao devem receber novas mudancas
- a pasta legacy existe so para consulta e comparacao pontual

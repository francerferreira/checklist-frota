# Etapa 05 - Documentos, treinamentos e historico funcional (SQLite)

## Entrega

Foram incluidos tres registros ligados ao cadastro de colaborador:

- `employee_documents`: documento anexado, emissao, validade, situacao e marcacao de sensibilidade;
- `employee_trainings`: curso, certificado, carga horaria, validade e situacao;
- `employee_history_events`: eventos funcionais datados, como mudanca de funcao e movimentacoes internas.

Os arquivos continuam usando o fluxo existente de upload do sistema e a API aceita apenas caminhos internos iniciados por `/uploads/`.

## Protecao de dados

Documento marcado como sensivel so pode ser criado e listado por perfil `admin`. O perfil `gestor` visualiza apenas documentos funcionais nao sensiveis. Esta regra e aplicada na API, portanto nao depende somente da tela.

Nao foram incluidos campos de CPF, dados clinicos detalhados ou informacoes medicas. Quando houver necessidade documental, o anexo sensivel fica referenciado sem expor seu conteudo na listagem de gestor.

## Interface

A tela **Documentos e treinamentos**, dentro de **Gestao**, permite:

1. anexar documentos e certificados pelo fluxo de upload ja existente;
2. registrar curso e validade;
3. registrar evento funcional;
4. filtrar os registros por colaborador.

O historico funcional so aparece apos selecionar um colaborador, evitando uma listagem ampla sem necessidade.

## Validacao prevista

- rotas de RH: criacao, ocultacao de documento sensivel e bloqueio do perfil motorista;
- navegacao desktop: nova tela permitida apenas para administrador e gestor;
- banco local: criacao das tres tabelas pelo bootstrap SQLite e validacao de backup/restauracao.

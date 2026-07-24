# Etapa 03 - RH: cadastro de colaboradores

## Entrega aplicada

- Criada a tabela `employees` no SQLite local.
- Criada a tela **Recursos Humanos** no desktop para admin e gestor.
- Cada colaborador possui matrícula, nome, função, equipe, turno, situação, foto, data de admissão e observação.
- O vínculo com um login de sistema é opcional e único: um login não pode representar dois colaboradores.
- A foto é enviada pelo mecanismo de upload já existente; a API não aceita caminho de arquivo informado manualmente.

## Situações disponíveis

- `PRE_CADASTRO`
- `AGUARDANDO_FOTO`
- `AGUARDANDO_DOCUMENTOS`
- `EM_VALIDACAO`
- `ATIVO`
- `INATIVO`

## Segurança

- Admin e gestor podem listar, criar e alterar colaboradores.
- Outros perfis recebem `403` ao tentar acessar a API de RH.
- Não existe exclusão física nesta etapa.
- CPF, dados médicos, atestados, férias, frequência e documentos sensíveis não foram criados nesta entrega.

## Rotas

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/rh/colaboradores` | Listar e filtrar colaboradores |
| GET | `/rh/colaboradores/usuarios-disponiveis` | Consultar logins ativos para vínculo opcional |
| POST | `/rh/colaboradores` | Criar colaborador |
| GET | `/rh/colaboradores/<id>` | Consultar um colaborador |
| PUT | `/rh/colaboradores/<id>` | Atualizar cadastro funcional |

## Validação

- Teste de criação, atualização, busca e vínculo de login: aprovado.
- Teste de bloqueio para perfil sem permissão: aprovado.
- Teste de vínculo duplicado de login: aprovado.
- Navegação desktop: regressão aprovada.
- SQLite local: tabela `employees` confirmada, total de 56 tabelas.

## Próxima etapa

Etapa 04 - RH: frequência, faltas, atrasos, atestados, férias, DSR, folgas e trilha de auditoria.

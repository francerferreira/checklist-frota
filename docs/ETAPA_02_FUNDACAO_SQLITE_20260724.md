# Etapa 02 - Fundação SQLite local

## Objetivo

Fortalecer o uso local do SQLite para que o backend responda melhor quando duas gravações forem solicitadas quase ao mesmo tempo, sem substituir o backup e a restauração já existentes.

## Proteções aplicadas

- `journal_mode=WAL`: permite leituras enquanto uma gravação está em andamento.
- `busy_timeout=15000`: a segunda gravação aguarda até 15 segundos pelo término da primeira antes de retornar erro.
- `foreign_keys=ON`: chaves estrangeiras são ativadas em toda conexão SQLite aberta pelo backend.
- `synchronous=FULL`: confirma gravações com prioridade para durabilidade dos dados.
- `/health`: informa modo de journal, tempo de espera e estado das chaves estrangeiras, sem revelar o caminho do banco.

SQLite continua permitindo uma gravação por vez. O objetivo é organizar a fila curta de gravações; não transformar o banco em múltiplos escritores simultâneos.

## Operação segura

Use `validar_sqlite_local.bat` para executar a validação local de saúde, backup e restauração isolada.

Regras:

1. Execute apenas uma instância do backend apontando para o mesmo arquivo `.db`.
2. Desktop e web/mobile usam a API; não abrem o arquivo `.db` diretamente.
3. Antes de atualização estrutural, execute a validação e mantenha o ZIP de backup gerado.
4. Em falha local, restaure primeiro em pasta isolada para validar o backup antes de substituir qualquer arquivo operacional.

## Validações executadas

- Teste de runtime SQLite: 2 aprovados, incluindo espera da segunda gravação.
- Teste de segurança e saúde: 3 aprovados.
- Teste de backup e restauração: 1 aprovado.
- Validador executado no banco SQLite local:
  - 55 tabelas;
  - integridade `ok`;
  - nenhuma violação de chave estrangeira;
  - WAL, `busy_timeout=15000` e chaves estrangeiras ativas;
  - backup restaurado em cópia temporária com 13 registros e 9 anexos.

## Próxima etapa

Etapa 03 - RH: cadastro de colaboradores, função, equipe, turno, foto, situação e vínculo opcional com o usuário de login.

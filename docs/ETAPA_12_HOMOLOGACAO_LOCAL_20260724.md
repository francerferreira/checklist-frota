# Etapa 12 - Homologação local e aceite operacional

## Resultado técnico desta execução

| Verificação | Resultado |
|---|---|
| Navegador Web Mobile ponta a ponta | Aprovado: 5 testes |
| Operações mobile e sincronização | Validado na suíte automatizada |
| Navegação Desktop | Validada na suíte automatizada |
| Base Mestre, indicadores e PCM | Validados por testes de contrato e regra |
| SQLite local | Integridade, chaves estrangeiras, backup ZIP e restauração isolada validados |

O banco homologado continua local, com SQLite em modo WAL. Nenhum dado de produção, PostgreSQL ou publicação externa foi alterado.

## Roteiro de treinamento prático

Use um equipamento e usuários de homologação, nunca um registro operacional real, para executar esta sequência:

1. **Operação mobile:** entrar, localizar o ativo, preencher um checklist com uma não conformidade e anexar evidência.
2. **Modo sem rede:** abrir uma inspeção técnica, desligar a rede, concluir e confirmar que a fila offline aparece; religar a rede e confirmar a sincronização.
3. **Gestão desktop:** localizar a não conformidade, consultar a manutenção e o PCM; conferir que a programação somente sugere datas e não cria OS sozinha.
4. **RH:** vincular um login de homologação a um colaborador, consultar a frequência e abrir `Minha jornada` no celular.
5. **BI:** consultar o contrato `/relatorios/bi/contrato`, exportar a Base Mestre e importar o CSV no Power BI sem abrir o arquivo `.db` ativo.
6. **Recuperação:** executar `python tools\validate_local_homologation.py` e guardar o ZIP gerado antes de uma atualização local.

## Ficha de aceite humano

| Item | Responsável | Data | Resultado | Assinatura/registro |
|---|---|---|---|---|
| Checklist e evidência no celular | Operação |  | Pendente |  |
| Fila offline e sincronização | Operação + TI |  | Pendente |  |
| Manutenção, PCM e backlog | PCM/Manutenção |  | Pendente |  |
| RH e privacidade dos dados | RH |  | Pendente |  |
| Exportação Power BI | Gestão |  | Pendente |  |
| Backup e restauração | TI |  | Pendente |  |

## Critério de liberação local

O aceite local só pode ser marcado como concluído quando todos os itens acima forem executados em dispositivo real, por responsáveis identificados, e a restauração do backup continuar aprovada. Até lá, a aprovação é **técnica**, não operacional.

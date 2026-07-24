# Etapa 09 - PCM, capacidade e programacao (SQLite)

## Entrega

Foi ampliada a tela PCM existente com uma projecao de programacao por horizonte:

- capacidade diaria em minutos, configurada apenas para a consulta;
- carga ocupada, livre e excedente por dia;
- quantidade de OS e concluidas por dia;
- cumprimento preventivo sobre dias ja ocorridos;
- janela de programacao e data sugerida para preventivas vencidas sem OS ativa.

## Como a sugestao funciona

O sistema nao cria nem move OS por conta propria. Ele procura o primeiro dia livre dentro da janela da preventiva, considerando a duracao estimada do plano e a capacidade diaria informada. Se nao houver espaco, mostra `SEM_CAPACIDADE`.

Pense como uma agenda de oficina: a tela marca os horarios que cabem no dia, mas o encarregado continua decidindo quando confirmar o servico.

## Regras preservadas

- nenhuma tabela ou migration foi criada;
- OS, reprogramacao e geracao de preventivas continuam nos fluxos auditados existentes;
- horizonte limitado a 90 dias e capacidade entre 60 e 1440 minutos/dia;
- cumprimento e indicador operacional, nao medicao de folha ou produtividade individual.

## Validacao prevista

- preventiva vencida recebe janela e data recomendada quando cabe na capacidade;
- horizonte retorna carga diaria consistente;
- mecanico segue bloqueado de consultar PCM gerencial.

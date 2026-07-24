# Etapa 06 - Painel e alertas de RH (SQLite)

## Entrega

Foi incluida a tela **Painel de RH**, em **Gestao**, exclusiva para administrador e gestor. Ela consolida:

- efetivo total, ativo e inativo;
- ocorrencias de frequencia no periodo;
- indicador gerencial de absenteismo;
- documentos e treinamentos vencidos ou vencendo;
- efetivo ativo por equipe.

## Regra do indicador

O absenteismo e calculado por `FALTA`, `ATESTADO` e `AFASTADO` sobre os registros operacionais (`PRESENTE`, `ATRASO`, `FALTA`, `ATESTADO` e `AFASTADO`) do periodo selecionado. Ele serve como termometro de gestao e nao substitui conferencia de folha, escala ou ponto oficial.

## Alertas e privacidade

O alerta mostra apenas tipo, colaborador, registro, validade e situacao. Nao expõe arquivo, observacao ou conteudo documental. Gestor nao recebe alerta de documento marcado como sensivel; administrador recebe conforme a permissao ja definida na Etapa 05.

## Exportacao permitida

Os alertas podem ser exportados em CSV ou Excel pela tela desktop. A exportacao nao inclui caminho de arquivo nem observacoes e gera evento de auditoria `RH_MANAGEMENT / EXPORT`.

## Validacao prevista

- calculo de efetivo, frequencia e alerta no endpoint `/rh/gestao`;
- bloqueio de motorista;
- ocultacao de documento sensivel para gestor;
- auditoria de exportacao;
- navegacao desktop para administrador e gestor.

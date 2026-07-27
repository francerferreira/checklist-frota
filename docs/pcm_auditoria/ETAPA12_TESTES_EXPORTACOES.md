# Etapa 12 — testes, auditoria e exportações de Preventivas

## O que foi fechado

- A tela Desktop de Preventivas RTG e LBS exporta a visão filtrada atual.
- Formatos disponíveis: CSV, Excel (`.xlsx`) e PDF executivo em A4 paisagem.
- O PDF leva título do módulo, família, data/hora de emissão, responsável e tabela operacional.
- A auditoria existente continua sendo a trilha oficial: alterações de planos, leituras,
  execuções, etapas e integrações são persistidas em `audit_logs` pelos hooks do serviço
  `backend/app/services/audit_service.py`.

## Como usar

1. Abra **Preventiva RTG** ou **Preventiva LBS** no Desktop.
2. Use situação e pesquisa para montar a visão desejada.
3. Clique em **CSV**, **Excel** ou **PDF**.
4. Escolha o arquivo. O PDF é aberto ao terminar; CSV e Excel ficam salvos no caminho escolhido.

O filtro funciona como uma peneira: somente as linhas que permanecem na tabela são exportadas.

## Validação da etapa

Os testes cobrem:

- preservação dos cabeçalhos e acentos no CSV;
- geração de arquivo Excel não vazio;
- geração de PDF não vazio;
- funcionamento das regras centrais de cálculo de ciclo e vencimento;
- contratos das rotas do Dashboard e da interface Web Mobile já existentes.

Para conferência local:

```powershell
pytest -q tests/test_preventive_exports.py tests/test_preventive_service.py tests/test_preventive_rtg_page.py
```

## Limite conhecido

O relatório exporta o retrato da tela no momento da emissão. A auditoria histórica deve ser
consultada em **Administração → Logs de auditoria**, com filtro por entidade e período.

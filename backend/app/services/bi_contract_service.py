from __future__ import annotations

from app.services.report_service import MASTER_BASE_EXPORT_COLUMNS


BI_CONTRACT_VERSION = "bi.sqlite.readonly.v1"


def build_readonly_bi_contract() -> dict:
    """Catálogo estável de consumo analítico, sem conexão de escrita ao SQLite."""
    return {
        "schema_version": BI_CONTRACT_VERSION,
        "access": {
            "mode": "EXPORTACAO_CONTROLADA",
            "database_write": False,
            "active_sqlite_file_access": False,
            "authentication": "Bearer de usuario admin ou gestor",
            "refresh_policy": "Manual ou por processo autenticado aprovado; nao compartilhar o arquivo SQLite em uso.",
        },
        "datasets": [
            {
                "id": "pcm_base_mestre",
                "schema_version": "pcm.base_mestre.v1",
                "purpose": "Intervencoes programadas, OS, equipamento, familia, local e situacao operacional.",
                "read_endpoint": "/relatorios/base-mestre",
                "export_endpoint": "/relatorios/base-mestre/exportar?formato=csv",
                "formats": ["json", "csv", "xlsx"],
                "primary_key": "intervention_id",
                "columns": list(MASTER_BASE_EXPORT_COLUMNS),
                "max_export_rows": 5000,
                "filters": ["familia", "equipamento", "local", "status", "origem", "busca", "data_inicial", "data_final", "ativos"],
            },
            {
                "id": "manutencao_executiva",
                "purpose": "Indicadores consolidados de confiabilidade, disponibilidade, backlog, preventivas e suprimentos.",
                "read_endpoint": "/relatorios/manutencao-executivo",
                "formats": ["json"],
                "refresh": "Consulta autenticada; nao e uma tabela operacional.",
                "measures": ["mtbf_horas", "mttr_horas", "backlog.total", "backlog.vencidas", "pcm.preventivas_vencendo_ou_vencidas", "suprimentos.materiais_abaixo_minimo"],
            },
            {
                "id": "pcm_programacao",
                "purpose": "Capacidade diaria, carga, janelas preventivas e cumprimento operacional projetado.",
                "read_endpoint": "/pcm/programacao",
                "formats": ["json"],
                "filters": ["data_inicial", "data_final", "capacidade_minutos"],
                "measures": ["capacity_total_minutes", "occupied_minutes", "free_minutes", "overloaded_days", "preventive_compliance_percent"],
            },
        ],
        "indicator_definitions": [
            {
                "id": "backlog_aberto",
                "source": "manutencao_executiva.backlog.total",
                "definition": "Quantidade de itens retornados pelo backlog operacional no momento da consulta.",
            },
            {
                "id": "cumprimento_preventivo",
                "source": "pcm_programacao.summary.preventive_compliance_percent",
                "definition": "Percentual de itens preventivos concluídos em dias já ocorridos, dentro do horizonte consultado.",
            },
            {
                "id": "mtbf",
                "source": "manutencao_executiva.confiabilidade.mtbf_horas",
                "definition": "Média das horas entre falhas comparáveis, calculada apenas quando existem execuções completas registradas.",
            },
            {
                "id": "mttr",
                "source": "manutencao_executiva.confiabilidade.mttr_horas",
                "definition": "Média das horas de reparos concluídos com início, conclusão e liberação registrados.",
            },
        ],
        "limitations": [
            "Campos sem dado continuam nulos; o contrato nao estima custo, parada ou meta ausente.",
            "Power BI nao deve gravar no SQLite nem abrir o arquivo operacional enquanto o backend estiver em uso.",
            "Para refresh automatico, use somente uma conta tecnica autenticada e aprovada em etapa posterior.",
        ],
    }

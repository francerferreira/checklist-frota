from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from .severity_service import overall_executive_status


@dataclass(slots=True)
class MessagePackage:
    title: str
    email_subject: str
    whatsapp_text: str
    email_body: str
    summary_items: list[tuple[str, str]]


def build_macro_message_package(rows: list[dict], period_label: str, generated_by: str = "") -> MessagePackage:
    total_nc = sum(_as_int(row.get("total_nc")) for row in rows)
    open_total = sum(_as_int(row.get("abertas")) for row in rows)
    resolved_total = sum(_as_int(row.get("resolvidas")) for row in rows)
    priority = overall_executive_status(rows, total_nc, open_total)
    top_items = sorted(rows, key=lambda row: _as_int(row.get("total_nc")), reverse=True)[:5]

    leader = top_items[0]["item_nome"] if top_items else "-"
    summary_items = [
        ("Período", period_label),
        ("Total de não conformidades", str(total_nc)),
        ("Itens com ocorrência", str(len(rows))),
        ("Abertas", str(open_total)),
        ("Resolvidas", str(resolved_total)),
        ("Prioridade", priority["label"]),
    ]

    whatsapp_lines = [
        "**RELATÓRIO EXECUTIVO - NÃO CONFORMIDADES POR ITEM**",
        f"_Período: {period_label}_",
    ]
    if generated_by:
        whatsapp_lines.append(f"_Emitido por: {generated_by}_")
    whatsapp_lines.extend(
        [
            "",
            "**Resumo geral**",
            f"- Total de não conformidades: {total_nc}",
            f"- Itens com ocorrência: {len(rows)}",
            f"- Abertas: {open_total}",
            f"- Resolvidas: {resolved_total}",
            f"- Prioridade executiva: {priority['label']}",
            "",
            "**Top 5 itens**",
        ]
    )
    whatsapp_lines.extend(_numbered_lines(top_items, "item_nome", "total_nc", "ocorrências"))
    whatsapp_lines.extend(
        [
            "",
            "**Conclusão executiva**",
            f"_{_macro_conclusion(priority['label'], leader, open_total, resolved_total)}_",
        ]
    )

    email_lines = [
        "RELATÓRIO EXECUTIVO - NÃO CONFORMIDADES POR ITEM",
        f"Período: {period_label}",
    ]
    if generated_by:
        email_lines.append(f"Emitido por: {generated_by}")
    email_lines.extend(
        [
            "",
            "Resumo geral:",
            f"- Total de não conformidades: {total_nc}",
            f"- Itens com ocorrência: {len(rows)}",
            f"- Abertas: {open_total}",
            f"- Resolvidas: {resolved_total}",
            f"- Prioridade executiva: {priority['label']}",
            "",
            "Top 5 itens:",
        ]
    )
    email_lines.extend(_numbered_lines(top_items, "item_nome", "total_nc", "ocorrências"))
    email_lines.extend(
        [
            "",
            "Conclusão executiva:",
            _macro_conclusion(priority["label"], leader, open_total, resolved_total),
        ]
    )

    return MessagePackage(
        title="Mensagem executiva - Não conformidades por item",
        email_subject=f"Relatório executivo - Não conformidades por item | {period_label}",
        whatsapp_text="\n".join(whatsapp_lines).strip(),
        email_body="\n".join(email_lines).strip(),
        summary_items=summary_items,
    )


def build_micro_message_package(rows: list[dict], period_label: str, generated_by: str = "") -> MessagePackage:
    total_nc = sum(_as_int(row.get("total_nc")) for row in rows)
    vehicles_with_nc = sum(1 for row in rows if _as_int(row.get("total_nc")) > 0)
    priority = overall_executive_status([{"total_nc": total_nc, "abertas": total_nc}], total_nc, total_nc)
    top_items = sorted(rows, key=lambda row: _as_int(row.get("total_nc")), reverse=True)[:5]
    leader = top_items[0].get("frota") if top_items else "-"

    summary_items = [
        ("Período", period_label),
        ("Total de não conformidades", str(total_nc)),
        ("Veículos com ocorrência", str(vehicles_with_nc)),
        ("Prioridade", priority["label"]),
        ("Líder", leader),
    ]

    whatsapp_lines = [
        "**RELATÓRIO EXECUTIVO - NÃO CONFORMIDADES POR EQUIPAMENTO**",
        f"_Período: {period_label}_",
    ]
    if generated_by:
        whatsapp_lines.append(f"_Emitido por: {generated_by}_")
    whatsapp_lines.extend(
        [
            "",
            "**Resumo geral**",
            f"- Total de não conformidades: {total_nc}",
            f"- Veículos com ocorrência: {vehicles_with_nc}",
            f"- Prioridade executiva: {priority['label']}",
            "",
            "**Top 5 equipamentos**",
        ]
    )
    whatsapp_lines.extend(_numbered_lines(top_items, "frota", "total_nc", "ocorrências"))
    whatsapp_lines.extend(
        [
            "",
            "**Conclusão executiva**",
            f"_{_micro_conclusion(priority['label'], leader, total_nc, vehicles_with_nc)}_",
        ]
    )

    email_lines = [
        "RELATÓRIO EXECUTIVO - NÃO CONFORMIDADES POR EQUIPAMENTO",
        f"Período: {period_label}",
    ]
    if generated_by:
        email_lines.append(f"Emitido por: {generated_by}")
    email_lines.extend(
        [
            "",
            "Resumo geral:",
            f"- Total de não conformidades: {total_nc}",
            f"- Veículos com ocorrência: {vehicles_with_nc}",
            f"- Prioridade executiva: {priority['label']}",
            "",
            "Top 5 equipamentos:",
        ]
    )
    email_lines.extend(_numbered_lines(top_items, "frota", "total_nc", "ocorrências"))
    email_lines.extend(
        [
            "",
            "Conclusão executiva:",
            _micro_conclusion(priority["label"], leader, total_nc, vehicles_with_nc),
        ]
    )

    return MessagePackage(
        title="Mensagem executiva - Não conformidades por equipamento",
        email_subject=f"Relatório executivo - Não conformidades por equipamento | {period_label}",
        whatsapp_text="\n".join(whatsapp_lines).strip(),
        email_body="\n".join(email_lines).strip(),
        summary_items=summary_items,
    )


def build_item_message_package(
    rows: list[dict],
    item_name: str,
    period_label: str,
    generated_by: str = "",
) -> MessagePackage:
    total_occurrences = len(rows)
    open_total = sum(1 for row in rows if not row.get("resolvido"))
    resolved_total = total_occurrences - open_total
    vehicle_counter = Counter((row.get("veiculo") or {}).get("frota") or "-" for row in rows)
    top_vehicles = vehicle_counter.most_common(5)
    priority = overall_executive_status([{"total_nc": total_occurrences, "abertas": open_total}], total_occurrences, open_total)
    leader = top_vehicles[0][0] if top_vehicles else "-"

    summary_items = [
        ("Item", item_name or "-"),
        ("Período", period_label),
        ("Total de ocorrências", str(total_occurrences)),
        ("Abertas", str(open_total)),
        ("Resolvidas", str(resolved_total)),
        ("Prioridade", priority["label"]),
    ]

    whatsapp_lines = [
        f"**RELATÓRIO EXECUTIVO - ITEM {item_name or '-'}**",
        f"_Período: {period_label}_",
    ]
    if generated_by:
        whatsapp_lines.append(f"_Emitido por: {generated_by}_")
    whatsapp_lines.extend(
        [
            "",
            "**Resumo geral**",
            f"- Total de ocorrências: {total_occurrences}",
            f"- Abertas: {open_total}",
            f"- Resolvidas: {resolved_total}",
            f"- Veículos impactados: {len(vehicle_counter)}",
            f"- Prioridade executiva: {priority['label']}",
            "",
            "**Top 5 veículos impactados**",
        ]
    )
    whatsapp_lines.extend(_top_counter_lines(top_vehicles, "ocorrências"))
    whatsapp_lines.extend(
        [
            "",
            "**Conclusão executiva**",
            f"_{_item_conclusion(priority['label'], item_name or '-', leader, open_total, resolved_total)}_",
        ]
    )

    email_lines = [
        f"RELATÓRIO EXECUTIVO - ITEM {item_name or '-'}",
        f"Período: {period_label}",
    ]
    if generated_by:
        email_lines.append(f"Emitido por: {generated_by}")
    email_lines.extend(
        [
            "",
            "Resumo geral:",
            f"- Total de ocorrências: {total_occurrences}",
            f"- Abertas: {open_total}",
            f"- Resolvidas: {resolved_total}",
            f"- Veículos impactados: {len(vehicle_counter)}",
            f"- Prioridade executiva: {priority['label']}",
            "",
            "Top 5 veículos impactados:",
        ]
    )
    email_lines.extend(_top_counter_lines(top_vehicles, "ocorrências"))
    email_lines.extend(
        [
            "",
            "Conclusão executiva:",
            _item_conclusion(priority["label"], item_name or "-", leader, open_total, resolved_total),
        ]
    )

    return MessagePackage(
        title=f"Mensagem executiva - {item_name or 'Item'}",
        email_subject=f"Relatório executivo - Item {item_name or '-'} | {period_label}",
        whatsapp_text="\n".join(whatsapp_lines).strip(),
        email_body="\n".join(email_lines).strip(),
        summary_items=summary_items,
    )


def build_material_message_package(report: dict, period_label: str, generated_by: str = "") -> MessagePackage:
    resumo = report.get("resumo", {})
    below_stock = report.get("baixo_estoque", [])
    consumption = report.get("consumo_periodo", [])
    ranking = report.get("ranking_uso", [])

    total_materials = _as_int(resumo.get("total_materiais"))
    below_minimum = _as_int(resumo.get("abaixo_minimo"))
    saldo_total = _as_int(resumo.get("saldo_total"))
    consumption_total = _as_int(resumo.get("consumo_total_periodo"))
    priority = overall_executive_status(
        [{"total_nc": below_minimum, "abertas": below_minimum}],
        below_minimum,
        below_minimum,
    )
    leader = ranking[0]["descricao"] if ranking else "-"

    summary_items = [
        ("Período", period_label),
        ("Materiais", str(total_materials)),
        ("Abaixo do mínimo", str(below_minimum)),
        ("Saldo total", str(saldo_total)),
        ("Consumo no período", str(consumption_total)),
        ("Prioridade", priority["label"]),
    ]

    whatsapp_lines = [
        "**RELATÓRIO EXECUTIVO - ESTOQUE DE MATERIAIS**",
        f"_Período: {period_label}_",
    ]
    if generated_by:
        whatsapp_lines.append(f"_Emitido por: {generated_by}_")
    whatsapp_lines.extend(
        [
            "",
            "**Resumo geral**",
            f"- Materiais cadastrados: {total_materials}",
            f"- Materiais abaixo do mínimo: {below_minimum}",
            f"- Saldo total em estoque: {saldo_total}",
            f"- Consumo no período: {consumption_total}",
            f"- Prioridade executiva: {priority['label']}",
            "",
            "**Ranking dos mais usados**",
        ]
    )
    whatsapp_lines.extend(_numbered_lines(ranking[:5], "descricao", "consumo_total", "movimentações"))
    if below_stock:
        whatsapp_lines.extend(["", "**Materiais abaixo do mínimo**"])
        whatsapp_lines.extend(_numbered_lines(below_stock[:5], "descricao", "deficit", "unidades em déficit"))
    whatsapp_lines.extend(
        [
            "",
            "**Conclusão executiva**",
            f"_{_material_conclusion(priority['label'], below_minimum, leader, consumption_total)}_",
        ]
    )

    email_lines = [
        "RELATÓRIO EXECUTIVO - ESTOQUE DE MATERIAIS",
        f"Período: {period_label}",
    ]
    if generated_by:
        email_lines.append(f"Emitido por: {generated_by}")
    email_lines.extend(
        [
            "",
            "Resumo geral:",
            f"- Materiais cadastrados: {total_materials}",
            f"- Materiais abaixo do mínimo: {below_minimum}",
            f"- Saldo total em estoque: {saldo_total}",
            f"- Consumo no período: {consumption_total}",
            f"- Prioridade executiva: {priority['label']}",
            "",
            "Ranking dos mais usados:",
        ]
    )
    email_lines.extend(_numbered_lines(ranking[:5], "descricao", "consumo_total", "movimentações"))
    if below_stock:
        email_lines.extend(["", "Materiais abaixo do mínimo:"])
        email_lines.extend(_numbered_lines(below_stock[:5], "descricao", "deficit", "unidades em déficit"))
    email_lines.extend(
        [
            "",
            "Conclusão executiva:",
            _material_conclusion(priority["label"], below_minimum, leader, consumption_total),
        ]
    )

    return MessagePackage(
        title="Mensagem executiva - Estoque de materiais",
        email_subject=f"Relatório executivo - Estoque de materiais | {period_label}",
        whatsapp_text="\n".join(whatsapp_lines).strip(),
        email_body="\n".join(email_lines).strip(),
        summary_items=summary_items,
    )


def build_activity_message_package(activity: dict, generated_by: str = "") -> MessagePackage:
    resumo = activity.get("resumo", {})
    items = activity.get("itens", [])
    total = _as_int(resumo.get("total"))
    installed = _as_int(resumo.get("instalados"))
    not_installed = _as_int(resumo.get("nao_instalados"))
    pending = _as_int(resumo.get("pendentes"))
    problem_count = not_installed + pending
    priority = overall_executive_status([{"total_nc": problem_count, "abertas": problem_count}], problem_count, problem_count)

    item_name = activity.get("item_nome") or "-"
    period_label = _activity_period(activity)
    leader = next(
        ((item.get("veiculo") or {}).get("frota") or "-" for item in items if item.get("status_execucao") in {"NAO_INSTALADO", "PENDENTE"}),
        None,
    )
    if not leader and items:
        leader = (items[0].get("veiculo") or {}).get("frota") or "-"
    if not leader:
        leader = "-"

    summary_items = [
        ("Atividade", activity.get("titulo") or "-"),
        ("Período", period_label),
        ("Total", str(total)),
        ("Instalados", str(installed)),
        ("Não instalados", str(not_installed)),
        ("Pendentes", str(pending)),
    ]

    whatsapp_lines = [
        "**RELATÓRIO EXECUTIVO - ATIVIDADE EM MASSA**",
        f"_Atividade: {activity.get('titulo') or '-'}_",
        f"_Período: {period_label}_",
    ]
    if generated_by:
        whatsapp_lines.append(f"_Emitido por: {generated_by}_")
    whatsapp_lines.extend(
        [
            "",
            "**Resumo geral**",
            f"- Equipamentos auditados: {total}",
            f"- Instalados: {installed}",
            f"- Não instalados: {not_installed}",
            f"- Pendentes: {pending}",
            f"- Prioridade executiva: {priority['label']}",
            "",
            "**Detalhe operacional**",
        ]
    )
    whatsapp_lines.extend(_activity_lines(items))
    whatsapp_lines.extend(
        [
            "",
            "**Conclusão executiva**",
            f"_{_activity_conclusion(priority['label'], item_name, total, installed, not_installed, pending, leader)}_",
        ]
    )

    email_lines = [
        "RELATÓRIO EXECUTIVO - ATIVIDADE EM MASSA",
        f"Atividade: {activity.get('titulo') or '-'}",
        f"Período: {period_label}",
    ]
    if generated_by:
        email_lines.append(f"Emitido por: {generated_by}")
    email_lines.extend(
        [
            "",
            "Resumo geral:",
            f"- Equipamentos auditados: {total}",
            f"- Instalados: {installed}",
            f"- Não instalados: {not_installed}",
            f"- Pendentes: {pending}",
            f"- Prioridade executiva: {priority['label']}",
            "",
            "Detalhe operacional:",
        ]
    )
    email_lines.extend(_activity_lines(items))
    email_lines.extend(
        [
            "",
            "Conclusão executiva:",
            _activity_conclusion(priority["label"], item_name, total, installed, not_installed, pending, leader),
        ]
    )

    return MessagePackage(
        title="Mensagem executiva - Atividade em massa",
        email_subject=f"Atividade em massa - {activity.get('titulo') or '-'} | {period_label}",
        whatsapp_text="\n".join(whatsapp_lines).strip(),
        email_body="\n".join(email_lines).strip(),
        summary_items=summary_items,
    )


def _activity_period(activity: dict) -> str:
    created_at = activity.get("created_at")
    finalized_at = activity.get("finalized_at")
    start = _format_date(created_at)
    end = _format_date(finalized_at)
    if start == "-" and end == "-":
        return "Base consolidada"
    if end == "-":
        return f"A partir de {start}"
    return f"{start} a {end}"


def _activity_lines(items: list[dict]) -> list[str]:
    lines: list[str] = []
    ordered = sorted(
        items,
        key=lambda item: (
            0 if item.get("status_execucao") in {"NAO_INSTALADO", "PENDENTE"} else 1,
            _as_int(item.get("id")),
        ),
    )
    for index, item in enumerate(ordered[:5], start=1):
        vehicle = item.get("veiculo") or {}
        status = _activity_status_label(item.get("status_execucao"))
        lines.append(f"{index}. {vehicle.get('frota') or '-'} - {status}")
    if not lines:
        lines.append("- Nenhum equipamento informado.")
    return lines


def _activity_status_label(value: str | None) -> str:
    return {
        "INSTALADO": "Instalado",
        "NAO_INSTALADO": "Não instalado",
        "PENDENTE": "Pendente",
    }.get(value or "", value or "-")


def _macro_conclusion(priority_label: str, leader: str, open_total: int, resolved_total: int) -> str:
    if priority_label == "Alta prioridade":
        return (
            f"Ação imediata recomendada no item {leader}. "
            f"Há {open_total} ocorrências em aberto e {resolved_total} já resolvidas no período."
        )
    if priority_label == "Prioridade moderada":
        return (
            f"Manter acompanhamento nos itens recorrentes, com foco em {leader}. "
            f"O cenário ainda exige disciplina sobre {open_total} ocorrências em aberto."
        )
    return "Cenário controlado. Manter rotina de acompanhamento e preservar o ganho obtido nas tratativas."


def _micro_conclusion(priority_label: str, leader: str, total_nc: int, vehicles_with_nc: int) -> str:
    if priority_label == "Alta prioridade":
        return (
            f"Priorizar a intervenção nos equipamentos com maior concentração de ocorrências, especialmente {leader}. "
            f"São {vehicles_with_nc} veículos com registros e {total_nc} ocorrências ao todo."
        )
    if priority_label == "Prioridade moderada":
        return (
            f"Monitorar a evolução dos veículos mais recorrentes, em especial {leader}. "
            f"O volume total exige acompanhamento próximo para evitar recorrência."
        )
    return "Cenário controlado. Continuar o monitoramento preventivo e a manutenção da rotina operacional."


def _item_conclusion(priority_label: str, item_name: str, leader: str, open_total: int, resolved_total: int) -> str:
    if priority_label == "Alta prioridade":
        return (
            f"Atuação imediata recomendada para o item {item_name}, com maior atenção ao veículo {leader}. "
            f"Há {open_total} ocorrências em aberto e {resolved_total} já resolvidas."
        )
    if priority_label == "Prioridade moderada":
        return (
            f"Item {item_name} segue em acompanhamento. "
            f"Manter prioridade nas ocorrências em aberto e validar a reincidência no veículo {leader}."
        )
    return f"Item {item_name} sob controle. Manter acompanhamento de rotina e encerramento das ocorrências resolvidas."


def _material_conclusion(priority_label: str, below_minimum: int, leader: str, consumption_total: int) -> str:
    if priority_label == "Alta prioridade":
        return (
            f"Reabastecimento imediato recomendado. Há {below_minimum} materiais abaixo do mínimo, "
            f"com foco principal em {leader}. Consumo no período: {consumption_total}."
        )
    if priority_label == "Prioridade moderada":
        return (
            f"Manter reposição programada dos itens em alerta, com atenção ao material {leader}. "
            f"O consumo registrado no período confirma necessidade de acompanhamento."
        )
    return "Estoque controlado. Manter a rotina de reposição e o acompanhamento dos níveis mínimos."


def _activity_conclusion(
    priority_label: str,
    item_name: str,
    total: int,
    installed: int,
    not_installed: int,
    pending: int,
    leader: str,
) -> str:
    if priority_label == "Alta prioridade":
        return (
            f"Concluir a atividade {item_name} com prioridade em {leader}. "
            f"Há {not_installed} itens não instalados e {pending} pendentes em um total de {total} equipamentos."
        )
    if priority_label == "Prioridade moderada":
        return (
            f"Atividade {item_name} em acompanhamento. "
            f"Já foram instalados {installed} equipamentos, mas ainda existem itens pendentes para fechamento."
        )
    return f"Atividade {item_name} em situação controlada, com {installed} equipamentos instalados e acompanhamento normal."


def _numbered_lines(rows: list[dict], label_key: str, value_key: str, suffix: str) -> list[str]:
    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        label = row.get(label_key) or "-"
        value = _as_int(row.get(value_key))
        lines.append(f"{index}. {label} - {value} {suffix}")
    if not lines:
        lines.append("- Sem registros para destacar.")
    return lines


def _top_counter_lines(items: list[tuple[str, int]], suffix: str) -> list[str]:
    lines: list[str] = []
    for index, (label, value) in enumerate(items, start=1):
        lines.append(f"{index}. {label} - {value} {suffix}")
    if not lines:
        lines.append("- Sem registros para destacar.")
    return lines


def _format_date(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value.replace("Z", "")).strftime("%d/%m/%Y")
    except ValueError:
        return value[:10]


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0



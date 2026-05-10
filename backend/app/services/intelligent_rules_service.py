from __future__ import annotations

import json

from app.extensions import db
from app.models import AuditLog, ChecklistItem, MaintenanceSchedule, MaintenanceWorkOrder, Material, ResolutionPackage, SystemSetting


DEFAULT_INTELLIGENT_RULES = {
    "recurrence_window_days": 15,
    "recurrence_weight": 5,
    "critical_recurrence_threshold": 5,
    "reserve_high_quantity_minimum": 3,
    "reserve_high_multiplier": 2,
    "reserve_low_consumption_divisor": 3,
    "fallback_piece_strategy": "ITEM_PADRAO",
}


def _coerce_rule_value(key: str, value):
    if key == "fallback_piece_strategy":
        normalized = str(value or DEFAULT_INTELLIGENT_RULES[key]).strip().upper()
        return normalized or DEFAULT_INTELLIGENT_RULES[key]
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(DEFAULT_INTELLIGENT_RULES[key])
    if key in {"reserve_low_consumption_divisor", "reserve_high_multiplier", "critical_recurrence_threshold", "recurrence_window_days"}:
        return max(1, number)
    return max(0, number)


def _read_setting(key: str):
    row = SystemSetting.query.filter_by(key=key).first()
    if not row or row.value_json in {None, ""}:
        return DEFAULT_INTELLIGENT_RULES[key]
    try:
        raw = json.loads(row.value_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        raw = row.value_json
    return _coerce_rule_value(key, raw)


def get_intelligent_rules() -> dict:
    values = {key: _read_setting(key) for key in DEFAULT_INTELLIGENT_RULES}
    return {
        "rules": values,
        "defaults": dict(DEFAULT_INTELLIGENT_RULES),
    }


def update_intelligent_rules(payload: dict, *, user_id: int) -> dict:
    stored = {}
    for key in DEFAULT_INTELLIGENT_RULES:
        value = _coerce_rule_value(key, payload.get(key, DEFAULT_INTELLIGENT_RULES[key]))
        row = SystemSetting.query.filter_by(key=key).first()
        if not row:
            row = SystemSetting(key=key)
            db.session.add(row)
        row.value_json = json.dumps(value, ensure_ascii=False)
        row.updated_by_user_id = user_id
        stored[key] = value
    db.session.flush()
    return {
        "rules": stored,
        "defaults": dict(DEFAULT_INTELLIGENT_RULES),
    }


def get_rule_value(key: str):
    if key not in DEFAULT_INTELLIGENT_RULES:
        raise KeyError(key)
    return get_intelligent_rules()["rules"][key]


def build_compatibility_status() -> dict:
    schedules = MaintenanceSchedule.query.all()
    work_orders = MaintenanceWorkOrder.query.all()
    materials = Material.query.all()
    packages = ResolutionPackage.query.all()
    checklist_open = ChecklistItem.query.filter_by(status="NC").all()

    checklist_without_group = sum(
        1
        for row in checklist_open
        if not (row.item_principal and row.tipo_agrupamento and row.item_origem)
    )
    legacy_schedules = [row for row in schedules if row.source_origin_type() != "PACOTE_RESOLUCAO"]
    work_orders_without_package = [row for row in work_orders if not row.resolution_package_id]
    materials_without_movement = [row for row in materials if not row.movements]
    open_packages = [row for row in packages if str(row.status or "").upper() in {"ABERTO", "EM_MANUTENCAO"}]

    alerts = []
    if checklist_without_group:
        alerts.append("Há não conformidades antigas sem agrupamento completo. O sistema continua compatível, mas usa fallback.")
    if work_orders_without_package:
        alerts.append("Há ordens de serviço legadas sem pacote vinculado. A execução continua válida, mas sem vínculo completo.")
    if legacy_schedules:
        alerts.append("Há programações legadas vindas de fontes antigas. Elas continuam legíveis e utilizáveis.")
    if not alerts:
        alerts.append("Compatibilidade preservada. Os dados legados continuam legíveis e os novos fluxos entram de forma aditiva.")

    return {
        "status_geral": "COMPATIVEL",
        "resumo": {
            "nao_conformidades_abertas": len(checklist_open),
            "checklists_sem_agrupamento": checklist_without_group,
            "pacotes_abertos_ou_execucao": len(open_packages),
            "programacoes_legadas": len(legacy_schedules),
            "ordens_sem_pacote": len(work_orders_without_package),
            "materiais_sem_movimento": len(materials_without_movement),
        },
        "leituras": alerts,
    }


def build_homologation_status() -> dict:
    packages = ResolutionPackage.query.all()
    schedules = MaintenanceSchedule.query.all()
    work_orders = MaintenanceWorkOrder.query.all()
    exported_work_orders = AuditLog.query.filter_by(entity_type="MAINTENANCE_WORK_ORDER", action="EXPORT_PDF").count()

    item_packages = [row for row in packages if str(row.grouping_mode or "").upper() == "POR_ITEM"]
    equipment_packages = [row for row in packages if str(row.grouping_mode or "").upper() == "POR_EQUIPAMENTO"]
    package_schedules = [row for row in schedules if row.source_origin_type() == "PACOTE_RESOLUCAO"]
    work_orders_with_package = [row for row in work_orders if row.resolution_package_id]
    assigned_work_orders = [row for row in work_orders if row.assigned_mechanic_user_id]
    schedules_with_materials = [row for row in schedules if row.materials]
    schedules_with_blockers = [row for row in schedules if row.blocker_summary().get("materiais_bloqueados") or row.blocker_summary().get("ordens_bloqueadas")]

    scenarios = [
        {
            "cenario": "Pacote por item",
            "status": "COM_EVIDENCIA" if item_packages else "PRONTO_PARA_VALIDAR",
            "quantidade": len(item_packages),
            "leitura": "Agrupamento por item distinto pronto para uso na Central de Resolução.",
        },
        {
            "cenario": "Pacote por equipamento",
            "status": "COM_EVIDENCIA" if equipment_packages else "PRONTO_PARA_VALIDAR",
            "quantidade": len(equipment_packages),
            "leitura": "Agrupamento por equipamento pronto para consolidar várias NCs da mesma unidade.",
        },
        {
            "cenario": "Pacote enviado para manutenção",
            "status": "COM_EVIDENCIA" if package_schedules else "PRONTO_PARA_VALIDAR",
            "quantidade": len(package_schedules),
            "leitura": "A manutenção já consegue receber pacote como origem oficial da execução.",
        },
        {
            "cenario": "OS formal e PDF",
            "status": "COM_EVIDENCIA" if work_orders_with_package or exported_work_orders else "PRONTO_PARA_VALIDAR",
            "quantidade": len(work_orders_with_package),
            "leitura": "Ordens de serviço já nascem formais e podem ser exportadas em PDF rico.",
        },
        {
            "cenario": "Painel do mecânico",
            "status": "COM_EVIDENCIA" if assigned_work_orders else "PRONTO_PARA_VALIDAR",
            "quantidade": len(assigned_work_orders),
            "leitura": "O Web/Mobile já consegue entregar fila por mecânico com OS visível.",
        },
        {
            "cenario": "Materiais e bloqueios",
            "status": "COM_EVIDENCIA" if schedules_with_materials or schedules_with_blockers else "PRONTO_PARA_VALIDAR",
            "quantidade": len(schedules_with_materials),
            "leitura": "Peças, reservas e travas já conversam com programação e OS.",
        },
    ]

    ready = sum(1 for row in scenarios if row["status"] == "PRONTO_PARA_VALIDAR")
    evidenced = sum(1 for row in scenarios if row["status"] == "COM_EVIDENCIA")
    return {
        "status_geral": "PRONTO_PARA_HOMOLOGAR" if ready or evidenced else "SEM_BASE",
        "resumo": {
            "cenarios_total": len(scenarios),
            "cenarios_com_evidencia": evidenced,
            "cenarios_prontos_para_validar": ready,
            "pdfs_os_exportados": exported_work_orders,
        },
        "cenarios": scenarios,
    }

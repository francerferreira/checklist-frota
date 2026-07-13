from __future__ import annotations

import json

from sqlalchemy import case

from app.extensions import db
from app.models import AutomationExecution, EmergencyEvent, Material, MaintenanceWorkOrder, PreventivePlan, WorkOrderExecution
from app.services.audit_service import record_event
from app.services.availability_service import build_availability_overview
from app.services.pcm_service import build_backlog, plan_due_state
from app.utils.timezone import now_manaus_naive


OPEN_EMERGENCY_STATUSES = {"ABERTA", "TRIAGEM", "CONVERTIDA"}


def _average_hours(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _reliability_metrics() -> dict:
    executions = (
        WorkOrderExecution.query.join(MaintenanceWorkOrder)
        .filter(
            WorkOrderExecution.failure_started_at.isnot(None),
            WorkOrderExecution.repair_started_at.isnot(None),
            WorkOrderExecution.released_at.isnot(None),
        )
        .order_by(MaintenanceWorkOrder.vehicle_id.asc(), WorkOrderExecution.failure_started_at.asc())
        .all()
    )
    repair_hours, failure_intervals, previous_release_by_vehicle = [], [], {}
    rows_by_vehicle: dict[int, dict] = {}
    for execution in executions:
        order = execution.work_order
        if not order or execution.released_at < execution.repair_started_at:
            continue
        repair = (execution.released_at - execution.repair_started_at).total_seconds() / 3600
        repair_hours.append(repair)
        row = rows_by_vehicle.setdefault(
            order.vehicle_id,
            {"vehicle": order.vehicle.to_dict() if order.vehicle else None, "reparos": [], "intervalos": []},
        )
        row["reparos"].append(repair)
        previous_release = previous_release_by_vehicle.get(order.vehicle_id)
        if previous_release and execution.failure_started_at >= previous_release:
            interval = (execution.failure_started_at - previous_release).total_seconds() / 3600
            failure_intervals.append(interval)
            row["intervalos"].append(interval)
        previous_release_by_vehicle[order.vehicle_id] = execution.released_at
    by_vehicle = [
        {
            "vehicle": row["vehicle"],
            "mtbf_horas": _average_hours(row["intervalos"]),
            "mttr_horas": _average_hours(row["reparos"]),
            "falhas_comparaveis": len(row["intervalos"]),
            "reparos_concluidos": len(row["reparos"]),
        }
        for row in rows_by_vehicle.values()
    ]
    by_vehicle.sort(key=lambda item: ((item["mtbf_horas"] is None), item["mtbf_horas"] or 0))
    return {
        "mtbf_horas": _average_hours(failure_intervals),
        "mttr_horas": _average_hours(repair_hours),
        "falhas_comparaveis": len(failure_intervals),
        "reparos_concluidos": len(repair_hours),
        "por_equipamento": by_vehicle[:10],
    }


def list_automation_alerts(*, active_only: bool = False) -> list[dict]:
    query = AutomationExecution.query
    if active_only:
        query = query.filter(AutomationExecution.status.in_({"ATIVO", "RECONHECIDO"}))
    rows = query.order_by(
        case((AutomationExecution.severity == "CRITICA", 0), (AutomationExecution.severity == "ALTA", 1), else_=2),
        AutomationExecution.evaluated_at.desc(),
    ).all()
    return [row.to_dict() for row in rows]


def build_maintenance_intelligence_overview() -> dict:
    reliability = _reliability_metrics()
    availability = build_availability_overview()
    backlog = build_backlog()
    active_alerts = list_automation_alerts(active_only=True)
    low_stock = Material.query.filter(Material.ativo.is_(True), Material.quantidade_estoque <= Material.estoque_minimo).count()
    due_plans = [plan for plan in PreventivePlan.query.filter_by(status="ATIVO").all() if plan_due_state(plan).get("due")]
    return {
        "confiabilidade": reliability,
        "disponibilidade": availability.get("summary") or {},
        "backlog": {
            "total": len(backlog),
            "vencidas": sum(1 for item in backlog if item.get("overdue")),
            "materiais_bloqueados": sum(1 for item in backlog if (item.get("blockers") or {}).get("materiais_bloqueados")),
        },
        "pcm": {"preventivas_vencendo_ou_vencidas": len(due_plans)},
        "suprimentos": {"materiais_abaixo_minimo": int(low_stock or 0)},
        "automacoes": {
            "alertas_ativos": len(active_alerts),
            "alertas_criticos": sum(1 for item in active_alerts if item.get("severity") == "CRITICA"),
            "alertas": active_alerts[:10],
        },
    }


def _automation_candidates() -> list[dict]:
    candidates = []
    for emergency in EmergencyEvent.query.filter(EmergencyEvent.severity == "CRITICA", EmergencyEvent.status.in_(OPEN_EMERGENCY_STATUSES)).all():
        candidates.append({"rule_code": "EMERGENCIA_CRITICA_ABERTA", "entity_type": "EMERGENCY_EVENT", "entity_id": emergency.id, "severity": "CRITICA", "message": f"Emergencial critica {emergency.event_number} permanece aberta: {emergency.title}.", "context": {"event_number": emergency.event_number, "vehicle_id": emergency.vehicle_id}})
    for plan in PreventivePlan.query.filter_by(status="ATIVO").all():
        due = plan_due_state(plan)
        if due.get("overdue"):
            candidates.append({"rule_code": "PREVENTIVA_VENCIDA", "entity_type": "PREVENTIVE_PLAN", "entity_id": plan.id, "severity": "ALTA" if plan.priority in {"ALTA", "CRITICA"} else "MEDIA", "message": f"Preventiva {plan.code} esta vencida para {plan.vehicle.frota if plan.vehicle else 'equipamento'}.", "context": {"plan_code": plan.code, "vehicle_id": plan.vehicle_id, "priority": plan.priority}})
    for material in Material.query.filter(Material.ativo.is_(True), Material.quantidade_estoque <= Material.estoque_minimo).all():
        candidates.append({"rule_code": "ESTOQUE_ABAIXO_MINIMO", "entity_type": "MATERIAL", "entity_id": material.id, "severity": "ALTA" if material.quantidade_estoque == 0 else "MEDIA", "message": f"Material {material.referencia} esta abaixo do estoque minimo ({material.quantidade_estoque}/{material.estoque_minimo}).", "context": {"referencia": material.referencia, "saldo": material.quantidade_estoque, "minimo": material.estoque_minimo}})
    return candidates


def evaluate_automation_rules(*, user_id: int) -> dict:
    now, candidates, active_keys, created = now_manaus_naive(), _automation_candidates(), set(), 0
    for candidate in candidates:
        dedup_key = f"{candidate['rule_code']}:{candidate['entity_type']}:{candidate['entity_id']}"
        active_keys.add(dedup_key)
        row = AutomationExecution.query.filter_by(dedup_key=dedup_key).first()
        if not row:
            context = candidate["context"]
            row = AutomationExecution(
                dedup_key=dedup_key,
                created_by_user_id=user_id,
                context_json=json.dumps(context, ensure_ascii=False),
                rule_code=candidate["rule_code"],
                entity_type=candidate["entity_type"],
                entity_id=candidate["entity_id"],
                severity=candidate["severity"],
                message=candidate["message"],
            )
            db.session.add(row)
            db.session.flush()
            record_event(user_id=user_id, entity_type="AUTOMATION_EXECUTION", entity_id=row.id, action="ALERT_CREATED", new_value=row.message)
            created += 1
        else:
            row.severity, row.message, row.context_json, row.evaluated_at = candidate["severity"], candidate["message"], json.dumps(candidate["context"], ensure_ascii=False), now
            if row.status == "ENCERRADO":
                row.status, row.acknowledged_at, row.acknowledged_by_user_id = "ATIVO", None, None
    stale_rows = AutomationExecution.query.filter(AutomationExecution.status.in_({"ATIVO", "RECONHECIDO"}), ~AutomationExecution.dedup_key.in_(active_keys or {"__NONE__"})).all()
    for row in stale_rows:
        row.status, row.evaluated_at = "ENCERRADO", now
        record_event(user_id=user_id, entity_type="AUTOMATION_EXECUTION", entity_id=row.id, action="ALERT_CLOSED", old_value=row.message, new_value="Condicao nao identificada na nova avaliacao.")
    db.session.commit()
    return {"avaliados": len(candidates), "novos_alertas": created, "encerrados": len(stale_rows), "alertas": list_automation_alerts(active_only=True)}


def acknowledge_automation_alert(alert_id: int, *, user_id: int) -> AutomationExecution:
    row = db.session.get(AutomationExecution, alert_id)
    if not row:
        raise LookupError("Alerta de automacao nao encontrado.")
    if row.status == "ENCERRADO":
        raise ValueError("Alerta encerrado nao pode ser reconhecido.")
    row.status, row.acknowledged_at, row.acknowledged_by_user_id = "RECONHECIDO", now_manaus_naive(), user_id
    record_event(user_id=user_id, entity_type="AUTOMATION_EXECUTION", entity_id=row.id, action="ALERT_ACKNOWLEDGED", old_value="ATIVO", new_value=row.message)
    db.session.commit()
    return row

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.models import MaintenanceWorkOrder, MaintenanceWorkOrderCost, SystemSetting
from app.utils.timezone import now_manaus_naive


GOVERNANCE_TARGETS_KEY = "maintenance_governance_targets"
COST_CATEGORIES = ("PECA", "MAO_DE_OBRA", "SERVICO_EXTERNO")
TARGET_LIMITS = {
    "availability_min_percent": (0, 100),
    "mttr_max_hours": (0, None),
    "mtbf_min_hours": (0, None),
    "preventive_compliance_min_percent": (0, 100),
}


def _clean_text(value, field: str, *, required: bool = False, limit: int = 160) -> str | None:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"Informe {field}.")
    if len(text) > limit:
        raise ValueError(f"{field.capitalize()} deve ter no maximo {limit} caracteres.")
    return text or None


def _parse_amount(value) -> Decimal:
    try:
        amount = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Informe um valor de custo valido.") from None
    if amount < 0:
        raise ValueError("O valor do custo nao pode ser negativo.")
    return amount.quantize(Decimal("0.01"))


def _parse_occurred_at(value) -> datetime:
    if value in {None, ""}:
        return now_manaus_naive()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        raise ValueError("Data do custo invalida.") from None


def _cost_summary(costs: list[MaintenanceWorkOrderCost]) -> dict:
    totals = {category: Decimal("0.00") for category in COST_CATEGORIES}
    for cost in costs:
        totals[cost.category] = totals.get(cost.category, Decimal("0.00")) + Decimal(cost.amount or 0)
    return {
        "total": float(sum(totals.values(), Decimal("0.00"))),
        "by_category": {category: float(total) for category, total in totals.items()},
        "records": len(costs),
    }


def get_work_order_governance(work_order_id: int) -> dict:
    order = db.session.get(MaintenanceWorkOrder, work_order_id)
    if not order:
        raise LookupError("Ordem de servico nao encontrada.")
    costs = sorted(order.cost_records, key=lambda item: (item.occurred_at, item.id), reverse=True)
    return {
        "work_order": order.to_dict(),
        "classification": {
            "failure_cause": order.failure_cause,
            "affected_component": order.affected_component,
            "work_shift": order.work_shift,
        },
        "costs": [item.to_dict() for item in costs],
        "cost_summary": _cost_summary(costs),
        "cost_categories": list(COST_CATEGORIES),
    }


def update_work_order_classification(work_order_id: int, payload: dict) -> MaintenanceWorkOrder:
    order = db.session.get(MaintenanceWorkOrder, work_order_id)
    if not order:
        raise LookupError("Ordem de servico nao encontrada.")
    order.failure_cause = _clean_text(payload.get("failure_cause"), "a causa da falha")
    order.affected_component = _clean_text(payload.get("affected_component"), "o componente afetado")
    order.work_shift = _clean_text(payload.get("work_shift"), "o turno", limit=30)
    db.session.flush()
    return order


def create_work_order_cost(work_order_id: int, payload: dict, *, user_id: int) -> MaintenanceWorkOrderCost:
    order = db.session.get(MaintenanceWorkOrder, work_order_id)
    if not order:
        raise LookupError("Ordem de servico nao encontrada.")
    category = str(payload.get("category") or "").strip().upper()
    if category not in COST_CATEGORIES:
        raise ValueError("Categoria de custo invalida.")
    cost = MaintenanceWorkOrderCost(
        work_order_id=order.id,
        category=category,
        description=_clean_text(payload.get("description"), "a descricao", required=True, limit=200),
        supplier_name=_clean_text(payload.get("supplier_name"), "o fornecedor"),
        affected_component=_clean_text(payload.get("affected_component"), "o componente afetado"),
        amount=_parse_amount(payload.get("amount")),
        occurred_at=_parse_occurred_at(payload.get("occurred_at")),
        notes=_clean_text(payload.get("notes"), "a observacao", limit=2000),
        recorded_by_user_id=user_id,
    )
    db.session.add(cost)
    db.session.flush()
    return cost


def delete_work_order_cost(work_order_id: int, cost_id: int) -> dict:
    cost = MaintenanceWorkOrderCost.query.filter_by(id=cost_id, work_order_id=work_order_id).first()
    if not cost:
        raise LookupError("Lancamento de custo nao encontrado para esta ordem de servico.")
    data = cost.to_dict()
    db.session.delete(cost)
    db.session.flush()
    return data


def _empty_targets() -> dict:
    return {key: None for key in TARGET_LIMITS}


def get_governance_targets() -> dict:
    row = SystemSetting.query.filter_by(key=GOVERNANCE_TARGETS_KEY).first()
    targets = _empty_targets()
    if row and row.value_json:
        try:
            stored = json.loads(row.value_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            stored = {}
        if isinstance(stored, dict):
            for key in targets:
                if stored.get(key) is not None:
                    targets[key] = stored[key]
    return {
        "targets": targets,
        "configured": any(value is not None for value in targets.values()),
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        "updated_by": row.updated_by.to_dict() if row and row.updated_by else None,
    }


def _parse_target_value(key: str, value) -> float | None:
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Meta invalida para {key}.") from None
    minimum, maximum = TARGET_LIMITS[key]
    if number < minimum or (maximum is not None and number > maximum):
        maximum_label = f" e {maximum}" if maximum is not None else ""
        raise ValueError(f"Meta {key} deve ficar entre {minimum}{maximum_label}.")
    return round(number, 2)


def update_governance_targets(payload: dict, *, user_id: int) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Envie as metas em formato valido.")
    current = get_governance_targets()["targets"]
    for key in TARGET_LIMITS:
        if key in payload:
            current[key] = _parse_target_value(key, payload.get(key))
    row = SystemSetting.query.filter_by(key=GOVERNANCE_TARGETS_KEY).first()
    if not row:
        row = SystemSetting(key=GOVERNANCE_TARGETS_KEY)
        db.session.add(row)
    row.value_json = json.dumps(current, ensure_ascii=False)
    row.updated_by_user_id = user_id
    db.session.flush()
    return get_governance_targets()

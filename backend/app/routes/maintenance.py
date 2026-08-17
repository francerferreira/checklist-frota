from __future__ import annotations

import re
import tempfile
from io import BytesIO
from pathlib import Path

from datetime import datetime

from flask import Blueprint, g, request, send_file
from sqlalchemy.orm import lazyload

from app.extensions import db
from app.models import MaintenanceSchedule, MaintenanceScheduleItem
from app.services.auth_service import auth_required, user_has_management_access, user_has_mechanic_workspace_access
from app.services.audit_service import record_event
from app.services.maintenance_service import (
    build_work_order_report_payload,
    build_maintenance_overview,
    build_maintenance_report_payload,
    create_maintenance_schedule,
    link_schedule_material,
    mechanic_items_for_user,
    program_maintenance_schedule,
    reprogram_schedule_item,
    suggest_material_for_schedule,
    suggest_schedule_window,
    suggest_mechanic_for_payload,
    update_schedule_item,
)
from app.services.maintenance_pdf_export_service import export_maintenance_pdf
from app.services.maintenance_governance_service import (
    create_work_order_cost,
    delete_work_order_cost,
    get_governance_targets,
    get_work_order_governance,
    update_work_order_budget,
    update_governance_targets,
    update_work_order_classification,
)
from app.utils.responses import api_response

bp = Blueprint("maintenance", __name__)


def _guard_management_access():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar manutenção.", status_code=403)
    return None


def _guard_workspace_access():
    if not user_has_mechanic_workspace_access(g.current_user):
        return api_response(False, error="Somente admin, gestor ou mecânico podem acessar este módulo.", status_code=403)
    return None


def _maintenance_family_arg():
    value = str(request.args.get("familia") or "").strip().lower()
    if not value:
        return None, None
    if len(value) > 20 or not re.fullmatch(r"[a-z0-9_-]+", value):
        return None, api_response(False, error="Família de manutenção inválida.", status_code=400)
    return value, None


@bp.get("/manutencao/visao")
@auth_required
def maintenance_overview():
    denied = _guard_workspace_access()
    if denied:
        return denied

    year = request.args.get("ano", type=int)
    month = request.args.get("mes", type=int)
    family, family_error = _maintenance_family_arg()
    if family_error:
        return family_error
    mechanic_id = request.args.get("mecanico_id", type=int)
    exclude_checklist = request.args.get("excluir_checklist", "false").lower() in {"1", "true", "sim"}
    if g.current_user.tipo == "mecanico":
        mechanic_id = g.current_user.id
    return api_response(
        True,
        data=build_maintenance_overview(
            year=year,
            month=month,
            assigned_to_user_id=mechanic_id,
            family=family,
            exclude_checklist=exclude_checklist,
        ),
    )


@bp.get("/manutencao/mecanico")
@auth_required
def mechanic_maintenance_items():
    denied = _guard_workspace_access()
    if denied:
        return denied

    mechanic_id = g.current_user.id if g.current_user.tipo == "mecanico" else request.args.get("mecanico_id", type=int)
    if not mechanic_id:
        return api_response(False, error="Informe o mecânico para consulta.", status_code=400)
    items = mechanic_items_for_user(mechanic_id)
    return api_response(True, data=[item.to_dict() for item in items])


@bp.get("/manutencao/programacoes")
@auth_required
def list_maintenance_schedules():
    denied = _guard_workspace_access()
    if denied:
        return denied

    query = MaintenanceSchedule.query.options(lazyload("*")).order_by(MaintenanceSchedule.created_at.desc())
    schedules = query.all()
    if g.current_user.tipo == "mecanico":
        schedules = [
            schedule for schedule in schedules
            if schedule.assigned_mechanic_user_id == g.current_user.id
            or any(item.assigned_mechanic_user_id == g.current_user.id for item in schedule.items)
        ]
    return api_response(True, data=[schedule.to_dict(include_items=True, include_materials=True) for schedule in schedules])


@bp.get("/manutencao/relatorio/pdf")
@auth_required
def maintenance_pdf_report():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = build_maintenance_report_payload(
        report_type=request.args.get("tipo") or "mensal",
        year=request.args.get("ano", type=int),
        month=request.args.get("mes", type=int),
        mechanic_id=request.args.get("mecanico_id", type=int),
        vehicle_id=request.args.get("vehicle_id", type=int),
    )
    tmp = tempfile.NamedTemporaryFile(prefix="manutencao_", suffix=".pdf", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    export_maintenance_pdf(payload, tmp_path, generated_by=g.current_user.nome or g.current_user.login)
    pdf_buffer = BytesIO(tmp_path.read_bytes())
    tmp_path.unlink(missing_ok=True)
    pdf_buffer.seek(0)
    record_event(
        user_id=g.current_user.id,
        entity_type="MAINTENANCE_REPORT",
        entity_id=0,
        action="EXPORT_PDF",
        new_value=str({"tipo": request.args.get("tipo") or "mensal", "ano": request.args.get("ano"), "mes": request.args.get("mes")}),
    )
    db.session.commit()
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=payload["filename"],
    )


@bp.get("/manutencao/os/<int:work_order_id>/pdf")
@auth_required
def maintenance_work_order_pdf_report(work_order_id: int):
    denied = _guard_workspace_access()
    if denied:
        return denied

    item = MaintenanceScheduleItem.query.filter(MaintenanceScheduleItem.work_order.has(id=work_order_id)).first()
    if not item or not item.work_order:
        return api_response(False, error="Ordem de serviço não encontrada.", status_code=404)
    if g.current_user.tipo == "mecanico":
        assigned_ids = {item.assigned_mechanic_user_id, item.schedule.assigned_mechanic_user_id if item.schedule else None, item.work_order.assigned_mechanic_user_id}
        if g.current_user.id not in assigned_ids:
            return api_response(False, error="Esta ordem de serviço não foi direcionada para você.", status_code=403)

    payload = build_work_order_report_payload(work_order_id)
    tmp = tempfile.NamedTemporaryFile(prefix="ordem_servico_", suffix=".pdf", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    export_maintenance_pdf(payload, tmp_path, generated_by=g.current_user.nome or g.current_user.login)
    pdf_buffer = BytesIO(tmp_path.read_bytes())
    tmp_path.unlink(missing_ok=True)
    pdf_buffer.seek(0)
    record_event(
        user_id=g.current_user.id,
        entity_type="MAINTENANCE_WORK_ORDER",
        entity_id=work_order_id,
        action="EXPORT_PDF",
        new_value=str({"ordem_servico": payload.get("filename")}),
    )
    db.session.commit()
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=payload["filename"],
    )


@bp.get("/manutencao/os/<int:work_order_id>/governanca")
@auth_required
def maintenance_work_order_governance(work_order_id: int):
    denied = _guard_management_access()
    if denied:
        return denied
    try:
        return api_response(True, data=get_work_order_governance(work_order_id))
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)


@bp.put("/manutencao/os/<int:work_order_id>/classificacao")
@auth_required
def update_maintenance_work_order_classification(work_order_id: int):
    denied = _guard_management_access()
    if denied:
        return denied
    try:
        order = update_work_order_classification(work_order_id, request.get_json(silent=True) or {})
        record_event(
            user_id=g.current_user.id,
            entity_type="MAINTENANCE_WORK_ORDER",
            entity_id=order.id,
            action="GOVERNANCE_CLASSIFICATION_UPDATED",
            new_value=str({
                "failure_cause": order.failure_cause,
                "affected_component": order.affected_component,
                "work_shift": order.work_shift,
            }),
        )
        db.session.commit()
        return api_response(True, data=get_work_order_governance(order.id))
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)


@bp.put("/manutencao/os/<int:work_order_id>/orcamento")
@auth_required
def update_maintenance_work_order_budget(work_order_id: int):
    denied = _guard_management_access()
    if denied:
        return denied
    try:
        order = update_work_order_budget(work_order_id, request.get_json(silent=True) or {})
        record_event(
            user_id=g.current_user.id,
            entity_type="MAINTENANCE_WORK_ORDER",
            entity_id=order.id,
            action="BUDGET_UPDATED",
            new_value=str({"amount": float(order.budget_amount), "notes": order.budget_notes}),
        )
        db.session.commit()
        return api_response(True, data=get_work_order_governance(order.id))
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)


@bp.post("/manutencao/os/<int:work_order_id>/custos")
@auth_required
def create_maintenance_work_order_cost(work_order_id: int):
    denied = _guard_management_access()
    if denied:
        return denied
    try:
        cost = create_work_order_cost(work_order_id, request.get_json(silent=True) or {}, user_id=g.current_user.id)
        record_event(
            user_id=g.current_user.id,
            entity_type="MAINTENANCE_WORK_ORDER_COST",
            entity_id=cost.id,
            action="COST_RECORDED",
            new_value=str({
                "work_order_id": cost.work_order_id,
                "category": cost.category,
                "amount": float(cost.amount),
                "supplier_name": cost.supplier_name,
            }),
        )
        db.session.commit()
        return api_response(True, data=get_work_order_governance(work_order_id), status_code=201)
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)


@bp.delete("/manutencao/os/<int:work_order_id>/custos/<int:cost_id>")
@auth_required
def delete_maintenance_work_order_cost(work_order_id: int, cost_id: int):
    denied = _guard_management_access()
    if denied:
        return denied
    try:
        cost = delete_work_order_cost(work_order_id, cost_id)
        record_event(
            user_id=g.current_user.id,
            entity_type="MAINTENANCE_WORK_ORDER_COST",
            entity_id=cost_id,
            action="COST_DELETED",
            old_value=str({
                "work_order_id": work_order_id,
                "category": cost["category"],
                "amount": cost["amount"],
                "supplier_name": cost["supplier_name"],
            }),
        )
        db.session.commit()
        return api_response(True, data=get_work_order_governance(work_order_id))
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)


@bp.get("/manutencao/governanca/metas")
@auth_required
def maintenance_governance_targets():
    denied = _guard_management_access()
    if denied:
        return denied
    return api_response(True, data=get_governance_targets())


@bp.put("/manutencao/governanca/metas")
@auth_required
def update_maintenance_governance_targets():
    denied = _guard_management_access()
    if denied:
        return denied
    try:
        data = update_governance_targets(request.get_json(silent=True) or {}, user_id=g.current_user.id)
        record_event(
            user_id=g.current_user.id,
            entity_type="SYSTEM_SETTING",
            entity_id=0,
            action="MAINTENANCE_GOVERNANCE_TARGETS_UPDATED",
            new_value=str(data["targets"]),
        )
        db.session.commit()
        return api_response(True, data=data)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)


@bp.post("/manutencao/programacoes")
@auth_required
def create_maintenance_schedule_route():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    try:
        schedule = create_maintenance_schedule(payload, created_by_user_id=g.current_user.id)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=schedule.to_dict(include_items=True, include_materials=True), status_code=201)


@bp.post("/manutencao/sugestao-responsavel")
@auth_required
def suggest_maintenance_mechanic_route():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    suggestion = suggest_mechanic_for_payload(payload)
    return api_response(True, data=suggestion)


@bp.post("/manutencao/sugestao-agenda")
@auth_required
def suggest_maintenance_schedule_window_route():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    try:
        suggestion = suggest_schedule_window(payload)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=suggestion)


@bp.get("/manutencao/programacoes/<int:schedule_id>/sugestao-peca")
@auth_required
def suggest_maintenance_material_route(schedule_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    suggestion = suggest_material_for_schedule(schedule_id)
    return api_response(True, data=suggestion)


@bp.post("/manutencao/programacoes/sincronizar-nc")
@auth_required
def sync_nc_to_maintenance_route():
    denied = _guard_management_access()
    if denied:
        return denied
    return api_response(
        False,
        error="Importação direta de NC para manutenção foi desativada. Use a Central de Resolução para criar pacote e depois enviar para a manutenção.",
        status_code=409,
    )


@bp.post("/manutencao/programacoes/<int:schedule_id>/materiais")
@auth_required
def link_material_to_schedule_route(schedule_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    try:
        link = link_schedule_material(schedule_id, payload, user_id=g.current_user.id)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=link.to_dict(), status_code=201)


@bp.put("/manutencao/programacoes/<int:schedule_id>/cronograma")
@auth_required
def program_maintenance_schedule_route(schedule_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    try:
        schedule = program_maintenance_schedule(schedule_id, payload, user_id=g.current_user.id)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=schedule.to_dict(include_items=True, include_materials=True))


@bp.put("/manutencao/itens/<int:item_id>/reprogramar")
@auth_required
def reprogram_maintenance_item_route(item_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    try:
        item = reprogram_schedule_item(item_id, payload, user=g.current_user)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=item.to_dict())


@bp.put("/manutencao/itens/<int:item_id>")
@auth_required
def update_maintenance_item_route(item_id: int):
    denied = _guard_workspace_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    if g.current_user.tipo == "mecanico":
        item = MaintenanceScheduleItem.query.get_or_404(item_id)
        if item.assigned_mechanic_user_id not in {None, g.current_user.id} and (
            not item.schedule or item.schedule.assigned_mechanic_user_id not in {None, g.current_user.id}
        ):
            return api_response(False, error="Esta manutenção não foi direcionada para você.", status_code=403)

    try:
        item = update_schedule_item(item_id, payload, user=g.current_user)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=item.to_dict())

from __future__ import annotations

import tempfile
from io import BytesIO
from pathlib import Path

from datetime import datetime

from flask import Blueprint, g, request, send_file

from app.models import MaintenanceSchedule, MaintenanceScheduleItem
from app.services.auth_service import auth_required, user_has_management_access, user_has_mechanic_workspace_access
from app.services.maintenance_service import (
    build_maintenance_overview,
    build_maintenance_report_payload,
    create_maintenance_schedule,
    link_schedule_material,
    mechanic_items_for_user,
    program_maintenance_schedule,
    reprogram_schedule_item,
    sync_checklist_non_conformities,
    update_schedule_item,
)
from app.services.maintenance_pdf_export_service import export_maintenance_pdf
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


@bp.get("/manutencao/visao")
@auth_required
def maintenance_overview():
    denied = _guard_workspace_access()
    if denied:
        return denied

    year = request.args.get("ano", type=int)
    month = request.args.get("mes", type=int)
    mechanic_id = request.args.get("mecanico_id", type=int)
    if g.current_user.tipo == "mecanico":
        mechanic_id = g.current_user.id
    return api_response(True, data=build_maintenance_overview(year=year, month=month, assigned_to_user_id=mechanic_id))


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

    query = MaintenanceSchedule.query.order_by(MaintenanceSchedule.created_at.desc())
    schedules = query.all()
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
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=payload["filename"],
    )


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


@bp.post("/manutencao/programacoes/sincronizar-nc")
@auth_required
def sync_nc_to_maintenance_route():
    denied = _guard_management_access()
    if denied:
        return denied

    schedules = sync_checklist_non_conformities()
    return api_response(True, data={"updated": len(schedules)})


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

from datetime import datetime, time
from flask import Blueprint, request
from sqlalchemy import func
from app.extensions import db
from app.models import ChecklistItem, Vehicle, Checklist
from app.services.auth_service import auth_required
from app.services.report_service import build_dashboard_summary, build_productivity_report
from app.utils.responses import api_response
from app.utils.filters import apply_item_search
from app.routes.non_conformities import NCStatus

bp = Blueprint("reports", __name__, url_prefix="/relatorios")

def _parse_date(value: str | None, end_of_day: bool = False):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip())
        if len(str(value).strip()) <= 10:
            return datetime.combine(dt.date(), time.max if end_of_day else time.min)
        return dt
    except ValueError:
        return None


@bp.get("/dashboard")
@auth_required
def get_dashboard_report():
    """Resumo executivo do dashboard (mantido para desktop e web)."""
    return api_response(True, data=build_dashboard_summary())


@bp.get("/produtividade")
@auth_required
def get_productivity_dashboard():
    """Relatório consolidado de produtividade por usuário."""
    return api_response(True, data=build_productivity_report())

@bp.get("/macro")
@auth_required
def get_macro_report():
    """Relatório macro: consolidado agrupado por nome do item (Ponto 7: Métricas)."""
    query = db.session.query(
        ChecklistItem.item_nome,
        func.count(ChecklistItem.id).label("total_nc"),
        func.sum(func.cast(ChecklistItem.resolvido, db.Integer)).label("resolvidas")
    ).filter(ChecklistItem.status == NCStatus.TYPE_NC)

    modulo = request.args.get("modulo")
    if modulo in ("cavalo", "carreta"):
        query = query.join(Checklist).join(Vehicle).filter(Vehicle.tipo == modulo)

    results = query.group_by(ChecklistItem.item_nome).order_by(func.count(ChecklistItem.id).desc()).all()

    data = [{
        "item_nome": r.item_nome,
        "total_nc": r.total_nc,
        "resolvidas": int(r.resolvidas or 0),
        "abertas": r.total_nc - int(r.resolvidas or 0)
    } for r in results]

    return api_response(True, data=data)

@bp.get("/micro")
@auth_required
def get_micro_report():
    """Relatório micro: ranking de equipamentos com mais ocorrências."""
    query = db.session.query(
        Vehicle.id.label("vehicle_id"),
        Vehicle.frota,
        Vehicle.placa,
        Vehicle.modelo,
        Vehicle.tipo,
        func.count(ChecklistItem.id).label("total_nc"),
        func.max(Checklist.created_at).label("ultimo_checklist")
    ).join(Checklist, Checklist.vehicle_id == Vehicle.id)\
     .outerjoin(ChecklistItem, (ChecklistItem.checklist_id == Checklist.id) & (ChecklistItem.status == NCStatus.TYPE_NC))

    if request.args.get("ativos") == "true":
        query = query.filter(Vehicle.ativo == True)

    results = query.group_by(Vehicle.id).order_by(func.count(ChecklistItem.id).desc()).all()

    data = [{
        "vehicle_id": r.vehicle_id,
        "frota": r.frota,
        "placa": r.placa,
        "modelo": r.modelo,
        "tipo": r.tipo,
        "total_nc": r.total_nc,
        "ultimo_checklist": r.ultimo_checklist.isoformat() if r.ultimo_checklist else None
    } for r in results]

    return api_response(True, data=data)

@bp.get("/item")
@auth_required
def get_item_report():
    """Consulta detalhada de NCs usando o filtro centralizado."""
    query = ChecklistItem.query.join(Checklist).join(Vehicle).filter(ChecklistItem.status == NCStatus.TYPE_NC)

    # Uso da lógica centralizada de busca
    query = apply_item_search(query, ChecklistItem, request.args.get("item"))

    nc_status = request.args.get("nc_status")
    if nc_status == "abertas":
        query = query.filter(ChecklistItem.resolvido == False)
    elif nc_status == "resolvidas":
        query = query.filter(ChecklistItem.resolvido == True)

    modulo = request.args.get("modulo")
    if modulo in ("cavalo", "carreta"):
        query = query.filter(Vehicle.tipo == modulo)

    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"), end_of_day=True)
    data_base = request.args.get("data_base", "criacao")
    date_col = ChecklistItem.data_resolucao if data_base == "resolucao" else ChecklistItem.created_at

    if date_from:
        query = query.filter(date_col >= date_from)
    if date_to:
        query = query.filter(date_col <= date_to)

    results = query.order_by(ChecklistItem.created_at.desc()).all()
    return api_response(True, data=[item.to_dict() for item in results])

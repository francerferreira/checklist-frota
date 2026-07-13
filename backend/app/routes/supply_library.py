from flask import Blueprint, g, request

from app.extensions import db
from app.services.auth_service import auth_required, user_has_management_access
from app.services.supply_library_service import (
    adjust_warehouse_stock, create_technical_document, create_warehouse, initialize_warehouse_stock,
    list_technical_documents, list_warehouse_stocks, list_warehouses, reserve_warehouse_material,
    set_material_family_applications, update_technical_document, update_warehouse,
)
from app.utils.responses import api_response


bp = Blueprint("supply_library", __name__)


def _guard_management():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar este módulo.", status_code=403)


def _run(action, *, status_code=200):
    try:
        return api_response(True, data=action(), status_code=status_code)
    except LookupError as exc:
        db.session.rollback(); return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        db.session.rollback(); return api_response(False, error=str(exc), status_code=400)


@bp.get("/suprimentos/depositos")
@auth_required
def warehouse_list():
    return api_response(True, data=list_warehouses())


@bp.post("/suprimentos/depositos")
@auth_required
def warehouse_create():
    denied = _guard_management()
    if denied: return denied
    return _run(lambda: create_warehouse(request.get_json(silent=True) or {}).to_dict(), status_code=201)


@bp.put("/suprimentos/depositos/<int:warehouse_id>")
@auth_required
def warehouse_update(warehouse_id: int):
    denied = _guard_management()
    if denied: return denied
    return _run(lambda: update_warehouse(warehouse_id, request.get_json(silent=True) or {}).to_dict())


@bp.get("/suprimentos/estoques")
@auth_required
def warehouse_stock_list():
    return api_response(True, data=list_warehouse_stocks(request.args.get("warehouse_id", type=int)))


@bp.post("/suprimentos/estoques")
@auth_required
def warehouse_stock_initialize():
    denied = _guard_management()
    if denied: return denied
    return _run(lambda: initialize_warehouse_stock(request.get_json(silent=True) or {}).to_dict(), status_code=201)


@bp.post("/suprimentos/estoques/<int:stock_id>/movimentos")
@auth_required
def warehouse_stock_adjust(stock_id: int):
    denied = _guard_management()
    if denied: return denied
    return _run(lambda: adjust_warehouse_stock(stock_id, request.get_json(silent=True) or {}, user_id=g.current_user.id).to_dict())


@bp.put("/materiais/<int:material_id>/familias")
@auth_required
def material_family_application(material_id: int):
    denied = _guard_management()
    if denied: return denied
    return _run(lambda: set_material_family_applications(material_id, request.get_json(silent=True) or {}))


@bp.get("/suprimentos/reservas")
@auth_required
def warehouse_reservations():
    from app.models import WarehouseReservation
    return api_response(True, data=[row.to_dict() for row in WarehouseReservation.query.order_by(WarehouseReservation.created_at.desc()).all()])


@bp.post("/suprimentos/reservas")
@auth_required
def warehouse_reservation_create():
    denied = _guard_management()
    if denied: return denied
    return _run(lambda: reserve_warehouse_material(request.get_json(silent=True) or {}, user_id=g.current_user.id).to_dict(), status_code=201)


@bp.get("/biblioteca-tecnica")
@auth_required
def technical_document_list():
    vehicle_id = request.args.get("vehicle_id", type=int)
    include_archived = request.args.get("incluir_arquivados", "false").lower() == "true"
    if include_archived and not user_has_management_access(g.current_user):
        return api_response(False, error="Somente gestão consulta documentos arquivados.", status_code=403)
    return _run(lambda: list_technical_documents(vehicle_id=vehicle_id, include_archived=include_archived))


@bp.post("/biblioteca-tecnica")
@auth_required
def technical_document_create():
    denied = _guard_management()
    if denied: return denied
    return _run(lambda: create_technical_document(request.get_json(silent=True) or {}, g.current_user.id).to_dict(), status_code=201)


@bp.put("/biblioteca-tecnica/<int:document_id>")
@auth_required
def technical_document_update(document_id: int):
    denied = _guard_management()
    if denied: return denied
    return _run(lambda: update_technical_document(document_id, request.get_json(silent=True) or {}).to_dict())

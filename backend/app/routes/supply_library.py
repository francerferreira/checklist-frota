from flask import Blueprint, g, request

from app.extensions import db
from app.services.auth_service import auth_required, user_has_management_access, user_has_mechanic_workspace_access
from app.services.audit_service import record_event
from app.services.supply_library_service import (
    adjust_warehouse_stock, create_technical_document, create_warehouse, create_warehouse_location, create_warehouse_transfer, initialize_warehouse_stock, update_warehouse_location,
    issue_mmp_stock, list_mmp_stocks, list_technical_documents, list_warehouse_locations, list_warehouse_stocks, list_warehouse_transfers, list_warehouses, lookup_mmp_qr, reserve_warehouse_material,
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
    search = str(request.args.get("q") or "").strip().lower()
    status = str(request.args.get("status") or "").strip().upper()
    rows = list_warehouses()
    if search:
        rows = [row for row in rows if search in f"{row.get('code', '')} {row.get('name', '')} {row.get('location', '')}".lower()]
    if status in {"ATIVO", "INATIVO"}:
        rows = [row for row in rows if bool(row.get("active")) is (status == "ATIVO")]
    return api_response(True, data=rows)


@bp.post("/suprimentos/depositos")
@auth_required
def warehouse_create():
    denied = _guard_management()
    if denied: return denied
    def action():
        row = create_warehouse(request.get_json(silent=True) or {})
        record_event(user_id=g.current_user.id, entity_type="WAREHOUSE", entity_id=row.id, action="CREATED", new_value=row.to_dict())
        db.session.commit()
        return row.to_dict()
    return _run(action, status_code=201)


@bp.put("/suprimentos/depositos/<int:warehouse_id>")
@auth_required
def warehouse_update(warehouse_id: int):
    denied = _guard_management()
    if denied: return denied
    def action():
        row = update_warehouse(warehouse_id, request.get_json(silent=True) or {})
        record_event(user_id=g.current_user.id, entity_type="WAREHOUSE", entity_id=row.id, action="UPDATED", new_value=row.to_dict())
        db.session.commit()
        return row.to_dict()
    return _run(action)


@bp.get("/suprimentos/depositos/<int:warehouse_id>/historico")
@auth_required
def warehouse_history(warehouse_id: int):
    """Retorna saldos, locais e transferências relacionadas ao depósito."""
    from app.models import Warehouse, WarehouseTransfer

    warehouse = db.session.get(Warehouse, warehouse_id)
    if not warehouse:
        return api_response(False, error="Depósito não encontrado.", status_code=404)
    transfers = (
        WarehouseTransfer.query.filter(
            (WarehouseTransfer.source_warehouse_id == warehouse_id)
            | (WarehouseTransfer.destination_warehouse_id == warehouse_id)
        )
        .order_by(WarehouseTransfer.created_at.desc())
        .limit(100)
        .all()
    )
    return api_response(
        True,
        data={
            "warehouse": warehouse.to_dict(include_stocks=True),
            "summary": {
                "stocks": len(warehouse.stocks),
                "locations": len(warehouse.locations),
                "transfers": len(transfers),
                "quantity": sum(int(row.quantity or 0) for row in warehouse.stocks),
            },
            "events": [row.to_dict() for row in transfers],
        },
    )


@bp.get("/suprimentos/estoques")
@auth_required
def warehouse_stock_list():
    return api_response(True, data=list_warehouse_stocks(request.args.get("warehouse_id", type=int)))


@bp.get("/suprimentos/mmp/saldos")
@auth_required
def mmp_stock_list():
    return api_response(True, data=list_mmp_stocks())


@bp.get("/suprimentos/locais")
@auth_required
def warehouse_location_list():
    return api_response(True, data=list_warehouse_locations(request.args.get("warehouse_id", type=int)))


@bp.post("/suprimentos/locais")
@auth_required
def warehouse_location_create():
    denied = _guard_management()
    if denied: return denied
    def action():
        row = create_warehouse_location(request.get_json(silent=True) or {})
        record_event(user_id=g.current_user.id, entity_type="WAREHOUSE_LOCATION", entity_id=row.id, action="CREATED", new_value=row.to_dict())
        db.session.commit()
        return row.to_dict()
    return _run(action, status_code=201)


@bp.put("/suprimentos/locais/<int:location_id>")
@auth_required
def warehouse_location_update(location_id: int):
    denied = _guard_management()
    if denied: return denied
    def action():
        row = update_warehouse_location(location_id, request.get_json(silent=True) or {})
        record_event(user_id=g.current_user.id, entity_type="WAREHOUSE_LOCATION", entity_id=row.id, action="UPDATED", new_value=row.to_dict())
        db.session.commit()
        return row.to_dict()
    return _run(action)


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


@bp.get("/suprimentos/transferencias")
@auth_required
def warehouse_transfer_list():
    return api_response(True, data=list_warehouse_transfers(request.args.get("limite", type=int) or 100))


@bp.post("/suprimentos/transferencias")
@auth_required
def warehouse_transfer_create():
    denied = _guard_management()
    if denied: return denied
    return _run(lambda: create_warehouse_transfer(request.get_json(silent=True) or {}, user_id=g.current_user.id).to_dict(), status_code=201)


@bp.get("/suprimentos/mmp/qr/<path:qr_code>")
@auth_required
def mmp_qr_lookup(qr_code: str):
    return _run(lambda: lookup_mmp_qr(qr_code))


@bp.post("/suprimentos/mmp/saidas")
@auth_required
def mmp_stock_issue():
    if not user_has_mechanic_workspace_access(g.current_user):
        return api_response(False, error="Perfil sem permissão para registrar aplicação no Estoque MMP.", status_code=403)
    return _run(lambda: issue_mmp_stock(request.get_json(silent=True) or {}, user_id=g.current_user.id))


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

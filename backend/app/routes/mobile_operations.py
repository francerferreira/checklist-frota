from flask import Blueprint, g, request

from app.services.auth_service import auth_required
from app.services.mobile_operation_service import (
    MobileOperationAccessError,
    MobileOperationConflict,
    mobile_access_code,
    resolve_mobile_asset,
    sync_mobile_operation,
)
from app.utils.responses import api_response


bp = Blueprint("mobile_operations", __name__)


@bp.get("/operacao-mobile/ativos/<access_code>")
@auth_required
def mobile_asset_by_code(access_code: str):
    try:
        vehicle = resolve_mobile_asset(access_code)
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)
    return api_response(True, data={"access_code": mobile_access_code(vehicle.id), "vehicle": vehicle.to_dict()})


@bp.post("/operacao-mobile/sincronizar")
@auth_required
def sync_mobile():
    try:
        data = sync_mobile_operation(request.get_json(silent=True) or {}, g.current_user)
    except MobileOperationAccessError as exc:
        return api_response(False, error=str(exc), status_code=403)
    except MobileOperationConflict as exc:
        return api_response(False, error=str(exc), status_code=409)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=data)

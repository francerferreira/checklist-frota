from flask import Blueprint, request

from app.services.maintenance_dashboard_service import parse_dashboard_filters
from app.services.maintenance_dashboard_tv_service import build_maintenance_tv_payload
from app.utils.responses import api_response


bp = Blueprint("maintenance_dashboard_tv", __name__)


def _payload():
    try:
        return api_response(True, data=build_maintenance_tv_payload(parse_dashboard_filters(request.args)))
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)


@bp.get("/api/dashboard-tv/manutencao")
@bp.get("/dashboard-tv/manutencao")
def maintenance_tv_data():
    return _payload()

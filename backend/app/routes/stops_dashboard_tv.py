from flask import Blueprint, request

from app.services.maintenance_dashboard_service import parse_dashboard_filters
from app.services.stops_dashboard_tv_service import build_stops_dashboard_tv_payload
from app.utils.responses import api_response


bp = Blueprint("stops_dashboard_tv", __name__)


@bp.get("/api/dashboard-tv/paradas")
@bp.get("/dashboard-tv/paradas")
def stops_dashboard_tv_data():
    try:
        return api_response(True, data=build_stops_dashboard_tv_payload(parse_dashboard_filters(request.args)))
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)

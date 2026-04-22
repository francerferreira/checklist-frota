from flask import Blueprint, jsonify, request

from app.services.auth_service import auth_required
from app.services.report_service import (
    build_dashboard_summary,
    build_item_report,
    build_macro_report,
    build_micro_report,
    build_productivity_report,
)

bp = Blueprint("reports", __name__)


@bp.get("/")
def index():
    return jsonify(
        {
            "name": "Sistema de Checklist de Frota",
            "status": "online",
            "docs": {
                "auth": "/login",
                "veiculos": "/veiculos",
                "checklist": "/checklist",
                "nao_conformidades": "/nao_conformidades",
                "nao_conformidades_mecanico": "/mecanico/nao_conformidades",
                "upload": "/upload",
                "relatorios": "/relatorios/macro",
            },
        }
    )


@bp.get("/relatorios/dashboard")
@auth_required
def dashboard_report():
    return jsonify(build_dashboard_summary())


@bp.get("/relatorios/macro")
@auth_required
def macro_report():
    return jsonify(build_macro_report())


@bp.get("/relatorios/micro")
@auth_required
def micro_report():
    return jsonify(build_micro_report())


@bp.get("/relatorios/produtividade")
@auth_required
def productivity_report():
    return jsonify(build_productivity_report())


@bp.get("/relatorios/item")
@auth_required
def item_report():
    return jsonify(
        build_item_report(
            request.args.get("item"),
            date_from=request.args.get("data_de"),
            date_to=request.args.get("data_ate"),
            nc_status=request.args.get("status_nc"),
            modulo=request.args.get("modulo"),
        )
    )

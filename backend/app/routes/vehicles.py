from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Vehicle
from app.services.auth_service import auth_required, user_has_management_access
from app.services.inventory_import_service import discover_inventory_file, import_inventory_data
from app.services.report_service import build_vehicle_history

bp = Blueprint("vehicles", __name__)


def _guard_management_access():
    if not user_has_management_access(g.current_user):
        return jsonify({"error": "Somente admin ou gestor podem gerenciar equipamentos."}), 403
    return None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _vehicle_from_payload(vehicle: Vehicle, payload: dict) -> Vehicle:
    if "placa" in payload:
        vehicle.placa = (_clean(payload.get("placa")) or "S/PLACA").upper()
    if "modelo" in payload:
        vehicle.modelo = _clean(payload.get("modelo")) or ""
    if "ano" in payload:
        vehicle.ano = _clean(payload.get("ano"))
    if "frota" in payload:
        vehicle.frota = (_clean(payload.get("frota")) or "").upper()
    if "tipo" in payload:
        vehicle.tipo = (_clean(payload.get("tipo")) or "").lower()
    if "chassi" in payload:
        vehicle.chassi = _clean(payload.get("chassi"))
    if "configuracao" in payload:
        vehicle.configuracao = _clean(payload.get("configuracao"))
    if "atividade" in payload:
        vehicle.atividade = _clean(payload.get("atividade"))
    if "status" in payload:
        vehicle.status = (_clean(payload.get("status")) or "ON").upper()
    if "local" in payload:
        vehicle.local = _clean(payload.get("local"))
    if "descricao" in payload:
        vehicle.descricao = _clean(payload.get("descricao"))
    if "foto_path" in payload:
        vehicle.foto_path = _clean(payload.get("foto_path"))
    if "ativo" in payload:
        vehicle.ativo = bool(payload.get("ativo"))
    elif vehicle.status:
        vehicle.ativo = vehicle.status.upper() not in {"RETIRADO", "OFF"}
    if vehicle.ativo:
        vehicle.retirado_em = None
    return vehicle


@bp.get("/veiculos")
@auth_required
def list_vehicles():
    tipo = request.args.get("tipo")
    ativos = request.args.get("ativos")
    query = Vehicle.query.order_by(Vehicle.frota.asc())
    if tipo:
        query = query.filter_by(tipo=tipo.lower())
    if ativos == "true":
        query = query.filter_by(ativo=True)
    elif ativos == "false":
        query = query.filter_by(ativo=False)
    return jsonify([vehicle.to_dict() for vehicle in query.all()])


@bp.get("/veiculos/<int:vehicle_id>/historico")
@auth_required
def vehicle_history(vehicle_id: int):
    return jsonify(build_vehicle_history(vehicle_id))


@bp.post("/veiculos")
@auth_required
def create_vehicle():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    required_fields = ["modelo", "frota", "tipo"]
    missing = [field for field in required_fields if not payload.get(field)]
    if missing:
        return jsonify({"error": f"Campos obrigatorios ausentes: {', '.join(missing)}"}), 400

    vehicle = _vehicle_from_payload(Vehicle(), payload)
    db.session.add(vehicle)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Placa ou frota ja cadastrada."}), 409
    return jsonify(vehicle.to_dict()), 201


@bp.put("/veiculos/<int:vehicle_id>")
@auth_required
def update_vehicle(vehicle_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    vehicle = Vehicle.query.get_or_404(vehicle_id)
    _vehicle_from_payload(vehicle, request.get_json(silent=True) or {})
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Placa ou frota ja cadastrada."}), 409
    return jsonify(vehicle.to_dict())


@bp.delete("/veiculos/<int:vehicle_id>")
@auth_required
def retire_vehicle(vehicle_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    vehicle = Vehicle.query.get_or_404(vehicle_id)
    vehicle.ativo = False
    vehicle.status = "RETIRADO"
    vehicle.retirado_em = datetime.utcnow()
    db.session.commit()
    return jsonify(vehicle.to_dict())


@bp.post("/veiculos/importar-inventario")
@auth_required
def import_inventory():
    denied = _guard_management_access()
    if denied:
        return denied

    inventory_file = discover_inventory_file(current_app.config.get("INVENTORY_FILE"))
    if not inventory_file:
        return jsonify({"error": "Arquivo de inventario nao encontrado."}), 404

    result = import_inventory_data(inventory_file)
    return jsonify(result)

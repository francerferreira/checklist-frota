from datetime import date, datetime, time, timedelta

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app.extensions import db
from app.models import Checklist, ChecklistCatalogItem, ChecklistItem, Vehicle
from app.services.auth_service import auth_required, user_has_management_access
from app.services.checklist_catalog import (
    CHECKLIST_CATALOG,
    build_checklist_catalog,
    get_items_for_vehicle_type,
    normalize_item_name,
)
from app.services.activity_link_service import auto_link_non_conformities_to_open_activities
from app.services.maintenance_service import sync_checklist_non_conformities
from app.services.vehicle_type_service import resolve_vehicle_type_for_checklist
from app.utils.responses import api_response

bp = Blueprint("checklist", __name__)


def _guard_management_access():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar itens do checklist.", status_code=403)
    return None


def _clean(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_vehicle_type(value: str | None) -> str:
    vehicle_type = (_clean(value) or "").lower()
    if vehicle_type not in CHECKLIST_CATALOG:
        raise ValueError("Tipo de equipamento invalido.")
    return vehicle_type


def _next_position(vehicle_type: str) -> int:
    current = (
        db.session.query(func.max(ChecklistCatalogItem.position))
        .filter_by(vehicle_type=vehicle_type)
        .scalar()
    )
    return int(current or 0) + 1


def _item_payload_from_request(item: ChecklistCatalogItem, payload: dict, *, is_create: bool = False):
    if is_create or "tipo" in payload or "vehicle_type" in payload:
        item.vehicle_type = _normalize_vehicle_type(payload.get("tipo") or payload.get("vehicle_type"))
    if is_create or "item_nome" in payload:
        item_name = _clean(payload.get("item_nome"))
        if not item_name:
            raise ValueError("Nome do item e obrigatorio.")
        item.item_nome = item_name.upper()
    if "position" in payload or "ordem" in payload:
        try:
            position = int(payload.get("position") or payload.get("ordem"))
        except (TypeError, ValueError):
            raise ValueError("Ordem do item invalida.")
        if position <= 0:
            raise ValueError("Ordem do item deve ser maior que zero.")
        item.position = position
    elif is_create:
        item.position = _next_position(item.vehicle_type)
    if "foto_path" in payload:
        item.foto_path = _clean(payload.get("foto_path"))
    if "ativo" in payload:
        item.ativo = bool(payload.get("ativo"))
    elif is_create:
        item.ativo = True
    return item


def _find_vehicle(identifier: str):
    if identifier.isdigit():
        vehicle = Vehicle.query.get(int(identifier))
        if vehicle:
            return vehicle
    pattern = f"%{identifier}%"
    return Vehicle.query.filter(
        (Vehicle.frota.ilike(pattern)) | (Vehicle.placa.ilike(pattern))
    ).first()


def _parse_date_param(value: str | None, fallback: date) -> date:
    text = (value or "").strip()
    if not text:
        return fallback
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("Data inválida. Use o formato YYYY-MM-DD.") from exc


@bp.get("/config/checklists")
@auth_required
def checklist_catalog():
    include_inactive = request.args.get("incluir_inativos") == "true"
    if include_inactive:
        denied = _guard_management_access()
        if denied:
            return denied
    return api_response(True, data=build_checklist_catalog(include_inactive=include_inactive))


@bp.get("/checklist-itens")
@auth_required
def list_checklist_items():
    denied = _guard_management_access()
    if denied:
        return denied

    vehicle_type = request.args.get("tipo")
    active_filter = request.args.get("ativos", "true")
    query = ChecklistCatalogItem.query
    if vehicle_type:
        try:
            query = query.filter_by(vehicle_type=_normalize_vehicle_type(vehicle_type))
        except ValueError as exc:
            return api_response(False, error=str(exc), status_code=400)
    if active_filter != "all":
        query = query.filter_by(ativo=active_filter == "true")

    rows = query.order_by(
        ChecklistCatalogItem.vehicle_type.asc(),
        ChecklistCatalogItem.position.asc(),
        ChecklistCatalogItem.item_nome.asc(),
    ).all()
    return api_response(True, data=[item.to_dict() for item in rows])


@bp.post("/checklist-itens")
@auth_required
def create_checklist_item():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    item = ChecklistCatalogItem()
    try:
        _item_payload_from_request(item, payload, is_create=True)
        db.session.add(item)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    except IntegrityError:
        db.session.rollback()
        return api_response(False, error="Já existe um item com este nome para este tipo de equipamento.", status_code=409)
    return api_response(True, data=item.to_dict(), status_code=201)


@bp.put("/checklist-itens/<int:item_id>")
@auth_required
def update_checklist_item(item_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    item = ChecklistCatalogItem.query.get_or_404(item_id)
    payload = request.get_json(silent=True) or {}
    try:
        _item_payload_from_request(item, payload)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    except IntegrityError:
        db.session.rollback()
        return api_response(False, error="Já existe um item com este nome para este tipo de equipamento.", status_code=409)
    return api_response(True, data=item.to_dict())


@bp.delete("/checklist-itens/<int:item_id>")
@auth_required
def delete_checklist_item(item_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    item = ChecklistCatalogItem.query.get_or_404(item_id)
    item.ativo = False
    db.session.commit()
    return api_response(True, data=item.to_dict())


@bp.post("/checklist")
@auth_required
def create_checklist():
    payload = request.get_json(silent=True) or {}
    vehicle_id = payload.get("vehicle_id")
    items_payload = payload.get("itens") or []

    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return api_response(False, error="Veículo não encontrado.", status_code=404)

    resolved_vehicle_type = resolve_vehicle_type_for_checklist(vehicle)
    expected_items = get_items_for_vehicle_type(resolved_vehicle_type)
    provided_items = {
        normalize_item_name(item.get("item_nome")): item for item in items_payload if item.get("item_nome")
    }
    expected_keys = {normalize_item_name(item) for item in expected_items}

    if set(provided_items.keys()) != expected_keys:
        err_data = {
            "error": "Checklist incompleto ou inconsistente.",
            "esperado": expected_items,
        }
        return api_response(False, data=err_data, error="Checklist incompleto.", status_code=400)

    checklist = Checklist(vehicle_id=vehicle.id, user_id=g.current_user.id)
    db.session.add(checklist)
    db.session.flush()

    for item_name in expected_items:
        item_payload = provided_items[normalize_item_name(item_name)]
        status = (item_payload.get("status") or "").strip().upper()
        if status not in {"OK", "NC"}:
            db.session.rollback()
            return api_response(False, error=f"Status inválido para o item {item_name}.", status_code=400)

        foto_antes = item_payload.get("foto_antes")
        if status == "NC" and not foto_antes:
            db.session.rollback()
            return api_response(False, error=f"Foto antes obrigatória para NC no item {item_name}.", status_code=400)

        item = ChecklistItem(
            checklist_id=checklist.id,
            item_nome=item_name,
            status=status,
            observacao=(item_payload.get("observacao") or "").strip() or None,
            foto_antes=foto_antes,
            foto_depois=item_payload.get("foto_depois"),
            codigo_peca=(item_payload.get("codigo_peca") or "").strip() or None,
            descricao_peca=(item_payload.get("descricao_peca") or "").strip() or None,
            resolvido=False if status == "NC" else True,
        )
        db.session.add(item)

    db.session.commit()
    nc_items = ChecklistItem.query.filter_by(checklist_id=checklist.id, status="NC").all()
    if nc_items:
        sync_checklist_non_conformities(nc_items)
        auto_link_non_conformities_to_open_activities(nc_items)
    return api_response(True, data=checklist.to_dict(include_items=True), status_code=201)


@bp.get("/checklist")
@auth_required
def list_checklists():
    vehicle_identifier = request.args.get("veiculo")
    limit = min(int(request.args.get("limit", 100)), 500)
    query = Checklist.query.order_by(Checklist.created_at.desc())

    if vehicle_identifier:
        vehicle = _find_vehicle(vehicle_identifier)
        if not vehicle:
            return api_response(True, data=[])
        query = query.filter_by(vehicle_id=vehicle.id)

    return api_response(True, data=[checklist.to_dict() for checklist in query.limit(limit).all()])


@bp.get("/checklist/historico-matriz")
@auth_required
def checklist_history_matrix():
    vehicle_type = request.args.get("tipo")
    if vehicle_type:
        try:
            vehicle_type = _normalize_vehicle_type(vehicle_type)
        except ValueError as exc:
            return api_response(False, error=str(exc), status_code=400)

    today = datetime.utcnow().date()
    try:
        start_date = _parse_date_param(request.args.get("data_inicio"), today - timedelta(days=6))
        end_date = _parse_date_param(request.args.get("data_fim"), today)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)

    if end_date < start_date:
        return api_response(False, error="A data final deve ser maior ou igual à data inicial.", status_code=400)

    max_days = 62
    if (end_date - start_date).days + 1 > max_days:
        return api_response(False, error=f"Período muito grande. Limite de {max_days} dias.", status_code=400)

    start_dt = datetime.combine(start_date, time.min)
    end_dt_exclusive = datetime.combine(end_date + timedelta(days=1), time.min)

    vehicle_query = Vehicle.query.filter(Vehicle.ativo.is_(True))
    if vehicle_type:
        vehicle_query = vehicle_query.filter(Vehicle.tipo == vehicle_type)
    else:
        vehicle_query = vehicle_query.filter(Vehicle.tipo.in_(list(CHECKLIST_CATALOG.keys()) + ["auxiliar"]))
    vehicles = vehicle_query.order_by(Vehicle.frota.asc()).all()

    columns = []
    day = start_date
    while day <= end_date:
        columns.append({
            "date": day.isoformat(),
            "label": day.strftime("%d/%m"),
        })
        day += timedelta(days=1)

    rows_map: dict[int, dict] = {}
    for vehicle in vehicles:
        rows_map[vehicle.id] = {
            "vehicle_id": vehicle.id,
            "frota": vehicle.frota,
            "placa": vehicle.placa,
            "tipo": vehicle.tipo,
            "checklist_count": 0,
            "cells": {column["date"]: "" for column in columns},
            "_latest_by_date": {},
        }

    checklist_query = (
        Checklist.query.join(Vehicle)
        .filter(Checklist.created_at >= start_dt, Checklist.created_at < end_dt_exclusive)
    )
    if vehicle_type:
        checklist_query = checklist_query.filter(Vehicle.tipo == vehicle_type)
    else:
        checklist_query = checklist_query.filter(Vehicle.tipo.in_(list(CHECKLIST_CATALOG.keys()) + ["auxiliar"]))

    checklists = checklist_query.order_by(Checklist.created_at.asc()).all()
    for checklist in checklists:
        row = rows_map.get(checklist.vehicle_id)
        if not row:
            continue
        row["checklist_count"] += 1
        day_key = checklist.created_at.date().isoformat()
        if day_key not in row["cells"]:
            continue

        previous_dt = row["_latest_by_date"].get(day_key)
        if previous_dt and checklist.created_at <= previous_dt:
            continue

        user_name = (checklist.user.nome or checklist.user.login or "").strip()
        row["cells"][day_key] = f"{checklist.created_at.strftime('%H:%M')} - {user_name}"
        row["_latest_by_date"][day_key] = checklist.created_at

    rows = []
    for vehicle in vehicles:
        row = rows_map[vehicle.id]
        rows.append({
            "vehicle_id": row["vehicle_id"],
            "frota": row["frota"],
            "placa": row["placa"],
            "tipo": row["tipo"],
            "checklist_count": int(row["checklist_count"] or 0),
            "cells": [row["cells"].get(column["date"], "") for column in columns],
        })

    data = {
        "periodo": {
            "inicio": start_date.isoformat(),
            "fim": end_date.isoformat(),
        },
        "columns": columns,
        "rows": rows,
    }
    return api_response(True, data=data)


@bp.get("/checklist/<veiculo>")
@auth_required
def list_checklists_by_vehicle(veiculo: str):
    vehicle = _find_vehicle(veiculo)
    if not vehicle:
        return api_response(False, error="Veículo não encontrado.", status_code=404)

    checklists = (
        Checklist.query.filter_by(vehicle_id=vehicle.id)
        .order_by(Checklist.created_at.desc())
        .all()
    )
    return api_response(True, data=[checklist.to_dict(include_items=True) for checklist in checklists])

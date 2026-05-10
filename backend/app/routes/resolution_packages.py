from __future__ import annotations

from collections import Counter

from flask import Blueprint, g, request

from app.extensions import db
from app.models import ChecklistItem, ResolutionPackage, ResolutionPackageLink
from app.services.auth_service import auth_required, user_has_management_access
from app.services.resolution_package_service import (
    DEFAULT_RECURRENCE_WEIGHT,
    DEFAULT_RECURRENCE_WINDOW_DAYS,
    derive_package_item_name,
    normalized_item_name,
    refresh_package_metrics,
)
from app.utils.responses import api_response

bp = Blueprint("resolution_packages", __name__)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _vehicle_id(item: ChecklistItem) -> int | None:
    checklist = item.checklist
    vehicle = checklist.vehicle if checklist else None
    return vehicle.id if vehicle else None


def _vehicle_label(item: ChecklistItem) -> str:
    checklist = item.checklist
    vehicle = checklist.vehicle if checklist else None
    if not vehicle:
        return "-"
    return vehicle.frota or vehicle.placa or "-"


def _build_default_title(grouping_mode: str, items: list[ChecklistItem]) -> str:
    if grouping_mode == "POR_ITEM":
        return f"Pacote por item - {derive_package_item_name(items) or '-'}"
    return f"Pacote por equipamento - {_vehicle_label(items[0]) if items else '-'}"


@bp.get("/pacotes_resolucao")
@auth_required
def list_resolution_packages():
    status_filter = _clean(request.args.get("status"))
    query = ResolutionPackage.query.order_by(ResolutionPackage.created_at.desc())
    if status_filter:
        query = query.filter(ResolutionPackage.status == status_filter)
    packages = [package.to_dict(include_links=True) for package in query.all()]
    return api_response(True, data=packages)


@bp.post("/pacotes_resolucao")
@auth_required
def create_resolution_package():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem criar pacote de resolução.", status_code=403)

    payload = request.get_json(silent=True) or {}
    grouping_mode = str(payload.get("grouping_mode") or "").strip().upper()
    if grouping_mode not in {"POR_ITEM", "POR_EQUIPAMENTO"}:
        return api_response(False, error="Modo de agrupamento inválido.", status_code=400)

    raw_ids = payload.get("checklist_item_ids") or []
    try:
        checklist_item_ids = [int(item_id) for item_id in raw_ids]
    except (TypeError, ValueError):
        return api_response(False, error="Lista de não conformidades inválida.", status_code=400)
    if not checklist_item_ids:
        return api_response(False, error="Selecione ao menos uma não conformidade para criar o pacote.", status_code=400)

    items = (
        ChecklistItem.query.filter(ChecklistItem.id.in_(checklist_item_ids), ChecklistItem.status == "NC")
        .all()
    )
    if len(items) != len(set(checklist_item_ids)):
        return api_response(False, error="Uma ou mais não conformidades não foram encontradas.", status_code=404)

    unresolved_items = [item for item in items if not item.resolvido]
    if not unresolved_items:
        return api_response(False, error="As não conformidades selecionadas já estão resolvidas.", status_code=400)

    already_linked = (
        db.session.query(ResolutionPackageLink, ResolutionPackage)
        .join(ResolutionPackage, ResolutionPackage.id == ResolutionPackageLink.package_id)
        .filter(
            ResolutionPackageLink.checklist_item_id.in_([item.id for item in unresolved_items]),
            ResolutionPackage.status.in_(["ABERTO", "EM_MANUTENCAO"]),
        )
        .all()
    )
    if already_linked:
        package_labels = ", ".join(sorted({f"#{package.id} {package.title}" for _, package in already_linked}))
        return api_response(False, error=f"Já existe pacote aberto para parte dos registros selecionados: {package_labels}.", status_code=409)

    if grouping_mode == "POR_ITEM":
        distinct_items = {normalized_item_name(item) for item in unresolved_items}
        if len(distinct_items) != 1:
            return api_response(False, error="Pacote por item exige um item distinto em todos os registros selecionados.", status_code=400)
        item_name = next(iter(distinct_items))
        vehicle_id = None
    else:
        distinct_vehicle_ids = {_vehicle_id(item) for item in unresolved_items}
        if len(distinct_vehicle_ids) != 1:
            return api_response(False, error="Pacote por equipamento exige registros do mesmo equipamento.", status_code=400)
        vehicle_id = next(iter(distinct_vehicle_ids))
        item_name = derive_package_item_name(unresolved_items)

    package = ResolutionPackage(
        title=_clean(payload.get("title")) or _build_default_title(grouping_mode, unresolved_items),
        grouping_mode=grouping_mode,
        item_name=item_name,
        vehicle_id=vehicle_id,
        status="ABERTO",
        recurrence_window_days=int(payload.get("recurrence_window_days") or DEFAULT_RECURRENCE_WINDOW_DAYS),
        recurrence_weight=int(payload.get("recurrence_weight") or DEFAULT_RECURRENCE_WEIGHT),
        observation=_clean(payload.get("observation")),
        created_by_user_id=g.current_user.id,
    )
    db.session.add(package)
    db.session.flush()

    for item in unresolved_items:
        db.session.add(
            ResolutionPackageLink(
                package_id=package.id,
                checklist_item_id=item.id,
            )
        )
    db.session.flush()

    refresh_package_metrics(package)
    db.session.commit()
    return api_response(True, data=package.to_dict(include_links=True), status_code=201)

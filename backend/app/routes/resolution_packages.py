from __future__ import annotations

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

OPEN_PACKAGE_STATUSES = ("ABERTO", "EM_MANUTENCAO")


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


def _valid_grouping_modes(items: list[ChecklistItem]) -> list[str]:
    item_names = {normalized_item_name(item) for item in items if normalized_item_name(item) != "-"}
    vehicle_ids = {_vehicle_id(item) for item in items if _vehicle_id(item)}
    modes: list[str] = []
    if len(item_names) == 1:
        modes.append("POR_ITEM")
    if len(vehicle_ids) == 1:
        modes.append("POR_EQUIPAMENTO")
    return modes


def _load_selected_items(payload: dict) -> tuple[list[ChecklistItem], list[ChecklistItem], str | None]:
    raw_ids = payload.get("checklist_item_ids") or []
    try:
        checklist_item_ids = [int(item_id) for item_id in raw_ids]
    except (TypeError, ValueError):
        return [], [], "Lista de não conformidades inválida."
    if not checklist_item_ids:
        return [], [], "Selecione ao menos uma não conformidade."

    items = ChecklistItem.query.filter(ChecklistItem.id.in_(checklist_item_ids), ChecklistItem.status == "NC").all()
    if len(items) != len(set(checklist_item_ids)):
        return [], [], "Uma ou mais não conformidades não foram encontradas."

    unresolved_items = [item for item in items if not item.resolvido]
    if not unresolved_items:
        return items, [], "As não conformidades selecionadas já estão resolvidas."
    return items, unresolved_items, None


def _find_linked_open_packages(items: list[ChecklistItem]) -> list[ResolutionPackage]:
    if not items:
        return []
    rows = (
        db.session.query(ResolutionPackage)
        .join(ResolutionPackageLink, ResolutionPackage.id == ResolutionPackageLink.package_id)
        .filter(
            ResolutionPackageLink.checklist_item_id.in_([item.id for item in items]),
            ResolutionPackage.status.in_(OPEN_PACKAGE_STATUSES),
        )
        .distinct()
        .order_by(ResolutionPackage.created_at.desc())
        .all()
    )
    return rows


def _find_candidate_packages(items: list[ChecklistItem], grouping_mode: str) -> list[ResolutionPackage]:
    if not items:
        return []
    query = ResolutionPackage.query.filter(ResolutionPackage.status.in_(OPEN_PACKAGE_STATUSES))
    if grouping_mode == "POR_ITEM":
        item_name = derive_package_item_name(items)
        if not item_name:
            return []
        query = query.filter(
            ResolutionPackage.grouping_mode == "POR_ITEM",
            ResolutionPackage.item_name == item_name,
        )
    else:
        vehicle_id = _vehicle_id(items[0]) if items else None
        if not vehicle_id:
            return []
        query = query.filter(
            ResolutionPackage.grouping_mode == "POR_EQUIPAMENTO",
            ResolutionPackage.vehicle_id == vehicle_id,
        )
    return query.order_by(ResolutionPackage.created_at.desc()).all()


def _package_hint(package: ResolutionPackage, reason: str) -> dict:
    label_map = {
        "JA_CONTEM_REGISTRO": "Já contém parte dos registros selecionados",
        "MESMO_ITEM": "Pacote aberto para o mesmo item distinto",
        "MESMO_EQUIPAMENTO": "Pacote aberto para o mesmo equipamento",
    }
    return {
        "id": package.id,
        "title": package.title,
        "grouping_mode": package.grouping_mode,
        "status": package.status,
        "priority_score": package.priority_score,
        "reference_label": package.reference_label(),
        "critical_recurrence": package.critical_recurrence,
        "reason": reason,
        "reason_label": label_map.get(reason, reason),
    }


@bp.get("/pacotes_resolucao")
@auth_required
def list_resolution_packages():
    status_filter = _clean(request.args.get("status"))
    query = ResolutionPackage.query.order_by(ResolutionPackage.created_at.desc())
    if status_filter:
        query = query.filter(ResolutionPackage.status == status_filter)
    packages = [package.to_dict(include_links=True) for package in query.all()]
    return api_response(True, data=packages)


@bp.post("/pacotes_resolucao/sugestoes")
@auth_required
def suggest_resolution_packages():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem analisar sugestões de pacote.", status_code=403)

    payload = request.get_json(silent=True) or {}
    _items, unresolved_items, error = _load_selected_items(payload)
    if error:
        return api_response(False, error=error, status_code=400)

    modes = _valid_grouping_modes(unresolved_items)
    linked_packages = _find_linked_open_packages(unresolved_items)
    suggestions: list[dict] = []
    seen_ids: set[int] = set()

    for package in linked_packages:
        suggestions.append(_package_hint(package, "JA_CONTEM_REGISTRO"))
        seen_ids.add(package.id)

    for grouping_mode in modes:
        reason = "MESMO_ITEM" if grouping_mode == "POR_ITEM" else "MESMO_EQUIPAMENTO"
        for package in _find_candidate_packages(unresolved_items, grouping_mode):
            if package.id in seen_ids:
                continue
            suggestions.append(_package_hint(package, reason))
            seen_ids.add(package.id)

    return api_response(
        True,
        data={
            "valid_grouping_modes": modes,
            "suggestions": suggestions,
        },
    )


@bp.post("/pacotes_resolucao")
@auth_required
def create_resolution_package():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem criar pacote de resolução.", status_code=403)

    payload = request.get_json(silent=True) or {}
    grouping_mode = str(payload.get("grouping_mode") or "").strip().upper()
    if grouping_mode not in {"POR_ITEM", "POR_EQUIPAMENTO"}:
        return api_response(False, error="Modo de agrupamento inválido.", status_code=400)

    _items, unresolved_items, error = _load_selected_items(payload)
    if error:
        return api_response(False, error=error, status_code=400)

    already_linked = _find_linked_open_packages(unresolved_items)
    if already_linked:
        package_labels = ", ".join(sorted({f"#{package.id} {package.title}" for package in already_linked}))
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
        db.session.add(ResolutionPackageLink(package_id=package.id, checklist_item_id=item.id))
    db.session.flush()

    refresh_package_metrics(package)
    db.session.commit()
    return api_response(True, data=package.to_dict(include_links=True), status_code=201)


@bp.post("/pacotes_resolucao/<int:package_id>/itens")
@auth_required
def add_items_to_resolution_package(package_id: int):
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem atualizar pacote de resolução.", status_code=403)

    package = ResolutionPackage.query.get_or_404(package_id)
    if package.status not in OPEN_PACKAGE_STATUSES:
        return api_response(False, error="Somente pacotes abertos podem receber novos registros.", status_code=400)

    payload = request.get_json(silent=True) or {}
    _items, unresolved_items, error = _load_selected_items(payload)
    if error:
        return api_response(False, error=error, status_code=400)

    if package.grouping_mode == "POR_ITEM":
        distinct_items = {normalized_item_name(item) for item in unresolved_items}
        if len(distinct_items) != 1 or next(iter(distinct_items)) != (package.item_name or "-"):
            return api_response(False, error="Este pacote só aceita registros do mesmo item distinto.", status_code=400)
    else:
        distinct_vehicle_ids = {_vehicle_id(item) for item in unresolved_items}
        if len(distinct_vehicle_ids) != 1 or next(iter(distinct_vehicle_ids)) != package.vehicle_id:
            return api_response(False, error="Este pacote só aceita registros do mesmo equipamento.", status_code=400)

    current_link_ids = {link.checklist_item_id for link in package.links}
    if all(item.id in current_link_ids for item in unresolved_items):
        return api_response(False, error="Os registros selecionados já fazem parte deste pacote.", status_code=400)

    other_linked = (
        db.session.query(ResolutionPackage)
        .join(ResolutionPackageLink, ResolutionPackage.id == ResolutionPackageLink.package_id)
        .filter(
            ResolutionPackageLink.checklist_item_id.in_([item.id for item in unresolved_items if item.id not in current_link_ids]),
            ResolutionPackage.status.in_(OPEN_PACKAGE_STATUSES),
            ResolutionPackage.id != package.id,
        )
        .distinct()
        .all()
    )
    if other_linked:
        package_labels = ", ".join(sorted({f"#{row.id} {row.title}" for row in other_linked}))
        return api_response(False, error=f"Parte dos registros já está vinculada a outro pacote aberto: {package_labels}.", status_code=409)

    for item in unresolved_items:
        if item.id in current_link_ids:
            continue
        db.session.add(ResolutionPackageLink(package_id=package.id, checklist_item_id=item.id))
    db.session.flush()

    note = _clean(payload.get("observation"))
    if note:
        current_observation = package.observation or ""
        package.observation = f"{current_observation}\nComplemento: {note}".strip()

    refresh_package_metrics(package)
    db.session.commit()
    return api_response(True, data=package.to_dict(include_links=True))

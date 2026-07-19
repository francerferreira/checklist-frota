from __future__ import annotations

from datetime import date, datetime, timedelta
import re

from sqlalchemy import and_, case, desc, func, or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Activity,
    ActivityItem,
    Checklist,
    ChecklistItem,
    EquipmentFamily,
    EquipmentProfile,
    MaintenanceSchedule,
    MaintenanceScheduleItem,
    MaintenanceWorkOrder,
    MechanicNonConformity,
    User,
    Vehicle,
    WashRecord,
)
from app.utils.timezone import now_manaus_naive

_ORIGIN_PATTERN = re.compile(r"\[ORIGEM:(?P<type>[A-Z_]+)#(?P<id>\d+)\]")


def _active_vehicle_filter():
    normalized_status = func.upper(func.trim(func.coalesce(Vehicle.status, "ON")))
    return (
        Vehicle.ativo.is_(True),
        Vehicle.retirado_em.is_(None),
        normalized_status.notin_(["RETIRADO", "OFF"]),
    )


def _extract_non_conformity_origin_id(observation: str | None) -> int | None:
    if not observation:
        return None
    match = _ORIGIN_PATTERN.search(observation)
    if not match:
        return None
    if (match.group("type") or "").strip().upper() not in {"NC", "NAO_CONFORMIDADE"}:
        return None
    try:
        return int(match.group("id"))
    except (TypeError, ValueError):
        return None


def _average_minutes(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def build_macro_report() -> list[dict]:
    item_principal = func.coalesce(ChecklistItem.item_principal, ChecklistItem.item_nome)
    rows = (
        db.session.query(
            item_principal.label("item_nome"),
            func.count(ChecklistItem.id).label("total_nc"),
            func.sum(case((ChecklistItem.resolvido.is_(False), 1), else_=0)).label("abertas"),
            func.sum(case((ChecklistItem.resolvido.is_(True), 1), else_=0)).label("resolvidas"),
        )
        .filter(ChecklistItem.status == "NC")
        .group_by(item_principal)
        .order_by(desc("total_nc"), item_principal.asc())
        .all()
    )
    return [
        {
            "item_nome": item_nome,
            "total_nc": int(total_nc or 0),
            "abertas": int(abertas or 0),
            "resolvidas": int(resolvidas or 0),
        }
        for item_nome, total_nc, abertas, resolvidas in rows
    ]


def build_micro_report(*, only_active: bool = True) -> list[dict]:
    query = (
        db.session.query(
            Vehicle.id,
            Vehicle.frota,
            Vehicle.placa,
            Vehicle.modelo,
            Vehicle.tipo,
            func.count(case((ChecklistItem.status == "NC", 1))).label("total_nc"),
            func.max(Checklist.created_at).label("ultimo_checklist"),
        )
        .outerjoin(Checklist, Checklist.vehicle_id == Vehicle.id)
        .outerjoin(ChecklistItem, ChecklistItem.checklist_id == Checklist.id)
    )
    if only_active:
        query = query.filter(*_active_vehicle_filter())
    rows = query.group_by(Vehicle.id).order_by(desc("total_nc"), Vehicle.frota.asc()).all()
    return [
        {
            "vehicle_id": vehicle_id,
            "frota": frota,
            "placa": placa,
            "modelo": modelo,
            "tipo": tipo,
            "total_nc": int(total_nc or 0),
            "ultimo_checklist": ultimo_checklist.isoformat() if ultimo_checklist else None,
        }
        for vehicle_id, frota, placa, modelo, tipo, total_nc, ultimo_checklist in rows
    ]


def build_item_report(
    item_name: str | None = None,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    nc_status: str | None = None,
    modulo: str | None = None,
    data_base: str | None = None,
) -> list[dict]:
    date_base = (data_base or "").strip().lower()
    date_column = ChecklistItem.data_resolucao if date_base == "resolucao" else ChecklistItem.created_at
    query = (
        ChecklistItem.query.join(Checklist)
        .join(Vehicle)
        .outerjoin(User, User.id == Checklist.user_id)
        .filter(ChecklistItem.status == "NC")
        .filter(*_active_vehicle_filter())
        .order_by(date_column.desc().nullslast(), ChecklistItem.created_at.desc())
    )
    if item_name and item_name.strip():
        search = f"%{item_name.strip()}%"
        query = query.filter(
            or_(
                ChecklistItem.item_nome.ilike(search),
                ChecklistItem.item_principal.ilike(search),
                ChecklistItem.parte.ilike(search),
                Vehicle.frota.ilike(search),
                Vehicle.placa.ilike(search),
                Vehicle.modelo.ilike(search),
                User.nome.ilike(search),
                User.login.ilike(search),
            )
        )
    if nc_status == "abertas":
        query = query.filter(ChecklistItem.resolvido.is_(False))
    elif nc_status == "resolvidas":
        query = query.filter(ChecklistItem.resolvido.is_(True))

    if modulo == "cavalo":
        query = query.filter(Vehicle.tipo == "cavalo")
    elif modulo == "carreta":
        query = query.filter(Vehicle.tipo == "carreta")
    elif modulo == "outros":
        query = query.filter(func.coalesce(Vehicle.tipo, "").notin_(["cavalo", "carreta"]))

    if date_base == "resolucao":
        query = query.filter(ChecklistItem.data_resolucao.isnot(None))

    if date_from:
        start = datetime.fromisoformat(date_from)
        query = query.filter(date_column >= start)
    if date_to:
        end = datetime.fromisoformat(date_to) + timedelta(days=1)
        query = query.filter(date_column < end)
    return [item.to_dict() for item in query.all()]


def build_vehicle_history(vehicle_id: int) -> dict:
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    non_conformities = (
        ChecklistItem.query.join(Checklist)
        .filter(Checklist.vehicle_id == vehicle_id, ChecklistItem.status == "NC")
        .order_by(ChecklistItem.created_at.desc())
        .all()
    )
    maintenance_items = (
        MaintenanceScheduleItem.query.filter_by(vehicle_id=vehicle_id)
        .order_by(MaintenanceScheduleItem.scheduled_date.desc().nullslast(), MaintenanceScheduleItem.created_at.desc())
        .all()
    )
    wash_records = (
        WashRecord.query.filter_by(vehicle_id=vehicle_id)
        .order_by(WashRecord.wash_date.desc(), WashRecord.id.desc())
        .limit(120)
        .all()
    )
    activity_items = (
        ActivityItem.query.filter_by(vehicle_id=vehicle_id)
        .order_by(ActivityItem.updated_at.desc())
        .limit(120)
        .all()
    )
    activity_history = []
    for item in activity_items:
        row = item.to_dict()
        row["atividade"] = item.activity.to_dict() if item.activity else None
        activity_history.append(row)

    return {
        "vehicle": vehicle.to_dict(),
        "nao_conformidades": [item.to_dict() for item in non_conformities],
        "manutencoes": [item.to_dict() for item in maintenance_items],
        "lavagens": [item.to_dict() for item in wash_records],
        "atividades": activity_history,
    }


def build_dashboard_summary() -> dict:
    from app.services.maintenance_intelligence_service import build_maintenance_intelligence_overview

    non_conformity_rows = ChecklistItem.query.with_entities(ChecklistItem.id, ChecklistItem.created_at).filter_by(status="NC").all()
    non_conformity_created_at = {row_id: created_at for row_id, created_at in non_conformity_rows}
    total_nc = len(non_conformity_rows)
    open_nc = ChecklistItem.query.filter_by(status="NC", resolvido=False).count()
    vehicles_with_failures = (
        db.session.query(func.count(func.distinct(Checklist.vehicle_id)))
        .join(ChecklistItem, ChecklistItem.checklist_id == Checklist.id)
        .filter(ChecklistItem.status == "NC")
        .scalar()
    )
    linked_activities = (
        Activity.query.with_entities(Activity.created_at, Activity.finalized_at, Activity.observacao)
        .filter(Activity.observacao.isnot(None))
        .all()
    )
    first_activity_at_by_nc: dict[int, datetime] = {}
    activity_to_resolution_minutes: list[float] = []

    for activity_created_at, activity_finalized_at, activity_observation in linked_activities:
        non_conformity_id = _extract_non_conformity_origin_id(activity_observation)
        if non_conformity_id is None:
            continue

        previous_created_at = first_activity_at_by_nc.get(non_conformity_id)
        if previous_created_at is None or activity_created_at < previous_created_at:
            first_activity_at_by_nc[non_conformity_id] = activity_created_at

        if activity_finalized_at and activity_finalized_at >= activity_created_at:
            elapsed_minutes = (activity_finalized_at - activity_created_at).total_seconds() / 60
            activity_to_resolution_minutes.append(elapsed_minutes)

    linked_non_conformity_ids = set(first_activity_at_by_nc).intersection(non_conformity_created_at)
    nc_to_activity_minutes: list[float] = []
    for non_conformity_id in linked_non_conformity_ids:
        nc_created_at = non_conformity_created_at.get(non_conformity_id)
        activity_created_at = first_activity_at_by_nc.get(non_conformity_id)
        if not nc_created_at or not activity_created_at or activity_created_at < nc_created_at:
            continue
        elapsed_minutes = (activity_created_at - nc_created_at).total_seconds() / 60
        nc_to_activity_minutes.append(elapsed_minutes)

    critical_items = build_macro_report()[:5]
    return {
        "total_nc": total_nc,
        "nc_abertas": open_nc,
        "veiculos_com_falha": int(vehicles_with_failures or 0),
        "nc_convertidas_em_atividade": len(linked_non_conformity_ids),
        "nc_sem_atividade": max(total_nc - len(linked_non_conformity_ids), 0),
        "tempo_medio_nc_para_atividade_minutos": _average_minutes(nc_to_activity_minutes),
        "tempo_medio_atividade_para_resolucao_minutos": _average_minutes(activity_to_resolution_minutes),
        "itens_criticos": critical_items,
        "manutencao_portuaria": build_maintenance_intelligence_overview(),
    }


def _parse_master_base_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"Data {field_name} invalida; use AAAA-MM-DD.") from exc


def _master_base_row(item: MaintenanceScheduleItem) -> dict:
    schedule = item.schedule
    vehicle = item.vehicle
    profile = vehicle.equipment_profile if vehicle else None
    location = profile.location if profile else None
    family = profile.family if profile else None
    work_order = item.work_order
    reference_date = item.scheduled_date or (item.created_at.date() if item.created_at else None)
    age_days = (now_manaus_naive().date() - reference_date).days if reference_date else None
    operational_state = vehicle.operational_state if vehicle else None

    return {
        "intervention_id": f"INTERVENCAO-{item.id:08d}",
        "schedule_item_id": item.id,
        "schedule_id": item.schedule_id,
        "work_order_id": work_order.id if work_order else None,
        "order_number": work_order.order_number if work_order else None,
        "source_type": schedule.source_type if schedule else None,
        "source_origin_type": schedule.source_origin_type() if schedule else None,
        "title": schedule.title if schedule else None,
        "item_name": work_order.item_name if work_order and work_order.item_name else (schedule.item_name if schedule else None),
        "status": work_order.status if work_order else item.status,
        "item_status": item.status,
        "work_order_status": work_order.status if work_order else None,
        "scheduled_date": item.scheduled_date.isoformat() if item.scheduled_date else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "age_days": max(age_days, 0) if age_days is not None else None,
        "assigned_mechanic_user_id": (
            work_order.assigned_mechanic_user_id
            if work_order and work_order.assigned_mechanic_user_id
            else item.assigned_mechanic_user_id
        ),
        "vehicle": {
            "id": vehicle.id,
            "frota": vehicle.frota,
            "modelo": vehicle.modelo,
            "tipo": vehicle.tipo,
            "ativo": bool(vehicle.ativo),
        }
        if vehicle
        else None,
        "family": {
            "id": family.id,
            "code": family.code,
            "name": family.name,
        }
        if family
        else None,
        "location": {
            "id": location.id,
            "code": location.code,
            "name": location.name,
            "full_name": location.full_name(),
        }
        if location
        else None,
        "operational_status": operational_state.operational_status if operational_state else "SEM_APONTAMENTO",
        "latest_hourmeter": (
            float(operational_state.latest_hourmeter)
            if operational_state and operational_state.latest_hourmeter is not None
            else None
        ),
    }


def build_management_master_base(
    *,
    page: int = 1,
    page_size: int = 50,
    family_code: str | None = None,
    vehicle_id: int | None = None,
    location_id: int | None = None,
    status: str | None = None,
    source_type: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    active_only: bool = True,
) -> dict:
    if page < 1:
        raise ValueError("A pagina deve ser maior que zero.")
    if page_size < 1 or page_size > 100:
        raise ValueError("O tamanho da pagina deve estar entre 1 e 100.")

    parsed_date_from = _parse_master_base_date(date_from, "inicial")
    parsed_date_to = _parse_master_base_date(date_to, "final")
    if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
        raise ValueError("A data inicial nao pode ser posterior a data final.")

    query = (
        MaintenanceScheduleItem.query
        .join(MaintenanceSchedule, MaintenanceSchedule.id == MaintenanceScheduleItem.schedule_id)
        .join(Vehicle, Vehicle.id == MaintenanceScheduleItem.vehicle_id)
        .outerjoin(EquipmentProfile, EquipmentProfile.vehicle_id == Vehicle.id)
        .outerjoin(EquipmentFamily, EquipmentFamily.id == EquipmentProfile.family_id)
        .outerjoin(
            MaintenanceWorkOrder,
            MaintenanceWorkOrder.schedule_item_id == MaintenanceScheduleItem.id,
        )
        .options(
            joinedload(MaintenanceScheduleItem.schedule),
            joinedload(MaintenanceScheduleItem.vehicle),
            joinedload(MaintenanceScheduleItem.work_order),
        )
    )
    if active_only:
        query = query.filter(Vehicle.ativo.is_(True), Vehicle.retirado_em.is_(None))
    if family_code:
        query = query.filter(func.lower(EquipmentFamily.code) == str(family_code).strip().lower())
    if vehicle_id:
        query = query.filter(Vehicle.id == vehicle_id)
    if location_id:
        query = query.filter(EquipmentProfile.operational_location_id == location_id)
    if status:
        normalized_status = str(status).strip().upper()
        query = query.filter(
            or_(
                and_(
                    MaintenanceWorkOrder.id.isnot(None),
                    MaintenanceWorkOrder.status == normalized_status,
                ),
                and_(
                    MaintenanceWorkOrder.id.is_(None),
                    MaintenanceScheduleItem.status == normalized_status,
                ),
            )
        )
    if source_type:
        query = query.filter(MaintenanceSchedule.source_type == str(source_type).strip().upper())
    if search and str(search).strip():
        term = f"%{str(search).strip()}%"
        query = query.filter(
            or_(
                MaintenanceWorkOrder.order_number.ilike(term),
                MaintenanceSchedule.title.ilike(term),
                MaintenanceSchedule.item_name.ilike(term),
                Vehicle.frota.ilike(term),
                Vehicle.modelo.ilike(term),
            )
        )
    if parsed_date_from:
        query = query.filter(MaintenanceScheduleItem.scheduled_date >= parsed_date_from)
    if parsed_date_to:
        query = query.filter(MaintenanceScheduleItem.scheduled_date <= parsed_date_to)

    total = query.order_by(None).count()
    rows = (
        query.order_by(
            MaintenanceScheduleItem.scheduled_date.desc().nullslast(),
            MaintenanceScheduleItem.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "schema_version": "pcm.base_mestre.v1",
        "items": [_master_base_row(item) for item in rows],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1 and total > 0,
        },
        "filters_applied": {
            "family_code": family_code,
            "vehicle_id": vehicle_id,
            "location_id": location_id,
            "status": status.upper() if status else None,
            "source_type": source_type.upper() if source_type else None,
            "search": search,
            "date_from": parsed_date_from.isoformat() if parsed_date_from else None,
            "date_to": parsed_date_to.isoformat() if parsed_date_to else None,
            "active_only": active_only,
        },
    }


MASTER_BASE_EXPORT_COLUMNS = (
    "intervention_id",
    "schedule_item_id",
    "schedule_id",
    "work_order_id",
    "order_number",
    "source_type",
    "source_origin_type",
    "title",
    "item_name",
    "status",
    "item_status",
    "work_order_status",
    "scheduled_date",
    "created_at",
    "updated_at",
    "age_days",
    "assigned_mechanic_user_id",
    "vehicle_id",
    "vehicle_frota",
    "vehicle_modelo",
    "vehicle_tipo",
    "vehicle_ativo",
    "family_id",
    "family_code",
    "family_name",
    "location_id",
    "location_code",
    "location_name",
    "operational_status",
    "latest_hourmeter",
)


def flatten_management_master_row(row: dict) -> dict:
    vehicle = row.get("vehicle") or {}
    family = row.get("family") or {}
    location = row.get("location") or {}
    return {
        "intervention_id": row.get("intervention_id"),
        "schedule_item_id": row.get("schedule_item_id"),
        "schedule_id": row.get("schedule_id"),
        "work_order_id": row.get("work_order_id"),
        "order_number": row.get("order_number"),
        "source_type": row.get("source_type"),
        "source_origin_type": row.get("source_origin_type"),
        "title": row.get("title"),
        "item_name": row.get("item_name"),
        "status": row.get("status"),
        "item_status": row.get("item_status"),
        "work_order_status": row.get("work_order_status"),
        "scheduled_date": row.get("scheduled_date"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "age_days": row.get("age_days"),
        "assigned_mechanic_user_id": row.get("assigned_mechanic_user_id"),
        "vehicle_id": vehicle.get("id"),
        "vehicle_frota": vehicle.get("frota"),
        "vehicle_modelo": vehicle.get("modelo"),
        "vehicle_tipo": vehicle.get("tipo"),
        "vehicle_ativo": vehicle.get("ativo"),
        "family_id": family.get("id"),
        "family_code": family.get("code"),
        "family_name": family.get("name"),
        "location_id": location.get("id"),
        "location_code": location.get("code"),
        "location_name": location.get("full_name") or location.get("name"),
        "operational_status": row.get("operational_status"),
        "latest_hourmeter": row.get("latest_hourmeter"),
    }


def build_management_master_export(**filters) -> dict:
    max_rows = 5000
    page_size = 100
    first_page = build_management_master_base(page=1, page_size=page_size, **filters)
    items = list(first_page["items"])
    total_pages = first_page["pagination"]["total_pages"]
    for page in range(2, total_pages + 1):
        if len(items) >= max_rows:
            break
        next_page = build_management_master_base(page=page, page_size=page_size, **filters)
        items.extend(next_page["items"])

    rows = [flatten_management_master_row(item) for item in items[:max_rows]]
    return {
        "schema_version": first_page["schema_version"],
        "columns": list(MASTER_BASE_EXPORT_COLUMNS),
        "items": rows,
        "total": first_page["pagination"]["total"],
        "exported": len(rows),
        "truncated": first_page["pagination"]["total"] > len(rows),
    }


def build_productivity_report() -> dict:
    users = (
        User.query.filter(User.tipo.in_(["motorista", "mecanico"]))
        .order_by(User.tipo.asc(), User.nome.asc())
        .all()
    )

    checklist_rows = (
        db.session.query(
            Checklist.user_id,
            func.count(Checklist.id).label("checklists"),
            func.count(case((ChecklistItem.status == "NC", 1))).label("nc_registradas"),
        )
        .outerjoin(ChecklistItem, ChecklistItem.checklist_id == Checklist.id)
        .group_by(Checklist.user_id)
        .all()
    )
    checklist_by_user = {
        user_id: {"checklists": int(checklists or 0), "nc_registradas": int(nc_registradas or 0)}
        for user_id, checklists, nc_registradas in checklist_rows
    }

    activity_rows = (
        db.session.query(
            ActivityItem.executado_por_login,
            func.count(ActivityItem.id).label("atividades_executadas"),
            func.sum(case((ActivityItem.status_execucao == "INSTALADO", 1), else_=0)).label("instalados"),
            func.sum(case((ActivityItem.status_execucao == "NAO_INSTALADO", 1), else_=0)).label("nao_instalados"),
        )
        .filter(ActivityItem.status_execucao != "PENDENTE")
        .group_by(ActivityItem.executado_por_login)
        .all()
    )
    activities_by_login = {
        login: {
            "atividades_executadas": int(total or 0),
            "instalados": int(installed or 0),
            "nao_instalados": int(not_installed or 0),
        }
        for login, total, installed, not_installed in activity_rows
        if login
    }

    assigned_rows = (
        db.session.query(
            Activity.assigned_mechanic_user_id,
            func.count(Activity.id).label("atividades_direcionadas"),
            func.sum(case((Activity.status == "FINALIZADA", 1), else_=0)).label("direcionadas_finalizadas"),
            func.sum(case((Activity.status == "ABERTA", 1), else_=0)).label("direcionadas_abertas"),
        )
        .filter(Activity.assigned_mechanic_user_id.isnot(None))
        .group_by(Activity.assigned_mechanic_user_id)
        .all()
    )
    assigned_by_user = {
        user_id: {
            "atividades_direcionadas": int(total or 0),
            "direcionadas_finalizadas": int(finalized or 0),
            "direcionadas_abertas": int(opened or 0),
        }
        for user_id, total, finalized, opened in assigned_rows
    }

    resolved_rows = (
        db.session.query(ChecklistItem.resolved_by_user_id, func.count(ChecklistItem.id))
        .filter(ChecklistItem.status == "NC", ChecklistItem.resolvido.is_(True), ChecklistItem.resolved_by_user_id.isnot(None))
        .group_by(ChecklistItem.resolved_by_user_id)
        .all()
    )
    checklist_resolved_by_user = {user_id: int(total or 0) for user_id, total in resolved_rows}

    mechanic_nc_rows = (
        db.session.query(
            MechanicNonConformity.created_by_user_id,
            func.count(MechanicNonConformity.id).label("internas_abertas"),
            func.sum(case((MechanicNonConformity.resolvido.is_(True), 1), else_=0)).label("internas_resolvidas"),
        )
        .group_by(MechanicNonConformity.created_by_user_id)
        .all()
    )
    mechanic_nc_by_user = {
        user_id: {"internas_abertas": int(opened or 0), "internas_resolvidas": int(resolved or 0)}
        for user_id, opened, resolved in mechanic_nc_rows
    }

    mechanic_nc_resolved_rows = (
        db.session.query(MechanicNonConformity.resolved_by_user_id, func.count(MechanicNonConformity.id))
        .filter(MechanicNonConformity.resolvido.is_(True), MechanicNonConformity.resolved_by_user_id.isnot(None))
        .group_by(MechanicNonConformity.resolved_by_user_id)
        .all()
    )
    mechanic_nc_resolved_by_user = {user_id: int(total or 0) for user_id, total in mechanic_nc_resolved_rows}

    wash_rows = (
        db.session.query(WashRecord.created_by_user_id, func.count(WashRecord.id))
        .filter(WashRecord.created_by_user_id.isnot(None))
        .group_by(WashRecord.created_by_user_id)
        .all()
    )
    washes_by_user = {user_id: int(total or 0) for user_id, total in wash_rows}

    rows = []
    totals = {
        "usuarios": len(users),
        "checklists": 0,
        "nc_registradas": 0,
        "nc_resolvidas": 0,
        "atividades_executadas": 0,
        "lavagens": 0,
        "pontuacao": 0,
    }
    for user in users:
        checklist = checklist_by_user.get(user.id, {"checklists": 0, "nc_registradas": 0})
        activity = activities_by_login.get(user.login, {"atividades_executadas": 0, "instalados": 0, "nao_instalados": 0})
        assigned = assigned_by_user.get(
            user.id,
            {"atividades_direcionadas": 0, "direcionadas_finalizadas": 0, "direcionadas_abertas": 0},
        )
        mechanic_nc = mechanic_nc_by_user.get(user.id, {"internas_abertas": 0, "internas_resolvidas": 0})
        nc_resolvidas = checklist_resolved_by_user.get(user.id, 0) + mechanic_nc_resolved_by_user.get(user.id, 0)
        lavagens = washes_by_user.get(user.id, 0)
        pontuacao = (
            checklist["checklists"]
            + activity["atividades_executadas"]
            + nc_resolvidas
            + lavagens
            + assigned["direcionadas_finalizadas"]
        )
        row = {
            "user": user.to_dict(),
            "checklists": checklist["checklists"],
            "nc_registradas": checklist["nc_registradas"],
            "nc_resolvidas": nc_resolvidas,
            "atividades_executadas": activity["atividades_executadas"],
            "instalados": activity["instalados"],
            "nao_instalados": activity["nao_instalados"],
            "atividades_direcionadas": assigned["atividades_direcionadas"],
            "direcionadas_finalizadas": assigned["direcionadas_finalizadas"],
            "direcionadas_abertas": assigned["direcionadas_abertas"],
            "nc_mecanico_abertas": mechanic_nc["internas_abertas"],
            "nc_mecanico_resolvidas": mechanic_nc["internas_resolvidas"],
            "lavagens": lavagens,
            "pontuacao": pontuacao,
        }
        rows.append(row)
        for key in totals:
            if key in row:
                totals[key] += row[key]

    rows.sort(key=lambda item: item["pontuacao"], reverse=True)
    return {"resumo": totals, "usuarios": rows}

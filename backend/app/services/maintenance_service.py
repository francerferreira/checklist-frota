from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta

from app.extensions import db
from app.models import Activity, ChecklistItem, Material, MaintenanceMaterial, MaintenanceSchedule, MaintenanceScheduleItem, WashQueueItem
from app.services.material_service import register_material_movement


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_type(value: str | None) -> str:
    normalized = (_clean(value) or "CHECKLIST_NC").upper()
    if normalized not in {"CHECKLIST_NC", "ATIVIDADE", "PREVENTIVA"}:
        raise ValueError("Tipo de manutenção inválido.")
    return normalized


def _normalize_status(value: str | None, default: str = "ABERTA") -> str:
    normalized = (_clean(value) or default).upper()
    allowed = {"ABERTA", "AGUARDANDO_MATERIAL", "PROGRAMADA", "EM_EXECUCAO", "CONCLUIDA", "CANCELADA"}
    if normalized not in allowed:
        raise ValueError("Status de programação inválido.")
    return normalized


def _normalize_item_status(value: str | None, default: str = "PENDENTE") -> str:
    normalized = (_clean(value) or default).upper()
    allowed = {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "INSTALADO", "NAO_EXECUTADO", "REPROGRAMADO", "CANCELADO"}
    if normalized not in allowed:
        raise ValueError("Status do item inválido.")
    return normalized


def _normalize_material_status(value: str | None, default: str = "AGUARDANDO_MATERIAL") -> str:
    normalized = (_clean(value) or default).upper()
    allowed = {"AGUARDANDO_MATERIAL", "EM_COMPRAS", "DISPONIVEL_EM_ESTOQUE", "RESERVADO", "UTILIZADO"}
    if normalized not in allowed:
        raise ValueError("Status do material inválido.")
    return normalized


def _parse_date(value: str | date | datetime | None, *, default: date | None = None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean(value)
    if not text:
        return default
    return datetime.fromisoformat(text).date()


def _normalize_daily_capacity(value, *, default: int = 1) -> int:
    try:
        capacity = int(value or default)
    except (TypeError, ValueError):
        raise ValueError("A capacidade diária deve ser maior que zero.")
    if capacity <= 0:
        raise ValueError("A capacidade diária deve ser maior que zero.")
    return capacity


def _month_label(year: int, month: int) -> str:
    labels = [
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ]
    return f"{labels[month - 1]} de {year}"


def _group_key_for_nc(item: ChecklistItem) -> str:
    return f"CHECKLIST_NC:{item.item_nome.strip().upper()}"


def ensure_schedule_for_checklist_item(item: ChecklistItem) -> MaintenanceSchedule:
    schedule = MaintenanceSchedule.query.filter_by(
        source_type="CHECKLIST_NC",
        source_key=_group_key_for_nc(item),
    ).first()

    if not schedule:
        schedule = MaintenanceSchedule(
            source_type="CHECKLIST_NC",
            source_key=_group_key_for_nc(item),
            title=f"Não conformidade - {item.item_nome}",
            item_name=item.item_nome,
            status="ABERTA",
            start_date=item.created_at.date() if item.created_at else date.today(),
            daily_capacity=1,
            created_by_user_id=item.checklist.user_id,
            observation=item.observacao,
        )
        db.session.add(schedule)
        db.session.flush()

    existing_item = MaintenanceScheduleItem.query.filter_by(checklist_item_id=item.id).first()
    if not existing_item:
        schedule_item = MaintenanceScheduleItem(
            schedule_id=schedule.id,
            vehicle_id=item.checklist.vehicle_id,
            checklist_item_id=item.id,
            status="PENDENTE",
            observation=item.observacao,
        )
        db.session.add(schedule_item)
        db.session.flush()

    recalculate_schedule(schedule)
    return schedule


def sync_checklist_non_conformities(items: list[ChecklistItem] | None = None) -> list[MaintenanceSchedule]:
    query = items if items is not None else ChecklistItem.query.filter_by(status="NC").all()
    schedules: list[MaintenanceSchedule] = []
    for item in query:
        schedule = ensure_schedule_for_checklist_item(item)
        schedules.append(schedule)
    db.session.commit()
    return schedules


def _refresh_schedule_materials(schedule: MaintenanceSchedule) -> None:
    total_items = max(len(schedule.items), 1)
    for link in schedule.materials:
        material = link.material
        total_required = int(link.quantity_per_vehicle or 1) * total_items
        installed_items = sum(1 for item in schedule.items if item.status == "INSTALADO")
        used_quantity = int(link.quantity_per_vehicle or 1) * installed_items
        remaining_required = max(total_required - used_quantity, 0)
        link.quantity_required = total_required
        if not material:
            link.status = "AGUARDANDO_MATERIAL"
            continue
        if remaining_required <= 0 and installed_items:
            link.status = "UTILIZADO"
            link.quantity_reserved = max(link.quantity_reserved or 0, used_quantity)
        elif (link.quantity_reserved or 0) >= remaining_required:
            link.status = "RESERVADO"
        elif material.quantidade_estoque >= remaining_required:
            link.status = "DISPONIVEL_EM_ESTOQUE"
        elif link.status != "EM_COMPRAS":
            link.status = "AGUARDANDO_MATERIAL"


def recalculate_schedule(schedule: MaintenanceSchedule) -> MaintenanceSchedule:
    _refresh_schedule_materials(schedule)
    materials = schedule.materials
    items = schedule.items

    if items and all(item.status == "INSTALADO" for item in items):
        schedule.status = "CONCLUIDA"
    elif any(item.status == "INSTALADO" for item in items):
        schedule.status = "EM_EXECUCAO"
    elif any(material.status in {"AGUARDANDO_MATERIAL", "EM_COMPRAS"} for material in materials):
        schedule.status = "AGUARDANDO_MATERIAL"
    elif any(item.status == "PROGRAMADO" for item in items):
        schedule.status = "PROGRAMADA"
    else:
        schedule.status = "ABERTA"
    return schedule


def _build_month_calendar(items: list[MaintenanceScheduleItem], *, year: int, month: int) -> dict:
    total_days = monthrange(year, month)[1]
    grouped: dict[str, list[MaintenanceScheduleItem]] = {
        date(year, month, day_number).isoformat(): []
        for day_number in range(1, total_days + 1)
    }

    for item in items:
        if not item.scheduled_date:
            continue
        key = item.scheduled_date.isoformat()
        grouped.setdefault(key, []).append(item)

    days = []
    for day_number in range(1, total_days + 1):
        current = date(year, month, day_number)
        rows = grouped.get(current.isoformat(), [])
        days.append(
            {
                "date": current.isoformat(),
                "day": day_number,
                "items": [item.to_dict() for item in rows],
                "total": len(rows),
                "pendentes": sum(1 for item in rows if item.status in {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"}),
                "instalados": sum(1 for item in rows if item.status == "INSTALADO"),
                "nao_executados": sum(1 for item in rows if item.status == "NAO_EXECUTADO"),
                "aguardando_material": sum(1 for item in rows if item.status == "AGUARDANDO_MATERIAL"),
            }
        )
    return {"days": days}


def build_maintenance_overview(*, year: int | None = None, month: int | None = None, assigned_to_user_id: int | None = None) -> dict:
    today = date.today()
    year = year or today.year
    month = month or today.month
    schedules = MaintenanceSchedule.query.order_by(MaintenanceSchedule.created_at.desc()).all()
    items = MaintenanceScheduleItem.query.order_by(MaintenanceScheduleItem.scheduled_date.asc().nullslast()).all()
    materials = MaintenanceMaterial.query.order_by(MaintenanceMaterial.created_at.desc()).all()

    items = [
        item
        for item in items
        if item.scheduled_date and item.scheduled_date.year == year and item.scheduled_date.month == month
    ]

    if assigned_to_user_id:
        schedules = [
            schedule
            for schedule in schedules
            if schedule.assigned_mechanic_user_id == assigned_to_user_id
            or any(item.assigned_mechanic_user_id == assigned_to_user_id for item in schedule.items)
        ]
        items = [
            item
            for item in items
            if item.assigned_mechanic_user_id == assigned_to_user_id
            or (item.schedule and item.schedule.assigned_mechanic_user_id == assigned_to_user_id)
        ]

    programmed = [item for item in items if item.scheduled_date]
    installed = sum(1 for item in items if item.status == "INSTALADO")
    not_executed = sum(1 for item in items if item.status == "NAO_EXECUTADO")
    pending = sum(1 for item in items if item.status in {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"})
    days_used = len({item.scheduled_date for item in programmed})
    total_done = installed + not_executed
    completion_base = len(items) or 1

    return {
        "periodo": {
            "ano": year,
            "mes": month,
            "rotulo": _month_label(year, month),
        },
        "resumo": {
            "programacoes": len(schedules),
            "itens": len(items),
            "materiais": len(materials),
            "aguardando_material": sum(1 for material in materials if material.status in {"AGUARDANDO_MATERIAL", "EM_COMPRAS"}),
            "programados": len(programmed),
            "instalados": installed,
            "nao_executados": not_executed,
            "pendentes": pending,
            "reprogramados": sum(1 for item in items if item.status == "REPROGRAMADO"),
            "dias_utilizados": days_used,
            "capacidade_media": round(len(programmed) / days_used, 1) if days_used else 0,
            "percentual_conclusao": round((total_done / completion_base) * 100, 1) if items else 0,
        },
        "cronograma": _build_month_calendar(items, year=year, month=month),
        "programacoes": [schedule.to_dict(include_items=True, include_materials=True) for schedule in schedules],
        "itens": [item.to_dict() for item in items],
        "materiais": [material.to_dict() for material in materials],
    }


def _distribute_dates(start_date: date, total_items: int, daily_capacity: int) -> list[date]:
    assigned_dates: list[date] = []
    current = start_date
    count_on_day = 0
    for _ in range(total_items):
        assigned_dates.append(current)
        count_on_day += 1
        if count_on_day >= daily_capacity:
            current = current + timedelta(days=1)
            count_on_day = 0
    return assigned_dates


def _ensure_preventive_wash_queue_items(schedule: MaintenanceSchedule) -> None:
    if schedule.source_type != "PREVENTIVA":
        return

    existing_by_vehicle = {item.vehicle_id: item for item in WashQueueItem.query.all()}
    max_position = db.session.query(db.func.max(WashQueueItem.queue_position)).scalar() or 0
    for schedule_item in schedule.items:
        if schedule_item.vehicle_id in existing_by_vehicle:
            continue
        vehicle = schedule_item.vehicle
        if not vehicle:
            continue
        max_position += 1
        queue_item = WashQueueItem(
            vehicle_id=vehicle.id,
            referencia=vehicle.frota,
            categoria="cavalo" if str(vehicle.tipo or "").lower() == "cavalo" else "auxiliar",
            queue_position=max_position,
        )
        db.session.add(queue_item)
        existing_by_vehicle[vehicle.id] = queue_item


def create_maintenance_schedule(payload: dict, *, created_by_user_id: int) -> MaintenanceSchedule:
    source_type = _normalize_type(payload.get("source_type") or payload.get("tipo") or payload.get("origem"))
    start_date = _parse_date(payload.get("start_date") or payload.get("data_inicio"), default=date.today())
    daily_capacity = _normalize_daily_capacity(payload.get("daily_capacity") or payload.get("capacidade_diaria"))

    schedule = MaintenanceSchedule(
        source_type=source_type,
        source_key=_clean(payload.get("source_key") or payload.get("chave_origem")),
        title=_clean(payload.get("title") or payload.get("titulo")) or "Programação de manutenção",
        item_name=_clean(payload.get("item_name") or payload.get("item_nome")),
        status=_normalize_status(payload.get("status"), default="ABERTA"),
        start_date=start_date,
        end_date=None,
        daily_capacity=daily_capacity,
        created_by_user_id=created_by_user_id,
        assigned_mechanic_user_id=payload.get("assigned_mechanic_user_id"),
        observation=_clean(payload.get("observation") or payload.get("observacao")),
    )
    db.session.add(schedule)
    db.session.flush()

    checklist_item_ids = [int(value) for value in payload.get("checklist_item_ids") or []]
    activity_ids = [int(value) for value in payload.get("activity_ids") or []]
    vehicle_ids = [int(value) for value in payload.get("vehicle_ids") or []]

    source_items: list[tuple[int, int | None, int | None]] = []
    if checklist_item_ids:
        checklist_items = ChecklistItem.query.filter(ChecklistItem.id.in_(checklist_item_ids)).all()
        for checklist_item in checklist_items:
            source_items.append((checklist_item.checklist.vehicle_id, checklist_item.id, None))
    elif activity_ids:
        activities = Activity.query.filter(Activity.id.in_(activity_ids)).all()
        for activity in activities:
            for activity_item in activity.items:
                source_items.append((activity_item.vehicle_id, None, activity.id))
    elif vehicle_ids:
        for vehicle_id in vehicle_ids:
            source_items.append((vehicle_id, None, None))
    else:
        raise ValueError("Selecione ao menos um veículo, não conformidade ou atividade.")

    assigned_dates = _distribute_dates(start_date, len(source_items), daily_capacity)
    for index, (vehicle_id, checklist_item_id, activity_id) in enumerate(source_items):
        db.session.add(
            MaintenanceScheduleItem(
                schedule_id=schedule.id,
                vehicle_id=vehicle_id,
                checklist_item_id=checklist_item_id,
                activity_id=activity_id,
                scheduled_date=assigned_dates[index],
                status="PROGRAMADO",
                assigned_mechanic_user_id=schedule.assigned_mechanic_user_id,
            )
        )

    schedule.end_date = assigned_dates[-1] if assigned_dates else start_date
    db.session.flush()
    _ensure_preventive_wash_queue_items(schedule)
    recalculate_schedule(schedule)
    db.session.commit()
    return schedule


def program_maintenance_schedule(schedule_id: int, payload: dict, *, user_id: int) -> MaintenanceSchedule:
    schedule = MaintenanceSchedule.query.get_or_404(schedule_id)
    start_date = _parse_date(payload.get("start_date") or payload.get("data_inicio"), default=schedule.start_date or date.today())
    if not start_date:
        start_date = date.today()
    daily_capacity = _normalize_daily_capacity(
        payload.get("daily_capacity") or payload.get("capacidade_diaria") or schedule.daily_capacity
    )

    assigned_mechanic = payload.get("assigned_mechanic_user_id")
    if assigned_mechanic is not None:
        schedule.assigned_mechanic_user_id = int(assigned_mechanic) if str(assigned_mechanic).strip() else None

    programmable_items = [
        item
        for item in sorted(schedule.items, key=lambda row: (row.scheduled_date or date.max, row.id))
        if item.status not in {"INSTALADO", "CANCELADO"}
    ]
    assigned_dates = _distribute_dates(start_date, len(programmable_items), daily_capacity)
    for index, item in enumerate(programmable_items):
        item.scheduled_date = assigned_dates[index]
        item.status = "PROGRAMADO" if item.status in {"PENDENTE", "AGUARDANDO_MATERIAL", "REPROGRAMADO", "NAO_EXECUTADO"} else item.status
        item.assigned_mechanic_user_id = schedule.assigned_mechanic_user_id

    schedule.start_date = assigned_dates[0] if assigned_dates else start_date
    schedule.end_date = assigned_dates[-1] if assigned_dates else start_date
    schedule.daily_capacity = daily_capacity
    db.session.flush()
    _ensure_preventive_wash_queue_items(schedule)
    recalculate_schedule(schedule)
    db.session.commit()
    return schedule


def reprogram_schedule_item(item_id: int, payload: dict, *, user) -> MaintenanceScheduleItem:
    item = MaintenanceScheduleItem.query.get_or_404(item_id)
    scheduled_date = _parse_date(payload.get("scheduled_date") or payload.get("data"))
    if not scheduled_date:
        raise ValueError("Informe a nova data do cronograma.")

    assigned_mechanic = payload.get("assigned_mechanic_user_id")
    if assigned_mechanic is not None:
        item.assigned_mechanic_user_id = int(assigned_mechanic) if str(assigned_mechanic).strip() else None

    item.scheduled_date = scheduled_date
    if item.status not in {"INSTALADO", "CANCELADO"}:
        item.status = "REPROGRAMADO"
    item.observation = _clean(payload.get("observation") or payload.get("observacao")) or item.observation
    recalculate_schedule(item.schedule)
    db.session.commit()
    return item


def link_schedule_material(schedule_id: int, payload: dict, *, user_id: int) -> MaintenanceMaterial:
    schedule = MaintenanceSchedule.query.get_or_404(schedule_id)
    material_id = payload.get("material_id")
    if not material_id:
        raise ValueError("Informe o material.")

    material = Material.query.get(material_id)
    if not material or not material.ativo:
        raise ValueError("Material informado e invalido ou esta inativo.")

    quantity_per_vehicle = int(payload.get("quantity_per_vehicle") or payload.get("quantidade_por_veiculo") or 1)
    if quantity_per_vehicle <= 0:
        raise ValueError("A quantidade por veículo deve ser maior que zero.")

    total_required = quantity_per_vehicle * max(len(schedule.items), 1)
    existing = MaintenanceMaterial.query.filter_by(schedule_id=schedule.id, material_id=material.id).first()
    if existing:
        existing.quantity_per_vehicle = quantity_per_vehicle
        existing.quantity_required = total_required
        existing.status = _normalize_material_status(payload.get("status"), default=existing.status)
        existing.observation = _clean(payload.get("observation") or payload.get("observacao")) or existing.observation
        link = existing
    else:
        status = _normalize_material_status(payload.get("status"), default="AGUARDANDO_MATERIAL")
        if material.quantidade_estoque >= total_required and status == "AGUARDANDO_MATERIAL":
            status = "DISPONIVEL_EM_ESTOQUE"
        link = MaintenanceMaterial(
            schedule_id=schedule.id,
            material_id=material.id,
            quantity_per_vehicle=quantity_per_vehicle,
            quantity_required=total_required,
            quantity_reserved=0,
            status=status,
            observation=_clean(payload.get("observation") or payload.get("observacao")),
        )
        db.session.add(link)

    if link.status == "DISPONIVEL_EM_ESTOQUE" and material.quantidade_estoque >= total_required:
        link.quantity_reserved = total_required
    elif material.quantidade_estoque < total_required:
        link.status = "EM_COMPRAS"

    recalculate_schedule(schedule)
    db.session.commit()
    return link


def _can_execute_with_material(item: MaintenanceScheduleItem) -> tuple[bool, str | None]:
    schedule = item.schedule
    if not schedule:
        return False, "Programação não encontrada."

    _refresh_schedule_materials(schedule)
    for link in schedule.materials:
        material = link.material
        required = int(link.quantity_per_vehicle or 1)
        if not material:
            return False, "Material vinculado não encontrado."
        if link.status in {"AGUARDANDO_MATERIAL", "EM_COMPRAS"}:
            return False, f"Material ainda não liberado para {material.referencia}."
        if material.quantidade_estoque < required:
            return False, f"Material insuficiente para {material.referencia}."
    return True, None


def update_schedule_item(item_id: int, payload: dict, *, user) -> MaintenanceScheduleItem:
    item = MaintenanceScheduleItem.query.get_or_404(item_id)
    new_status = _normalize_item_status(payload.get("status") or payload.get("status_execucao"))
    item.observation = _clean(payload.get("observation") or payload.get("observacao")) or item.observation
    item.not_executed_reason = _clean(payload.get("not_executed_reason") or payload.get("motivo")) or item.not_executed_reason
    item.photo_after = _clean(payload.get("photo_after") or payload.get("foto_depois")) or item.photo_after
    item.assigned_mechanic_user_id = payload.get("assigned_mechanic_user_id") or item.assigned_mechanic_user_id

    if new_status == "INSTALADO":
        allowed, message = _can_execute_with_material(item)
        if not allowed:
            raise ValueError(message or "Material indisponível para concluir a instalação.")
        for link in item.schedule.materials:
            required = int(link.quantity_per_vehicle or 1)
            register_material_movement(
                link.material,
                quantity=required,
                movement_type="ATIVIDADE",
                delta=-required,
                observation=f"Baixa para manutenção: {item.schedule.title}",
                activity_id=item.activity_id,
                checklist_item_id=item.checklist_item_id,
            )
            link.quantity_reserved = min(int(link.quantity_required or required), int(link.quantity_reserved or 0) + required)
        if item.checklist_item:
            item.checklist_item.resolvido = True
            item.checklist_item.data_resolucao = datetime.utcnow()
            item.checklist_item.resolved_by_user_id = user.id
            item.checklist_item.foto_depois = item.photo_after or item.checklist_item.foto_depois
            if item.observation:
                current_observation = item.checklist_item.observacao or ""
                suffix = f"Resolução de manutenção: {item.observation}"
                if suffix not in current_observation:
                    item.checklist_item.observacao = f"{current_observation}\n{suffix}".strip()
        item.executed_by_user_id = user.id
        item.executed_at = datetime.utcnow()
        item.status = "INSTALADO"
    elif new_status == "NAO_EXECUTADO":
        item.status = new_status
        item.executed_by_user_id = user.id
        item.executed_at = datetime.utcnow()
        if not item.not_executed_reason:
            raise ValueError("Informe o motivo para marcar como não executado.")
    else:
        item.status = new_status

    recalculate_schedule(item.schedule)
    db.session.commit()
    return item


def mechanic_items_for_user(user_id: int) -> list[MaintenanceScheduleItem]:
    rows = MaintenanceScheduleItem.query.order_by(MaintenanceScheduleItem.scheduled_date.asc().nullslast()).all()
    return [
        item
        for item in rows
        if item.assigned_mechanic_user_id == user_id
        or (item.schedule and item.schedule.assigned_mechanic_user_id == user_id)
    ]


def build_vehicle_maintenance_history(vehicle_id: int) -> dict:
    items = (
        MaintenanceScheduleItem.query.filter_by(vehicle_id=vehicle_id)
        .order_by(MaintenanceScheduleItem.scheduled_date.desc().nullslast(), MaintenanceScheduleItem.created_at.desc())
        .all()
    )
    return {
        "manutencoes": [item.to_dict() for item in items],
    }


def _maintenance_report_items(*, year: int | None = None, month: int | None = None) -> list[MaintenanceScheduleItem]:
    query = MaintenanceScheduleItem.query.order_by(MaintenanceScheduleItem.scheduled_date.desc().nullslast(), MaintenanceScheduleItem.id.desc())
    if year:
        query = query.filter(db.extract("year", MaintenanceScheduleItem.scheduled_date) == year)
    if month:
        query = query.filter(db.extract("month", MaintenanceScheduleItem.scheduled_date) == month)
    return query.all()


def _item_report_row(item: MaintenanceScheduleItem) -> dict:
    schedule = item.schedule
    vehicle = item.vehicle
    materials = schedule.materials if schedule else []
    material_label = "; ".join(
        f"{link.material.referencia if link.material else '-'} ({link.quantity_per_vehicle} por veículo)"
        for link in materials
    ) or "-"
    return {
        "data": item.scheduled_date.strftime("%d/%m/%Y") if item.scheduled_date else "-",
        "veiculo": vehicle.frota if vehicle else "-",
        "placa": vehicle.placa if vehicle else "-",
        "tipo": schedule.source_type.replace("_", " ").title() if schedule else "-",
        "programacao": schedule.title if schedule else "-",
        "status": item.status.replace("_", " "),
        "mecanico": (item.assigned_mechanic.nome if item.assigned_mechanic else None)
        or (schedule.assigned_mechanic.nome if schedule and schedule.assigned_mechanic else "-"),
        "materiais": material_label,
        "parecer": item.observation or item.not_executed_reason or "-",
    }


def build_maintenance_report_payload(
    *,
    report_type: str = "mensal",
    year: int | None = None,
    month: int | None = None,
    mechanic_id: int | None = None,
    vehicle_id: int | None = None,
) -> dict:
    today = date.today()
    year = year or today.year
    month = month or today.month
    normalized_type = (report_type or "mensal").strip().lower()
    items = _maintenance_report_items(year=year, month=month)

    if normalized_type == "preventiva":
        items = [item for item in items if item.schedule and item.schedule.source_type == "PREVENTIVA"]
    elif normalized_type == "mecanico":
        if mechanic_id:
            items = [
                item
                for item in items
                if item.assigned_mechanic_user_id == mechanic_id or (item.schedule and item.schedule.assigned_mechanic_user_id == mechanic_id)
            ]
    elif normalized_type == "veiculo":
        if vehicle_id:
            items = [item for item in items if item.vehicle_id == vehicle_id]
    elif normalized_type == "material":
        items = [item for item in items if item.schedule and item.schedule.materials]
    elif normalized_type == "pendencias":
        items = [item for item in items if item.status in {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO", "NAO_EXECUTADO"}]

    titles = {
        "mensal": "Relatório mensal de manutenção",
        "preventiva": "Relatório de preventiva",
        "mecanico": "Relatório por mecânico",
        "veiculo": "Relatório por veículo",
        "material": "Relatório de materiais utilizados",
        "pendencias": "Relatório de pendências",
    }
    columns = [
        ("Data", "data"),
        ("Veículo", "veiculo"),
        ("Placa", "placa"),
        ("Tipo", "tipo"),
        ("Programação", "programacao"),
        ("Status", "status"),
        ("Mecânico", "mecanico"),
        ("Materiais", "materiais"),
        ("Parecer", "parecer"),
    ]
    return {
        "title": titles.get(normalized_type, titles["mensal"]),
        "subtitle": f"{_month_label(year, month).title()} | {len(items)} registros",
        "period_label": _month_label(year, month).title(),
        "columns": columns,
        "rows": [_item_report_row(item) for item in items],
        "filename": f"relatorio_manutencao_{normalized_type}_{year}_{month:02d}.pdf",
    }


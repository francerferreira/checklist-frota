from __future__ import annotations

from datetime import datetime

from app.extensions import db
from app.utils.timezone import now_manaus_naive


PACKAGE_SOURCE_PREFIX = "PACOTE_RESOLUCAO:"
EMERGENCY_SOURCE_PREFIX = "EMERGENCIA:"
PLANNED_CORRECTIVE_SOURCE_PREFIX = "CORRETIVA_PROGRAMADA:"


def _package_ids_from_source_key(source_key: str | None) -> list[int]:
    raw = str(source_key or "")
    if not raw.startswith(PACKAGE_SOURCE_PREFIX):
        return []
    values: list[int] = []
    for chunk in raw.removeprefix(PACKAGE_SOURCE_PREFIX).split(","):
        try:
            number = int(str(chunk).strip())
        except (TypeError, ValueError):
            continue
        if number > 0:
            values.append(number)
    return values


def _package_reference_label(package_ids: list[int]) -> str | None:
    if not package_ids:
        return None
    if len(package_ids) == 1:
        return f"Pacote #{package_ids[0]}"
    return "Pacotes " + ", ".join(f"#{package_id}" for package_id in package_ids)


def _vehicle_family_from_items(items: list["MaintenanceScheduleItem"]) -> str:
    families = {
        str((item.vehicle.tipo if item.vehicle else "") or "").strip().lower()
        for item in items
        if item.vehicle and str(item.vehicle.tipo or "").strip()
    }
    families.discard("")
    if not families:
        return "ambos"
    if len(families) == 1:
        return families.pop()
    return "misto"


class MaintenanceSchedule(db.Model):
    __tablename__ = "maintenance_schedules"

    id = db.Column(db.Integer, primary_key=True)
    source_type = db.Column(db.String(30), nullable=False, index=True)
    source_key = db.Column(db.String(180), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    item_name = db.Column(db.String(160), nullable=True, index=True)
    status = db.Column(db.String(30), nullable=False, default="ABERTA", index=True)
    start_date = db.Column(db.Date, nullable=True, index=True)
    end_date = db.Column(db.Date, nullable=True, index=True)
    daily_capacity = db.Column(db.Integer, nullable=False, default=1)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    assigned_mechanic_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    observation = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    # Evita JOINs profundos em cascata. No SQLite, carregar toda a árvore de
    # manutenção em uma única consulta ultrapassa o limite de 64 tabelas.
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="select")
    assigned_mechanic = db.relationship("User", foreign_keys=[assigned_mechanic_user_id], lazy="select")
    items = db.relationship("MaintenanceScheduleItem", back_populates="schedule", cascade="all, delete-orphan", lazy="select")
    materials = db.relationship("MaintenanceMaterial", back_populates="schedule", cascade="all, delete-orphan", lazy="select")
    work_orders = db.relationship("MaintenanceWorkOrder", back_populates="schedule", cascade="all, delete-orphan", lazy="select")

    __table_args__ = (
        db.CheckConstraint(
            "source_type IN ('CHECKLIST_NC', 'ATIVIDADE', 'PREVENTIVA')",
            name="ck_maintenance_schedule_source_type",
        ),
        db.CheckConstraint(
            "status IN ('ABERTA', 'AGUARDANDO_MATERIAL', 'PROGRAMADA', 'EM_EXECUCAO', 'CONCLUIDA', 'CANCELADA')",
            name="ck_maintenance_schedule_status",
        ),
        db.CheckConstraint(
            "daily_capacity > 0",
            name="ck_maintenance_schedule_daily_capacity_positive",
        ),
        db.UniqueConstraint("source_type", "source_key", name="uq_maintenance_schedule_source"),
    )

    def counts(self) -> dict:
        total = len(self.items)
        installed = sum(1 for item in self.items if item.status == "INSTALADO")
        pending = sum(1 for item in self.items if item.status in {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"})
        not_executed = sum(1 for item in self.items if item.status == "NAO_EXECUTADO")
        return {
            "total": total,
            "instalados": installed,
            "pendentes": pending,
            "nao_executados": not_executed,
            "reprogramados": sum(1 for item in self.items if item.status == "REPROGRAMADO"),
        }

    def package_ids(self) -> list[int]:
        return _package_ids_from_source_key(self.source_key)

    def package_reference_label(self) -> str | None:
        return _package_reference_label(self.package_ids())

    def vehicle_family(self) -> str:
        return _vehicle_family_from_items(self.items)

    def blocker_summary(self) -> dict:
        blocked_materials = sum(1 for material in self.materials if material.status in {"AGUARDANDO_MATERIAL", "EM_COMPRAS"})
        blocked_work_orders = sum(1 for order in self.work_orders if order.status == "AGUARDANDO_MATERIAL")
        open_items = sum(1 for item in self.items if item.status in {"PENDENTE", "PROGRAMADO", "AGUARDANDO_MATERIAL", "REPROGRAMADO"})
        return {
            "sem_responsavel": bool(open_items and not self.assigned_mechanic_user_id),
            "materiais_bloqueados": blocked_materials,
            "ordens_bloqueadas": blocked_work_orders,
            "itens_em_aberto": open_items,
        }

    def material_context_summary(self) -> dict:
        return {
            "familia_veiculo": self.vehicle_family(),
            "quantidade_links": len(self.materials),
            "quantidade_prevista": sum(int(material.quantity_required or 0) for material in self.materials),
            "quantidade_reservada": sum(int(material.quantity_reserved or 0) for material in self.materials),
            "quantidade_bloqueada": sum(
                1 for material in self.materials if material.status in {"AGUARDANDO_MATERIAL", "EM_COMPRAS"}
            ),
        }

    def source_origin_type(self) -> str:
        source_key = str(self.source_key or "")
        if source_key.startswith(PACKAGE_SOURCE_PREFIX):
            return "PACOTE_RESOLUCAO"
        if source_key.startswith(EMERGENCY_SOURCE_PREFIX):
            return "EMERGENCIAL"
        if source_key.startswith(PLANNED_CORRECTIVE_SOURCE_PREFIX):
            return "CORRETIVA_PROGRAMADA"
        return self.source_type

    def to_dict(self, include_items: bool = False, include_materials: bool = False, include_work_orders: bool = False) -> dict:
        data = {
            "id": self.id,
            "source_type": self.source_type,
            "source_origin_type": self.source_origin_type(),
            "source_key": self.source_key,
            "title": self.title,
            "item_name": self.item_name,
            "status": self.status,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "daily_capacity": self.daily_capacity,
            "created_by_user_id": self.created_by_user_id,
            "assigned_mechanic_user_id": self.assigned_mechanic_user_id,
            "observation": self.observation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by.to_dict() if self.created_by else None,
            "assigned_mechanic": self.assigned_mechanic.to_dict() if self.assigned_mechanic else None,
            "resumo": self.counts(),
            "package_ids": self.package_ids(),
            "package_reference_label": self.package_reference_label(),
            "vehicle_family": self.vehicle_family(),
            "bloqueios_resumo": self.blocker_summary(),
            "materiais_resumo": self.material_context_summary(),
            "ordens_servico_resumo": {
                "total": len(self.work_orders),
                "abertas": sum(1 for order in self.work_orders if order.status in {"ABERTA", "PROGRAMADA", "AGUARDANDO_MATERIAL", "EM_EXECUCAO", "REPROGRAMADA"}),
                "concluidas": sum(1 for order in self.work_orders if order.status == "CONCLUIDA"),
                "nao_executadas": sum(1 for order in self.work_orders if order.status == "NAO_EXECUTADA"),
            },
        }
        if include_items:
            data["itens"] = [item.to_dict() for item in self.items]
        if include_materials:
            data["materiais"] = [material.to_dict() for material in self.materials]
        if include_work_orders:
            data["ordens_servico"] = [work_order.to_dict() for work_order in self.work_orders]
        return data


class MaintenanceScheduleItem(db.Model):
    __tablename__ = "maintenance_schedule_items"

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("maintenance_schedules.id"), nullable=False, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    checklist_item_id = db.Column(db.Integer, db.ForeignKey("checklist_items.id"), nullable=True, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=True, index=True)
    assigned_mechanic_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    scheduled_date = db.Column(db.Date, nullable=True, index=True)
    status = db.Column(db.String(30), nullable=False, default="PENDENTE", index=True)
    observation = db.Column(db.Text, nullable=True)
    not_executed_reason = db.Column(db.Text, nullable=True)
    photo_after = db.Column(db.String(255), nullable=True)
    executed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    executed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    schedule = db.relationship("MaintenanceSchedule", back_populates="items")
    vehicle = db.relationship("Vehicle", lazy="joined")
    checklist_item = db.relationship("ChecklistItem", lazy="joined")
    activity = db.relationship("Activity", lazy="joined")
    assigned_mechanic = db.relationship("User", foreign_keys=[assigned_mechanic_user_id], lazy="joined")
    executed_by = db.relationship("User", foreign_keys=[executed_by_user_id], lazy="joined")
    work_order = db.relationship("MaintenanceWorkOrder", back_populates="schedule_item", uselist=False, lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('PENDENTE', 'PROGRAMADO', 'AGUARDANDO_MATERIAL', 'INSTALADO', 'NAO_EXECUTADO', 'REPROGRAMADO', 'CANCELADO')",
            name="ck_maintenance_schedule_item_status",
        ),
        db.UniqueConstraint("checklist_item_id", name="uq_maintenance_schedule_checklist_item"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "vehicle_id": self.vehicle_id,
            "checklist_item_id": self.checklist_item_id,
            "activity_id": self.activity_id,
            "assigned_mechanic_user_id": self.assigned_mechanic_user_id,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "status": self.status,
            "observation": self.observation,
            "not_executed_reason": self.not_executed_reason,
            "photo_after": self.photo_after,
            "executed_by_user_id": self.executed_by_user_id,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "schedule": self.schedule.to_dict(include_materials=True) if self.schedule else None,
            "vehicle": self.vehicle.to_dict() if self.vehicle else None,
            "checklist_item": self.checklist_item.to_dict() if self.checklist_item else None,
            "activity": self.activity.to_dict() if self.activity else None,
            "assigned_mechanic": self.assigned_mechanic.to_dict() if self.assigned_mechanic else None,
            "executed_by": self.executed_by.to_dict() if self.executed_by else None,
            "work_order": self.work_order.to_dict() if self.work_order else None,
        }


class MaintenanceMaterial(db.Model):
    __tablename__ = "maintenance_materials"

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("maintenance_schedules.id"), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True)
    quantity_per_vehicle = db.Column(db.Integer, nullable=False, default=1)
    quantity_required = db.Column(db.Integer, nullable=False, default=1)
    quantity_reserved = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(30), nullable=False, default="AGUARDANDO_MATERIAL", index=True)
    observation = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    schedule = db.relationship("MaintenanceSchedule", back_populates="materials")
    material = db.relationship("Material", lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('AGUARDANDO_MATERIAL', 'EM_COMPRAS', 'DISPONIVEL_EM_ESTOQUE', 'RESERVADO', 'UTILIZADO')",
            name="ck_maintenance_material_status",
        ),
        db.CheckConstraint("quantity_per_vehicle > 0", name="ck_maintenance_material_quantity_per_vehicle_positive"),
        db.CheckConstraint("quantity_required >= 0", name="ck_maintenance_material_quantity_required_non_negative"),
        db.CheckConstraint("quantity_reserved >= 0", name="ck_maintenance_material_quantity_reserved_non_negative"),
    )

    def to_dict(self) -> dict:
        schedule = self.schedule
        package_ids = schedule.package_ids() if schedule else []
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "material_id": self.material_id,
            "quantity_per_vehicle": self.quantity_per_vehicle,
            "quantity_required": self.quantity_required,
            "quantity_reserved": self.quantity_reserved,
            "status": self.status,
            "observation": self.observation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "blocked": str(self.status or "").upper() in {"AGUARDANDO_MATERIAL", "EM_COMPRAS"},
            "schedule_title": schedule.title if schedule else None,
            "source_origin_type": schedule.source_origin_type() if schedule else None,
            "vehicle_family": schedule.vehicle_family() if schedule else "ambos",
            "package_ids": package_ids,
            "package_reference_label": schedule.package_reference_label() if schedule else None,
            "linked_work_orders_count": len(schedule.work_orders) if schedule else 0,
            "linked_work_orders": [order.order_number for order in (schedule.work_orders if schedule else []) if order.order_number],
            "material": self.material.to_dict() if self.material else None,
        }


class MaintenanceWorkOrder(db.Model):
    __tablename__ = "maintenance_work_orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(40), nullable=False, unique=True, index=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey("maintenance_schedules.id"), nullable=False, index=True)
    schedule_item_id = db.Column(db.Integer, db.ForeignKey("maintenance_schedule_items.id"), nullable=False, unique=True, index=True)
    resolution_package_id = db.Column(db.Integer, db.ForeignKey("resolution_packages.id"), nullable=True, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    assigned_mechanic_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    opened_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    item_name = db.Column(db.String(160), nullable=True, index=True)
    failure_cause = db.Column(db.String(160), nullable=True, index=True)
    affected_component = db.Column(db.String(160), nullable=True, index=True)
    work_shift = db.Column(db.String(30), nullable=True, index=True)
    budget_amount = db.Column(db.Numeric(14, 2), nullable=True)
    budget_notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="ABERTA", index=True)
    scheduled_date = db.Column(db.Date, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    schedule = db.relationship("MaintenanceSchedule", back_populates="work_orders")
    schedule_item = db.relationship("MaintenanceScheduleItem", back_populates="work_order")
    vehicle = db.relationship("Vehicle", lazy="joined")
    assigned_mechanic = db.relationship("User", foreign_keys=[assigned_mechanic_user_id], lazy="joined")
    opened_by = db.relationship("User", foreign_keys=[opened_by_user_id], lazy="joined")
    resolution_package = db.relationship("ResolutionPackage", lazy="joined")
    execution = db.relationship("WorkOrderExecution", back_populates="work_order", uselist=False, lazy="select", cascade="all, delete-orphan")
    cost_records = db.relationship("MaintenanceWorkOrderCost", back_populates="work_order", lazy="select", cascade="all, delete-orphan")
    preventive_executions = db.relationship("PreventiveExecution", back_populates="work_order", lazy="select")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('ABERTA', 'PROGRAMADA', 'AGUARDANDO_MATERIAL', 'EM_EXECUCAO', 'CONCLUIDA', 'NAO_EXECUTADA', 'REPROGRAMADA', 'CANCELADA')",
            name="ck_maintenance_work_order_status",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_number": self.order_number,
            "schedule_id": self.schedule_id,
            "schedule_item_id": self.schedule_item_id,
            "resolution_package_id": self.resolution_package_id,
            "vehicle_id": self.vehicle_id,
            "assigned_mechanic_user_id": self.assigned_mechanic_user_id,
            "opened_by_user_id": self.opened_by_user_id,
            "title": self.title,
            "item_name": self.item_name,
            "failure_cause": self.failure_cause,
            "affected_component": self.affected_component,
            "work_shift": self.work_shift,
            "budget_amount": float(self.budget_amount) if self.budget_amount is not None else None,
            "budget_notes": self.budget_notes,
            "status": self.status,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "schedule_title": self.schedule.title if self.schedule else None,
            "resolution_package_label": f"Pacote #{self.resolution_package_id}" if self.resolution_package_id else None,
            "vehicle": self.vehicle.to_dict() if self.vehicle else None,
            "assigned_mechanic": self.assigned_mechanic.to_dict() if self.assigned_mechanic else None,
            "opened_by": self.opened_by.to_dict() if self.opened_by else None,
        }


class MaintenanceWorkOrderCost(db.Model):
    __tablename__ = "maintenance_work_order_costs"

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("maintenance_work_orders.id"), nullable=False, index=True)
    category = db.Column(db.String(30), nullable=False, index=True)
    description = db.Column(db.String(200), nullable=False)
    supplier_name = db.Column(db.String(160), nullable=True, index=True)
    affected_component = db.Column(db.String(160), nullable=True, index=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    occurred_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    notes = db.Column(db.Text, nullable=True)
    recorded_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    work_order = db.relationship("MaintenanceWorkOrder", back_populates="cost_records")
    recorded_by = db.relationship("User", foreign_keys=[recorded_by_user_id], lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "category IN ('PECA', 'MAO_DE_OBRA', 'SERVICO_EXTERNO')",
            name="ck_maintenance_work_order_cost_category",
        ),
        db.CheckConstraint("amount >= 0", name="ck_maintenance_work_order_cost_amount_non_negative"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "category": self.category,
            "description": self.description,
            "supplier_name": self.supplier_name,
            "affected_component": self.affected_component,
            "amount": float(self.amount or 0),
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "notes": self.notes,
            "recorded_by_user_id": self.recorded_by_user_id,
            "recorded_by": self.recorded_by.to_dict() if self.recorded_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

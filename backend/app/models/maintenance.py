from __future__ import annotations

from datetime import datetime

from app.extensions import db


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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    assigned_mechanic = db.relationship("User", foreign_keys=[assigned_mechanic_user_id], lazy="joined")
    items = db.relationship("MaintenanceScheduleItem", back_populates="schedule", cascade="all, delete-orphan", lazy="joined")
    materials = db.relationship("MaintenanceMaterial", back_populates="schedule", cascade="all, delete-orphan", lazy="joined")

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

    def to_dict(self, include_items: bool = False, include_materials: bool = False) -> dict:
        data = {
            "id": self.id,
            "source_type": self.source_type,
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
        }
        if include_items:
            data["itens"] = [item.to_dict() for item in self.items]
        if include_materials:
            data["materiais"] = [material.to_dict() for material in self.materials]
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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    schedule = db.relationship("MaintenanceSchedule", back_populates="items")
    vehicle = db.relationship("Vehicle", lazy="joined")
    checklist_item = db.relationship("ChecklistItem", lazy="joined")
    activity = db.relationship("Activity", lazy="joined")
    assigned_mechanic = db.relationship("User", foreign_keys=[assigned_mechanic_user_id], lazy="joined")
    executed_by = db.relationship("User", foreign_keys=[executed_by_user_id], lazy="joined")

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
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

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
            "material": self.material.to_dict() if self.material else None,
        }

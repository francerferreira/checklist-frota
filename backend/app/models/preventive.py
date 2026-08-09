from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.utils.timezone import now_manaus_naive


PREVENTIVE_EXECUTION_STATUSES = (
    "PLANEJADA",
    "PROGRAMADA",
    "EM_EXECUCAO",
    "CONCLUIDA",
    "CANCELADA",
    "NAO_EXECUTADA",
)

PREVENTIVE_STAGE_TYPES = (
    "MOTOR",
    "ELETRICA",
    "LUBRIFICACAO",
    "ESTRUTURAL",
    "INSPECAO",
    "CHECKLIST",
    "TESTE_OPERACIONAL",
)

PREVENTIVE_STAGE_STATUSES = (
    "PENDENTE",
    "EM_EXECUCAO",
    "CONCLUIDA",
    "BLOQUEADA",
    "NAO_EXECUTADA",
)

PREVENTIVE_MATERIAL_STATUSES = (
    "SOLICITADO",
    "SEPARADO",
    "UTILIZADO",
    "CANCELADO",
)


def _number(value):
    if value is None:
        return None
    return float(value) if isinstance(value, Decimal) else float(value)


def _preventive_label(value):
    if value is None:
        return None
    try:
        hours = int(Decimal(str(value)))
    except Exception:
        return None
    return f"{hours} h" if 500 <= hours <= 6000 and hours % 500 == 0 else None


class PreventiveExecution(db.Model):
    """Execução concreta de um plano preventivo para um equipamento."""

    __tablename__ = "preventive_executions"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    preventive_plan_id = db.Column(db.Integer, db.ForeignKey("preventive_plans.id"), nullable=False, index=True)
    cycle_hourmeter = db.Column(db.Numeric(12, 2), nullable=True)
    hourmeter_start = db.Column(db.Numeric(12, 2), nullable=True)
    hourmeter_execution = db.Column(db.Numeric(12, 2), nullable=True)
    scheduled_date = db.Column(db.Date, nullable=True, index=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="PLANEJADA", index=True)
    responsible_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("maintenance_work_orders.id"), nullable=True, index=True)
    observation = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    vehicle = db.relationship("Vehicle", back_populates="preventive_executions", lazy="joined")
    preventive_plan = db.relationship("PreventivePlan", back_populates="executions", lazy="joined")
    responsible_user = db.relationship("User", foreign_keys=[responsible_user_id], lazy="joined")
    work_order = db.relationship("MaintenanceWorkOrder", back_populates="preventive_executions", lazy="joined")
    stages = db.relationship(
        "PreventiveStage",
        back_populates="preventive_execution",
        cascade="all, delete-orphan",
        order_by="PreventiveStage.id",
        lazy="selectin",
    )
    materials = db.relationship(
        "PreventiveMaterial",
        back_populates="preventive_execution",
        cascade="all, delete-orphan",
        order_by="PreventiveMaterial.id",
        lazy="selectin",
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('PLANEJADA', 'PROGRAMADA', 'EM_EXECUCAO', 'CONCLUIDA', 'CANCELADA', 'NAO_EXECUTADA')",
            name="ck_preventive_execution_status",
        ),
        db.CheckConstraint("cycle_hourmeter IS NULL OR cycle_hourmeter >= 0", name="ck_preventive_execution_cycle"),
        db.CheckConstraint("hourmeter_start IS NULL OR hourmeter_start >= 0", name="ck_preventive_execution_start"),
        db.CheckConstraint("hourmeter_execution IS NULL OR hourmeter_execution >= 0", name="ck_preventive_execution_reading"),
    )

    def to_dict(self, include_steps: bool = True) -> dict:
        data = {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "preventive_plan_id": self.preventive_plan_id,
            "cycle_hourmeter": _number(self.cycle_hourmeter),
            "preventive_label": _preventive_label(self.cycle_hourmeter),
            "hourmeter_start": _number(self.hourmeter_start),
            "hourmeter_execution": _number(self.hourmeter_execution),
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "responsible_user_id": self.responsible_user_id,
            "work_order_id": self.work_order_id,
            "observation": self.observation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "vehicle": self.vehicle.to_dict() if self.vehicle else None,
            "preventive_plan": {
                "id": self.preventive_plan.id,
                "code": self.preventive_plan.code,
                "title": self.preventive_plan.title,
                "priority": self.preventive_plan.priority,
            } if self.preventive_plan else None,
            "responsible_user": self.responsible_user.to_dict() if self.responsible_user else None,
        }
        if include_steps:
            data["etapas"] = [stage.to_dict() for stage in self.stages]
            data["materiais"] = [material.to_dict() for material in self.materials]
        return data


class PreventiveStage(db.Model):
    """Etapa técnica executada dentro de uma preventiva."""

    __tablename__ = "preventive_stages"

    id = db.Column(db.Integer, primary_key=True)
    preventive_execution_id = db.Column(db.Integer, db.ForeignKey("preventive_executions.id"), nullable=False, index=True)
    stage_type = db.Column(db.String(30), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="PENDENTE", index=True)
    percent_complete = db.Column(db.Integer, nullable=False, default=0)
    responsible_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    observation = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    preventive_execution = db.relationship("PreventiveExecution", back_populates="stages", lazy="joined")
    responsible_user = db.relationship("User", foreign_keys=[responsible_user_id], lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "stage_type IN ('MOTOR', 'ELETRICA', 'LUBRIFICACAO', 'ESTRUTURAL', 'INSPECAO', 'CHECKLIST', 'TESTE_OPERACIONAL')",
            name="ck_preventive_stage_type",
        ),
        db.CheckConstraint(
            "status IN ('PENDENTE', 'EM_EXECUCAO', 'CONCLUIDA', 'BLOQUEADA', 'NAO_EXECUTADA')",
            name="ck_preventive_stage_status",
        ),
        db.CheckConstraint("percent_complete >= 0 AND percent_complete <= 100", name="ck_preventive_stage_percent"),
        db.UniqueConstraint("preventive_execution_id", "stage_type", name="uq_preventive_stage_type"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "preventive_execution_id": self.preventive_execution_id,
            "stage_type": self.stage_type,
            "status": self.status,
            "percent_complete": self.percent_complete,
            "responsible_user_id": self.responsible_user_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "observation": self.observation,
        }


class PreventiveMaterial(db.Model):
    """Material planejado e consumido em uma execução preventiva."""

    __tablename__ = "preventive_materials"

    id = db.Column(db.Integer, primary_key=True)
    preventive_execution_id = db.Column(db.Integer, db.ForeignKey("preventive_executions.id"), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True)
    quantity_planned = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    quantity_separated = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    quantity_used = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="SOLICITADO", index=True)
    requested_at = db.Column(db.DateTime, nullable=True)
    separated_at = db.Column(db.DateTime, nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    observation = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    preventive_execution = db.relationship("PreventiveExecution", back_populates="materials", lazy="joined")
    material = db.relationship("Material", lazy="joined")

    __table_args__ = (
        db.CheckConstraint("quantity_planned >= 0", name="ck_preventive_material_planned"),
        db.CheckConstraint("quantity_separated >= 0 AND quantity_separated <= quantity_planned", name="ck_preventive_material_separated"),
        db.CheckConstraint("quantity_used >= 0 AND quantity_used <= quantity_separated", name="ck_preventive_material_used"),
        db.CheckConstraint("status IN ('SOLICITADO', 'SEPARADO', 'UTILIZADO', 'CANCELADO')", name="ck_preventive_material_status"),
        db.UniqueConstraint("preventive_execution_id", "material_id", name="uq_preventive_material"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "preventive_execution_id": self.preventive_execution_id,
            "material_id": self.material_id,
            "quantity_planned": _number(self.quantity_planned),
            "quantity_separated": _number(self.quantity_separated),
            "quantity_used": _number(self.quantity_used),
            "status": self.status,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "separated_at": self.separated_at.isoformat() if self.separated_at else None,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "observation": self.observation,
            "material": self.material.to_dict() if self.material else None,
        }

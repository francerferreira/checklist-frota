from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class PreventivePlan(db.Model):
    __tablename__ = "preventive_plans"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    trigger_type = db.Column(db.String(20), nullable=False, index=True)
    interval_days = db.Column(db.Integer, nullable=True)
    interval_hourmeter = db.Column(db.Numeric(12, 2), nullable=True)
    tolerance_days = db.Column(db.Integer, nullable=False, default=0)
    tolerance_hourmeter = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    next_due_date = db.Column(db.Date, nullable=True, index=True)
    next_due_hourmeter = db.Column(db.Numeric(12, 2), nullable=True, index=True)
    priority = db.Column(db.String(20), nullable=False, default="MEDIA", index=True)
    assigned_mechanic_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    estimated_duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    status = db.Column(db.String(20), nullable=False, default="ATIVO", index=True)
    generation_sequence = db.Column(db.Integer, nullable=False, default=0)
    last_generated_at = db.Column(db.DateTime, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    vehicle = db.relationship("Vehicle", lazy="joined")
    assigned_mechanic = db.relationship("User", foreign_keys=[assigned_mechanic_user_id], lazy="joined")
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")

    __table_args__ = (
        db.CheckConstraint("trigger_type IN ('CALENDARIO', 'HORIMETRO', 'AMBOS')", name="ck_preventive_plan_trigger"),
        db.CheckConstraint("priority IN ('BAIXA', 'MEDIA', 'ALTA', 'CRITICA')", name="ck_preventive_plan_priority"),
        db.CheckConstraint("status IN ('ATIVO', 'PAUSADO', 'ENCERRADO')", name="ck_preventive_plan_status"),
        db.CheckConstraint("interval_days IS NULL OR interval_days > 0", name="ck_preventive_plan_interval_days"),
        db.CheckConstraint("interval_hourmeter IS NULL OR interval_hourmeter > 0", name="ck_preventive_plan_interval_hourmeter"),
        db.CheckConstraint("tolerance_days >= 0", name="ck_preventive_plan_tolerance_days"),
        db.CheckConstraint("tolerance_hourmeter >= 0", name="ck_preventive_plan_tolerance_hourmeter"),
        db.CheckConstraint("estimated_duration_minutes > 0", name="ck_preventive_plan_duration"),
    )

    def to_dict(self, due_state: dict | None = None) -> dict:
        value = lambda item: float(item) if isinstance(item, Decimal) else (float(item) if item is not None else None)
        return {
            "id": self.id,
            "code": self.code,
            "vehicle_id": self.vehicle_id,
            "title": self.title,
            "description": self.description,
            "trigger_type": self.trigger_type,
            "interval_days": self.interval_days,
            "interval_hourmeter": value(self.interval_hourmeter),
            "tolerance_days": self.tolerance_days,
            "tolerance_hourmeter": value(self.tolerance_hourmeter),
            "next_due_date": self.next_due_date.isoformat() if self.next_due_date else None,
            "next_due_hourmeter": value(self.next_due_hourmeter),
            "priority": self.priority,
            "assigned_mechanic_user_id": self.assigned_mechanic_user_id,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "status": self.status,
            "generation_sequence": self.generation_sequence,
            "last_generated_at": self.last_generated_at.isoformat() if self.last_generated_at else None,
            "vehicle": self.vehicle.to_dict() if self.vehicle else None,
            "assigned_mechanic": self.assigned_mechanic.to_dict() if self.assigned_mechanic else None,
            "due": due_state,
        }

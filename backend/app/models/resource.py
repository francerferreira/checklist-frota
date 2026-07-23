from __future__ import annotations

from datetime import date

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class MaintenanceResource(db.Model):
    __tablename__ = "maintenance_resources"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    resource_type = db.Column(db.String(20), nullable=False, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    calibration_required = db.Column(db.Boolean, nullable=False, default=False)
    calibration_due_date = db.Column(db.Date, nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    reservations = db.relationship(
        "MaintenanceResourceReservation",
        back_populates="resource",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        db.CheckConstraint(
            "resource_type IN ('FERRAMENTA', 'INSTRUMENTO', 'EQUIPAMENTO')",
            name="ck_maintenance_resource_type",
        ),
        db.CheckConstraint(
            "NOT calibration_required OR calibration_due_date IS NOT NULL",
            name="ck_maintenance_resource_calibration_due",
        ),
    )

    def calibration_status(self, reference_date: date | None = None) -> str:
        if not self.calibration_required:
            return "NAO_APLICAVEL"
        reference_date = reference_date or date.today()
        if not self.calibration_due_date or self.calibration_due_date < reference_date:
            return "VENCIDA"
        return "EM_DIA"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "resource_type": self.resource_type,
            "active": self.active,
            "calibration_required": self.calibration_required,
            "calibration_due_date": self.calibration_due_date.isoformat() if self.calibration_due_date else None,
            "calibration_status": self.calibration_status(),
            "notes": self.notes,
        }


class MaintenanceResourceReservation(db.Model):
    __tablename__ = "maintenance_resource_reservations"

    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("maintenance_resources.id"), nullable=False, index=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("maintenance_work_orders.id"), nullable=True, index=True)
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    ends_at = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="RESERVADA", index=True)
    notes = db.Column(db.Text, nullable=True)
    cancellation_reason = db.Column(db.String(255), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    resource = db.relationship("MaintenanceResource", back_populates="reservations", lazy="joined")
    work_order = db.relationship("MaintenanceWorkOrder", lazy="joined")
    created_by = db.relationship("User", lazy="joined")

    __table_args__ = (
        db.CheckConstraint("ends_at > starts_at", name="ck_maintenance_resource_reservation_period"),
        db.CheckConstraint(
            "status IN ('RESERVADA', 'CANCELADA')",
            name="ck_maintenance_resource_reservation_status",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "work_order_id": self.work_order_id,
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat(),
            "status": self.status,
            "notes": self.notes,
            "cancellation_reason": self.cancellation_reason,
            "resource": self.resource.to_dict() if self.resource else None,
            "work_order": self.work_order.to_dict() if self.work_order else None,
        }

from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.utils.timezone import now_manaus_naive


OPERATIONAL_STATUSES = (
    "SEM_APONTAMENTO",
    "DISPONIVEL",
    "INDISPONIVEL",
    "RESTRICAO",
    "MANUTENCAO",
)


class EquipmentOperationalState(db.Model):
    __tablename__ = "equipment_operational_states"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicles.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    operational_status = db.Column(
        db.String(30),
        nullable=False,
        default="SEM_APONTAMENTO",
        index=True,
    )
    status_updated_at = db.Column(db.DateTime, nullable=True, index=True)
    status_reason = db.Column(db.String(255), nullable=True)
    status_evidence_path = db.Column(db.String(255), nullable=True)
    latest_hourmeter = db.Column(db.Numeric(12, 2), nullable=True)
    latest_hourmeter_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=now_manaus_naive,
        onupdate=now_manaus_naive,
    )

    vehicle = db.relationship("Vehicle", back_populates="operational_state")

    __table_args__ = (
        db.CheckConstraint(
            "operational_status IN ('SEM_APONTAMENTO', 'DISPONIVEL', 'INDISPONIVEL', 'RESTRICAO', 'MANUTENCAO')",
            name="ck_equipment_operational_state_status",
        ),
        db.CheckConstraint(
            "latest_hourmeter IS NULL OR latest_hourmeter >= 0",
            name="ck_equipment_operational_state_hourmeter_non_negative",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "operational_status": self.operational_status,
            "status_updated_at": self.status_updated_at.isoformat() if self.status_updated_at else None,
            "status_reason": self.status_reason,
            "status_evidence_path": self.status_evidence_path,
            "latest_hourmeter": float(self.latest_hourmeter) if self.latest_hourmeter is not None else None,
            "latest_hourmeter_at": (
                self.latest_hourmeter_at.isoformat() if self.latest_hourmeter_at else None
            ),
        }


class EquipmentStatusEvent(db.Model):
    __tablename__ = "equipment_status_events"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False, index=True)
    reason = db.Column(db.String(255), nullable=True)
    observation = db.Column(db.Text, nullable=True)
    evidence_path = db.Column(db.String(255), nullable=True)
    source = db.Column(db.String(30), nullable=False, default="MANUAL", index=True)
    started_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    ended_at = db.Column(db.DateTime, nullable=True, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    vehicle = db.relationship("Vehicle", back_populates="status_events", lazy="joined")
    created_by = db.relationship("User", lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('DISPONIVEL', 'INDISPONIVEL', 'RESTRICAO', 'MANUTENCAO')",
            name="ck_equipment_status_event_status",
        ),
        db.CheckConstraint(
            "source IN ('MANUAL', 'IMPORTADO', 'AUTOMACAO', 'TELEMETRIA')",
            name="ck_equipment_status_event_source",
        ),
        db.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_equipment_status_event_period",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "status": self.status,
            "reason": self.reason,
            "observation": self.observation,
            "evidence_path": self.evidence_path,
            "source": self.source,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "created_by_user_id": self.created_by_user_id,
            "created_by": self.created_by.to_dict() if self.created_by else None,
        }


class HourmeterReading(db.Model):
    __tablename__ = "hourmeter_readings"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    reading = db.Column(db.Numeric(12, 2), nullable=False, index=True)
    recorded_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    source = db.Column(db.String(30), nullable=False, default="MANUAL", index=True)
    evidence_path = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.String(255), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    vehicle = db.relationship("Vehicle", back_populates="hourmeter_readings", lazy="joined")
    created_by = db.relationship("User", lazy="joined")

    __table_args__ = (
        db.CheckConstraint("reading >= 0", name="ck_hourmeter_reading_non_negative"),
        db.CheckConstraint(
            "source IN ('MANUAL', 'IMPORTADO', 'TELEMETRIA')",
            name="ck_hourmeter_reading_source",
        ),
        db.UniqueConstraint("vehicle_id", "recorded_at", name="uq_hourmeter_vehicle_recorded_at"),
    )

    def to_dict(self) -> dict:
        value = self.reading
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "reading": float(value) if isinstance(value, Decimal) else float(value or 0),
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "source": self.source,
            "evidence_path": self.evidence_path,
            "notes": self.notes,
            "created_by_user_id": self.created_by_user_id,
            "created_by": self.created_by.to_dict() if self.created_by else None,
        }

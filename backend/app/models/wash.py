from __future__ import annotations

from datetime import datetime

from app.extensions import db


class WashQueueItem(db.Model):
    __tablename__ = "wash_queue_items"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, unique=True, index=True)
    referencia = db.Column(db.String(30), nullable=False, unique=True, index=True)
    categoria = db.Column(db.String(20), nullable=False, default="auxiliar", index=True)
    queue_position = db.Column(db.Integer, nullable=False, default=1, index=True)
    indisponivel = db.Column(db.Boolean, nullable=False, default=False, index=True)
    motivo_indisponivel = db.Column(db.String(255), nullable=True)
    indisponivel_desde = db.Column(db.DateTime, nullable=True)
    last_wash_at = db.Column(db.DateTime, nullable=True, index=True)
    last_location = db.Column(db.String(120), nullable=True)
    last_value = db.Column(db.Numeric(10, 2), nullable=True)
    preventive_enabled = db.Column(db.Boolean, nullable=False, default=False, index=True)
    preventive_week_of_month = db.Column(db.Integer, nullable=True)
    preventive_weekday = db.Column(db.Integer, nullable=True)
    preventive_notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    vehicle = db.relationship("Vehicle", lazy="joined")
    records = db.relationship(
        "WashRecord",
        back_populates="queue_item",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.CheckConstraint(
            "categoria IN ('cavalo', 'auxiliar')",
            name="ck_wash_queue_categoria",
        ),
        db.CheckConstraint(
            "queue_position > 0",
            name="ck_wash_queue_position_positive",
        ),
        db.CheckConstraint(
            "preventive_week_of_month IS NULL OR preventive_week_of_month BETWEEN 1 AND 5",
            name="ck_wash_preventive_week_of_month",
        ),
        db.CheckConstraint(
            "preventive_weekday IS NULL OR preventive_weekday BETWEEN 0 AND 6",
            name="ck_wash_preventive_weekday",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "referencia": self.referencia,
            "categoria": self.categoria,
            "queue_position": self.queue_position,
            "indisponivel": self.indisponivel,
            "motivo_indisponivel": self.motivo_indisponivel,
            "indisponivel_desde": self.indisponivel_desde.isoformat() if self.indisponivel_desde else None,
            "last_wash_at": self.last_wash_at.isoformat() if self.last_wash_at else None,
            "last_location": self.last_location,
            "last_value": float(self.last_value) if self.last_value is not None else None,
            "preventive_enabled": self.preventive_enabled,
            "preventive_week_of_month": self.preventive_week_of_month,
            "preventive_weekday": self.preventive_weekday,
            "preventive_notes": self.preventive_notes,
            "vehicle": self.vehicle.to_dict() if self.vehicle else None,
        }


class WashRecord(db.Model):
    __tablename__ = "wash_records"

    id = db.Column(db.Integer, primary_key=True)
    queue_item_id = db.Column(db.Integer, db.ForeignKey("wash_queue_items.id"), nullable=True, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    referencia = db.Column(db.String(30), nullable=False, index=True)
    carreta = db.Column(db.String(30), nullable=True)
    tipo_equipamento = db.Column(db.String(30), nullable=False, default="CAVALO")
    turno = db.Column(db.String(20), nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="LAVADO", index=True)
    wash_date = db.Column(db.DateTime, nullable=False, index=True)
    local = db.Column(db.String(120), nullable=True)
    valor = db.Column(db.Numeric(10, 2), nullable=True)
    observacao = db.Column(db.Text, nullable=True)
    foto_path = db.Column(db.String(255), nullable=True)
    queue_before = db.Column(db.Integer, nullable=True)
    queue_after = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    queue_item = db.relationship("WashQueueItem", back_populates="records", lazy="joined")
    vehicle = db.relationship("Vehicle", lazy="joined")
    created_by = db.relationship("User", lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('LAVADO', 'INDISPONIVEL')",
            name="ck_wash_record_status",
        ),
        db.CheckConstraint(
            "turno IS NULL OR turno IN ('MANHA', 'TARDE')",
            name="ck_wash_record_turno",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "queue_item_id": self.queue_item_id,
            "vehicle_id": self.vehicle_id,
            "created_by_user_id": self.created_by_user_id,
            "referencia": self.referencia,
            "carreta": self.carreta,
            "tipo_equipamento": self.tipo_equipamento,
            "turno": self.turno,
            "status": self.status,
            "wash_date": self.wash_date.isoformat() if self.wash_date else None,
            "local": self.local,
            "valor": float(self.valor) if self.valor is not None else None,
            "observacao": self.observacao,
            "foto_path": self.foto_path,
            "queue_before": self.queue_before,
            "queue_after": self.queue_after,
            "created_at": self.created_at.isoformat(),
            "vehicle": self.vehicle.to_dict() if self.vehicle else None,
            "created_by": self.created_by.to_dict() if self.created_by else None,
        }


class WashPlanConfig(db.Model):
    __tablename__ = "wash_plan_configs"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)
    morning_capacity = db.Column(db.Integer, nullable=False, default=2)
    afternoon_capacity = db.Column(db.Integer, nullable=False, default=2)
    auxiliary_interval_days = db.Column(db.Integer, nullable=False, default=15)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    blocked_days = db.relationship(
        "WashBlockedDay",
        back_populates="config",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    __table_args__ = (
        db.UniqueConstraint("year", "month", name="uq_wash_plan_year_month"),
        db.CheckConstraint("month BETWEEN 1 AND 12", name="ck_wash_plan_month"),
        db.CheckConstraint("morning_capacity >= 0", name="ck_wash_plan_morning_capacity"),
        db.CheckConstraint("afternoon_capacity >= 0", name="ck_wash_plan_afternoon_capacity"),
        db.CheckConstraint("auxiliary_interval_days > 0", name="ck_wash_plan_aux_interval"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "year": self.year,
            "month": self.month,
            "morning_capacity": self.morning_capacity,
            "afternoon_capacity": self.afternoon_capacity,
            "auxiliary_interval_days": self.auxiliary_interval_days,
            "notes": self.notes,
            "blocked_days": [item.to_dict() for item in self.blocked_days],
        }


class WashBlockedDay(db.Model):
    __tablename__ = "wash_blocked_days"

    id = db.Column(db.Integer, primary_key=True)
    config_id = db.Column(db.Integer, db.ForeignKey("wash_plan_configs.id"), nullable=False, index=True)
    day_date = db.Column(db.Date, nullable=False, index=True)
    shift = db.Column(db.String(20), nullable=False, default="ALL", index=True)
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    config = db.relationship("WashPlanConfig", back_populates="blocked_days")

    __table_args__ = (
        db.UniqueConstraint("config_id", "day_date", "shift", name="uq_wash_blocked_day_shift"),
        db.CheckConstraint("shift IN ('ALL', 'MANHA', 'TARDE')", name="ck_wash_blocked_shift"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "day_date": self.day_date.isoformat(),
            "shift": self.shift,
            "reason": self.reason,
        }


class WashScheduleDecision(db.Model):
    __tablename__ = "wash_schedule_decisions"

    id = db.Column(db.Integer, primary_key=True)
    queue_item_id = db.Column(db.Integer, db.ForeignKey("wash_queue_items.id"), nullable=False, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    decided_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    shift = db.Column(db.String(20), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="NAO_CUMPRIDO", index=True)
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    queue_item = db.relationship("WashQueueItem", lazy="joined")
    vehicle = db.relationship("Vehicle", lazy="joined")
    decided_by = db.relationship("User", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("queue_item_id", "scheduled_date", "shift", name="uq_wash_schedule_decision"),
        db.CheckConstraint("shift IN ('MANHA', 'TARDE')", name="ck_wash_schedule_decision_shift"),
        db.CheckConstraint("status IN ('NAO_CUMPRIDO')", name="ck_wash_schedule_decision_status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "queue_item_id": self.queue_item_id,
            "vehicle_id": self.vehicle_id,
            "decided_by_user_id": self.decided_by_user_id,
            "scheduled_date": self.scheduled_date.isoformat(),
            "shift": self.shift,
            "status": self.status,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

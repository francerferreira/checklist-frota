from __future__ import annotations

from datetime import date

from app.extensions import db
from app.utils.timezone import now_manaus_naive


EMPLOYEE_STATUSES = {
    "PRE_CADASTRO",
    "AGUARDANDO_FOTO",
    "AGUARDANDO_DOCUMENTOS",
    "EM_VALIDACAO",
    "ATIVO",
    "INATIVO",
}

ATTENDANCE_TYPES = {
    "PRESENTE",
    "FALTA",
    "ATRASO",
    "ATESTADO",
    "FERIAS",
    "DSR",
    "FOLGA",
    "CURSO",
    "AFASTADO",
    "SERVICO_EXTERNO",
}


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, unique=True, index=True)
    registration = db.Column(db.String(40), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(160), nullable=False, index=True)
    function_name = db.Column(db.String(100), nullable=False, index=True)
    team_name = db.Column(db.String(100), nullable=False, index=True)
    shift_name = db.Column(db.String(60), nullable=False, index=True)
    photo_path = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="PRE_CADASTRO", index=True)
    hired_on = db.Column(db.Date, nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    user = db.relationship("User", lazy="joined")
    attendance_records = db.relationship("EmployeeAttendanceRecord", back_populates="employee", lazy="select")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('PRE_CADASTRO', 'AGUARDANDO_FOTO', 'AGUARDANDO_DOCUMENTOS', 'EM_VALIDACAO', 'ATIVO', 'INATIVO')",
            name="ck_employee_status",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "registration": self.registration,
            "full_name": self.full_name,
            "function_name": self.function_name,
            "team_name": self.team_name,
            "shift_name": self.shift_name,
            "photo_path": self.photo_path,
            "status": self.status,
            "hired_on": self.hired_on.isoformat() if isinstance(self.hired_on, date) else None,
            "notes": self.notes,
            "linked_user": self.user.to_dict() if self.user else None,
        }


class EmployeeAttendanceRecord(db.Model):
    __tablename__ = "employee_attendance_records"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    occurrence_date = db.Column(db.Date, nullable=False, index=True)
    occurrence_type = db.Column(db.String(30), nullable=False, index=True)
    record_status = db.Column(db.String(20), nullable=False, default="ATIVO", index=True)
    scheduled_time = db.Column(db.Time, nullable=True)
    arrival_time = db.Column(db.Time, nullable=True)
    delay_minutes = db.Column(db.Integer, nullable=False, default=0)
    is_justified = db.Column(db.Boolean, nullable=False, default=False)
    reason = db.Column(db.String(500), nullable=True)
    document_path = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    change_reason = db.Column(db.String(500), nullable=True)
    cancellation_reason = db.Column(db.String(500), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    cancelled_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    employee = db.relationship("Employee", back_populates="attendance_records", lazy="joined")
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    updated_by = db.relationship("User", foreign_keys=[updated_by_user_id], lazy="joined")
    cancelled_by = db.relationship("User", foreign_keys=[cancelled_by_user_id], lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("employee_id", "occurrence_date", name="uq_employee_attendance_day"),
        db.CheckConstraint("delay_minutes >= 0", name="ck_employee_attendance_delay_minutes"),
        db.CheckConstraint(
            "occurrence_type IN ('PRESENTE', 'FALTA', 'ATRASO', 'ATESTADO', 'FERIAS', 'DSR', 'FOLGA', 'CURSO', 'AFASTADO', 'SERVICO_EXTERNO')",
            name="ck_employee_attendance_type",
        ),
        db.CheckConstraint("record_status IN ('ATIVO', 'CANCELADO')", name="ck_employee_attendance_status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "occurrence_date": self.occurrence_date.isoformat(),
            "occurrence_type": self.occurrence_type,
            "record_status": self.record_status,
            "scheduled_time": self.scheduled_time.isoformat(timespec="minutes") if self.scheduled_time else None,
            "arrival_time": self.arrival_time.isoformat(timespec="minutes") if self.arrival_time else None,
            "delay_minutes": self.delay_minutes,
            "is_justified": self.is_justified,
            "reason": self.reason,
            "document_path": self.document_path,
            "notes": self.notes,
            "change_reason": self.change_reason,
            "cancellation_reason": self.cancellation_reason,
            "employee": self.employee.to_dict() if self.employee else None,
        }

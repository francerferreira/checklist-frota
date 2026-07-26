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

VACATION_STATUSES = {"PROGRAMADA", "APROVADA", "CANCELADA"}
SPECIAL_SCHEDULE_TYPES = {"DOMINGO", "FERIADO"}

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
    documents = db.relationship("EmployeeDocument", back_populates="employee", lazy="select")
    trainings = db.relationship("EmployeeTraining", back_populates="employee", lazy="select")
    history_events = db.relationship("EmployeeHistoryEvent", back_populates="employee", lazy="select")
    vacations = db.relationship(
        "EmployeeVacation",
        back_populates="employee",
        cascade="all, delete-orphan",
        lazy="select",
    )
    special_schedules = db.relationship("EmployeeSpecialSchedule", back_populates="employee", lazy="select")

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


class EmployeeVacation(db.Model):
    __tablename__ = "employee_vacations"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    starts_on = db.Column(db.Date, nullable=False, index=True)
    ends_on = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="PROGRAMADA", index=True)
    notes = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    cancelled_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    employee = db.relationship("Employee", back_populates="vacations", lazy="joined")
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    cancelled_by = db.relationship("User", foreign_keys=[cancelled_by_user_id], lazy="joined")

    __table_args__ = (
        db.CheckConstraint("starts_on <= ends_on", name="ck_employee_vacation_period"),
        db.CheckConstraint(
            "status IN ('PROGRAMADA', 'APROVADA', 'CANCELADA')",
            name="ck_employee_vacation_status",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "starts_on": self.starts_on.isoformat(),
            "ends_on": self.ends_on.isoformat(),
            "status": self.status,
            "notes": self.notes,
            "created_by_user_id": self.created_by_user_id,
            "cancelled_by_user_id": self.cancelled_by_user_id,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "employee": self.employee.to_dict() if self.employee else None,
        }


class EmployeeSpecialSchedule(db.Model):
    __tablename__ = "employee_work_schedules"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    schedule_date = db.Column(db.Date, nullable=False, index=True)
    schedule_type = db.Column(db.String(20), nullable=False, index=True)
    holiday_name = db.Column(db.String(160), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="ESCALADO", index=True)
    dsr_date = db.Column(db.Date, nullable=True, index=True)
    dsr_week_start = db.Column(db.Date, nullable=True, index=True)
    dsr_attendance_record_id = db.Column(db.Integer, db.ForeignKey("employee_attendance_records.id"), nullable=True, unique=True)
    attendance_confirmed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    attendance_confirmed_at = db.Column(db.DateTime(), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    employee = db.relationship("Employee", back_populates="special_schedules", lazy="joined")
    dsr_attendance_record = db.relationship("EmployeeAttendanceRecord", foreign_keys=[dsr_attendance_record_id], lazy="joined")
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    attendance_confirmed_by = db.relationship("User", foreign_keys=[attendance_confirmed_by_user_id], lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("employee_id", "schedule_date", name="uq_employee_work_schedule_day"),
        db.CheckConstraint("schedule_type IN ('DOMINGO', 'FERIADO')", name="ck_employee_work_schedule_type"),
        db.CheckConstraint("status IN ('ESCALADO', 'COMPARECEU', 'NAO_COMPARECEU')", name="ck_employee_work_schedule_status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "schedule_date": self.schedule_date.isoformat(),
            "schedule_type": self.schedule_type,
            "holiday_name": self.holiday_name,
            "status": self.status,
            "dsr_date": self.dsr_date.isoformat() if self.dsr_date else None,
            "dsr_week_start": self.dsr_week_start.isoformat() if self.dsr_week_start else None,
            "dsr_attendance_record_id": self.dsr_attendance_record_id,
            "attendance_confirmed_at": self.attendance_confirmed_at.isoformat() if self.attendance_confirmed_at else None,
            "notes": self.notes,
            "employee": self.employee.to_dict() if self.employee else None,
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


class EmployeeDocument(db.Model):
    __tablename__ = "employee_documents"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    document_type = db.Column(db.String(80), nullable=False, index=True)
    issued_on = db.Column(db.Date, nullable=True)
    expires_on = db.Column(db.Date, nullable=True, index=True)
    file_path = db.Column(db.String(500), nullable=False)
    is_sensitive = db.Column(db.Boolean, nullable=False, default=False, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    employee = db.relationship("Employee", back_populates="documents", lazy="joined")
    created_by = db.relationship("User", lazy="joined")

    def status(self, reference_date: date | None = None) -> str:
        reference_date = reference_date or date.today()
        if not self.expires_on:
            return "SEM_VALIDADE"
        if self.expires_on < reference_date:
            return "VENCIDO"
        if (self.expires_on - reference_date).days <= 30:
            return "VENCENDO"
        return "VALIDO"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "document_type": self.document_type,
            "issued_on": self.issued_on.isoformat() if self.issued_on else None,
            "expires_on": self.expires_on.isoformat() if self.expires_on else None,
            "file_path": self.file_path,
            "is_sensitive": self.is_sensitive,
            "status": self.status(),
            "notes": self.notes,
            "employee": self.employee.to_dict() if self.employee else None,
        }


class EmployeeTraining(db.Model):
    __tablename__ = "employee_trainings"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    course_name = db.Column(db.String(160), nullable=False, index=True)
    training_type = db.Column(db.String(80), nullable=False, index=True)
    provider_name = db.Column(db.String(160), nullable=True)
    starts_on = db.Column(db.Date, nullable=True)
    ends_on = db.Column(db.Date, nullable=True)
    workload_hours = db.Column(db.Integer, nullable=True)
    expires_on = db.Column(db.Date, nullable=True, index=True)
    certificate_path = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    employee = db.relationship("Employee", back_populates="trainings", lazy="joined")
    created_by = db.relationship("User", lazy="joined")

    def status(self, reference_date: date | None = None) -> str:
        reference_date = reference_date or date.today()
        if not self.ends_on:
            return "PENDENTE"
        if self.expires_on and self.expires_on < reference_date:
            return "VENCIDO"
        if self.expires_on and (self.expires_on - reference_date).days <= 30:
            return "VENCENDO"
        return "VALIDO"

    def to_dict(self) -> dict:
        return {"id": self.id, "employee_id": self.employee_id, "course_name": self.course_name, "training_type": self.training_type, "provider_name": self.provider_name, "starts_on": self.starts_on.isoformat() if self.starts_on else None, "ends_on": self.ends_on.isoformat() if self.ends_on else None, "workload_hours": self.workload_hours, "expires_on": self.expires_on.isoformat() if self.expires_on else None, "certificate_path": self.certificate_path, "status": self.status(), "notes": self.notes, "employee": self.employee.to_dict() if self.employee else None}


class EmployeeHistoryEvent(db.Model):
    __tablename__ = "employee_history_events"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    event_type = db.Column(db.String(80), nullable=False, index=True)
    occurred_on = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    employee = db.relationship("Employee", back_populates="history_events", lazy="joined")
    created_by = db.relationship("User", lazy="joined")

    def to_dict(self) -> dict:
        return {"id": self.id, "employee_id": self.employee_id, "event_type": self.event_type, "occurred_on": self.occurred_on.isoformat(), "description": self.description, "employee": self.employee.to_dict() if self.employee else None}

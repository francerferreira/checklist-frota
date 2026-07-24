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

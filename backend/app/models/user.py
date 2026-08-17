from __future__ import annotations

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    login = db.Column(db.String(80), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, index=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    checklists = db.relationship("Checklist", back_populates="user", lazy="dynamic")
    employee = db.relationship("Employee", back_populates="user", uselist=False, foreign_keys="Employee.user_id", lazy="joined")
    page_permissions = db.relationship(
        "UserPagePermission",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def set_password(self, password: str) -> None:
        self.senha_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.senha_hash, password)

    def to_dict(self) -> dict:
        employee = self.employee
        identity = None
        first_access_required = False
        if employee:
            first_access_required = not employee.photo_path or not employee.signature_path
            identity = {
                "employee_id": employee.id,
                "registration": employee.registration,
                "full_name": employee.full_name,
                "function_name": employee.function_name,
                "team_name": employee.team_name,
                "shift_name": employee.shift_name,
                "photo_path": employee.photo_path,
                "signature_path": employee.signature_path,
                "first_access_completed_at": employee.first_access_completed_at.isoformat() if employee.first_access_completed_at else None,
                "first_access_required": first_access_required,
            }
        return {
            "id": self.id,
            "nome": self.nome,
            "login": self.login,
            "tipo": self.tipo,
            "ativo": self.ativo,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "identity": identity,
            "first_access_required": first_access_required,
            "custom_page_keys": [row.page_key for row in self.page_permissions if row.enabled],
        }

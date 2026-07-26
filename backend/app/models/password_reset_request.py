from __future__ import annotations

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class PasswordResetRequest(db.Model):
    __tablename__ = "password_reset_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    requested_login = db.Column(db.String(80), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="PENDENTE", index=True)
    requested_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    resolved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.String(500), nullable=True)

    user = db.relationship("User", foreign_keys=[user_id], lazy="joined")
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_user_id], lazy="joined")

    __table_args__ = (db.CheckConstraint("status IN ('PENDENTE', 'ATENDIDO', 'CANCELADO')", name="ck_password_reset_status"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "requested_login": self.requested_login,
            "status": self.status,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "resolved_by_user_id": self.resolved_by_user_id,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "notes": self.notes,
            "user": self.user.to_dict() if self.user else None,
        }

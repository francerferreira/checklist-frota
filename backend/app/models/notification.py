from __future__ import annotations

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class Notification(db.Model):
    """Aviso persistente direcionado a um usuário do SIS MMP."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), nullable=False, default="INFO", index=True)
    origin = db.Column(db.String(60), nullable=False, default="SYSTEM", index=True)
    entity_type = db.Column(db.String(60), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    read_at = db.Column(db.DateTime, nullable=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "priority": self.priority,
            "origin": self.origin,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "read": self.is_read,
        }

from __future__ import annotations

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class SystemSetting(db.Model):
    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), nullable=False, unique=True, index=True)
    value_json = db.Column(db.Text, nullable=True)
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    updated_by = db.relationship("User", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "value_json": self.value_json,
            "updated_by_user_id": self.updated_by_user_id,
            "updated_by": self.updated_by.to_dict() if self.updated_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

from __future__ import annotations

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class DashboardTvAccessToken(db.Model):
    """Credencial opaca de leitura para uma tela TV, sem guardar o token bruto."""

    __tablename__ = "dashboard_tv_access_tokens"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, default="TV OPERACIONAL")
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    revoked_at = db.Column(db.DateTime, nullable=True, index=True)
    last_used_at = db.Column(db.DateTime, nullable=True, index=True)

    created_by = db.relationship("User", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_by_user_id": self.created_by_user_id,
            "created_by": self.created_by.to_dict() if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "active": self.revoked_at is None and self.expires_at > now_manaus_naive(),
        }

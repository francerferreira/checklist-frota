from __future__ import annotations

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class UserNavigationPreference(db.Model):
    __tablename__ = "user_navigation_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    page_key = db.Column(db.String(60), nullable=False, index=True)
    is_favorite = db.Column(db.Boolean, nullable=False, default=False, index=True)
    access_count = db.Column(db.Integer, nullable=False, default=0)
    last_accessed_at = db.Column(db.DateTime, nullable=True, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    user = db.relationship("User", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("user_id", "page_key", name="uq_user_navigation_preference_page"),
        db.CheckConstraint("access_count >= 0", name="ck_user_navigation_preference_access_count"),
    )

    def to_dict(self) -> dict:
        return {
            "page_key": self.page_key,
            "is_favorite": self.is_favorite,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
        }

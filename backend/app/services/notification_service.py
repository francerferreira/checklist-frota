from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_

from app.extensions import db
from app.models.notification import Notification
from app.utils.timezone import now_manaus_naive

ALLOWED_PRIORITIES = {"INFO", "SUCCESS", "WARNING", "CRITICAL"}
MAX_TITLE_LENGTH = 160
MAX_MESSAGE_LENGTH = 4000


def normalize_priority(value: str | None) -> str:
    priority = str(value or "INFO").strip().upper()
    return priority if priority in ALLOWED_PRIORITIES else "INFO"


def create_notification(
    *,
    user_id: int,
    title: str,
    message: str,
    priority: str = "INFO",
    origin: str = "SYSTEM",
    entity_type: str | None = None,
    entity_id: int | None = None,
    expires_at: datetime | None = None,
) -> Notification:
    notification = Notification(
        user_id=int(user_id),
        title=str(title or "Notificação").strip()[:MAX_TITLE_LENGTH],
        message=str(message or "").strip()[:MAX_MESSAGE_LENGTH],
        priority=normalize_priority(priority),
        origin=str(origin or "SYSTEM").strip().upper()[:60],
        entity_type=str(entity_type).strip().upper()[:60] if entity_type else None,
        entity_id=int(entity_id) if entity_id is not None else None,
        expires_at=expires_at,
    )
    db.session.add(notification)
    return notification


def list_user_notifications(user_id: int, *, limit: int = 40, unread_only: bool = False) -> list[Notification]:
    now = now_manaus_naive()
    query = Notification.query.filter(
        Notification.user_id == int(user_id),
        or_(Notification.expires_at.is_(None), Notification.expires_at >= now),
    )
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    return query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(max(1, min(limit, 100))).all()


def unread_count(user_id: int) -> int:
    now = now_manaus_naive()
    return Notification.query.filter(
        Notification.user_id == int(user_id),
        Notification.read_at.is_(None),
        or_(Notification.expires_at.is_(None), Notification.expires_at >= now),
    ).count()

from __future__ import annotations

from flask import Blueprint, g, request

from app.extensions import db
from app.models import Notification, User
from app.services.auth_service import auth_required
from app.services.notification_service import create_notification, list_user_notifications, unread_count
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive


bp = Blueprint("notifications", __name__)


@bp.get("/notifications")
@auth_required
def list_notifications():
    try:
        limit = int(request.args.get("limit", 40))
    except (TypeError, ValueError):
        limit = 40
    unread_only = str(request.args.get("unread_only", "false")).lower() in {"1", "true", "yes"}
    rows = list_user_notifications(g.current_user.id, limit=limit, unread_only=unread_only)
    return api_response(True, data={"items": [row.to_dict() for row in rows], "unread_count": unread_count(g.current_user.id)})


@bp.post("/notifications/<int:notification_id>/read")
@auth_required
def mark_notification_read(notification_id: int):
    row = Notification.query.filter_by(id=notification_id, user_id=g.current_user.id).first()
    if not row:
        return api_response(False, error="Notificação não encontrada.", status_code=404)
    if not row.read_at:
        row.read_at = now_manaus_naive()
        db.session.commit()
    return api_response(True, data=row.to_dict())


@bp.post("/notifications/read-all")
@auth_required
def mark_all_notifications_read():
    now = now_manaus_naive()
    rows = Notification.query.filter_by(user_id=g.current_user.id).filter(Notification.read_at.is_(None)).all()
    for row in rows:
        row.read_at = now
    db.session.commit()
    return api_response(True, data={"updated": len(rows), "unread_count": 0})


@bp.delete("/notifications")
@auth_required
def clear_notifications():
    rows = Notification.query.filter_by(user_id=g.current_user.id).all()
    for row in rows:
        db.session.delete(row)
    db.session.commit()
    return api_response(True, data={"deleted": len(rows)})


@bp.post("/notifications")
@auth_required
def create_notifications():
    if g.current_user.tipo != "admin":
        return api_response(False, error="Somente admin pode criar notificações.", status_code=403)
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title") or "").strip()
    message = str(payload.get("message") or "").strip()
    if not title or not message:
        return api_response(False, error="Informe título e mensagem da notificação.", status_code=400)

    raw_ids = payload.get("user_ids")
    if raw_ids is None and payload.get("user_id") is not None:
        raw_ids = [payload.get("user_id")]
    if not isinstance(raw_ids, list) or not raw_ids:
        return api_response(False, error="Informe ao menos um usuário destinatário.", status_code=400)
    try:
        user_ids = sorted({int(value) for value in raw_ids})
    except (TypeError, ValueError):
        return api_response(False, error="Lista de usuários inválida.", status_code=400)
    users = User.query.filter(User.id.in_(user_ids), User.ativo.is_(True)).all()
    if len(users) != len(user_ids):
        return api_response(False, error="Há usuários inválidos ou inativos na lista.", status_code=400)

    rows = [
        create_notification(
            user_id=user.id,
            title=title,
            message=message,
            priority=payload.get("priority"),
            origin=payload.get("origin"),
            entity_type=payload.get("entity_type"),
            entity_id=payload.get("entity_id"),
        )
        for user in users
    ]
    db.session.commit()
    return api_response(True, data=[row.to_dict() for row in rows], status_code=201)

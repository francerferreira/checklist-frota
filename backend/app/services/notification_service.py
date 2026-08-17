from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select

from app.extensions import db
from app.models.notification import Notification
from app.models.user import User
from app.utils.timezone import now_manaus_naive

ALLOWED_PRIORITIES = {"INFO", "SUCCESS", "WARNING", "CRITICAL"}
MAX_TITLE_LENGTH = 160
MAX_MESSAGE_LENGTH = 4000

# Objetos internos não geram novos avisos. Isso evita o efeito "notificação
# notificando a própria notificação" e mantém o centro útil para a operação.
AUTOMATIC_NOTIFICATION_EXCLUDED_ENTITIES = {"NOTIFICATION", "AUDIT_LOG", "REVOKED_TOKEN", "SESSION"}


def automatic_notification_origin(entity_type: str | None) -> str:
    """Converte o nome técnico do modelo em uma área compreensível."""
    entity = str(entity_type or "").upper()
    if "EMERGENCY" in entity:
        return "EMERGÊNCIA"
    if any(token in entity for token in ("PURCHASE", "SUPPLIER", "INVOICE")):
        return "COMPRAS"
    if any(token in entity for token in ("WAREHOUSE", "MATERIAL", "SUPPLY", "MMP", "STOCK")):
        return "ESTOQUE MMP"
    if any(token in entity for token in ("MAINTENANCE", "WORK_ORDER", "PREVENTIVE", "ACTIVITY", "PCM")):
        return "MANUTENÇÃO"
    if entity.startswith("RH") or entity.startswith("HR_") or any(token in entity for token in ("EMPLOYEE", "ATTENDANCE", "TRAINING", "VACATION", "SPECIAL_SCHEDULE")):
        return "RH"
    if any(token in entity for token in ("EQUIPMENT", "VEHICLE", "CHECKLIST", "HOURMETER")):
        return "EQUIPAMENTOS"
    return "ADMINISTRAÇÃO"


def automatic_notification_priority(entity_type: str | None, action: str | None) -> str:
    if "EMERGENCY" in str(entity_type or "").upper():
        return "CRITICAL"
    if str(action or "").upper() == "DELETE":
        return "WARNING"
    return "INFO"


def automatic_notification_title(action: str | None) -> str:
    action_name = str(action or "UPDATE").upper()
    if action_name in {"TRANSFER", "TRANSFER_TO_MMP"}:
        return "Transferência registrada"
    if action_name in {"APPLICATION_OUT", "MATERIAL_OUT"}:
        return "Saída de material"
    if action_name.startswith("EXPORT") or action_name == "EXPORT":
        return "Relatório gerado"
    return {
        "CREATE": "Registro aberto",
        "UPDATE": "Registro movimentado",
        "STATUS_CHANGE": "Status atualizado",
        "DELETE": "Registro removido",
    }.get(action_name, "Atividade registrada")


def create_automatic_notifications(events: list[dict]) -> int:
    """Publica um aviso de cada alteração para os usuários ativos, exceto o autor."""
    if not events:
        return 0
    recipients = db.session.execute(select(User.id).where(User.ativo.is_(True))).scalars().all()
    if not recipients:
        return 0

    created = 0
    for event in events:
        entity_type = str(event.get("entity_type") or "SYSTEM").upper()
        if entity_type in AUTOMATIC_NOTIFICATION_EXCLUDED_ENTITIES:
            continue
        action = str(event.get("action") or "UPDATE").upper()
        origin = automatic_notification_origin(entity_type)
        title = f"{automatic_notification_title(action)} · {origin}"
        actor_name = str(event.get("actor_name") or "Sistema").strip()
        entity_id = int(event.get("entity_id") or 0)
        verb = {
            "CREATE": "abriu",
            "UPDATE": "movimentou",
            "STATUS_CHANGE": "atualizou",
            "DELETE": "removeu",
        }.get(action, "registrou uma atividade em")
        message = f"{actor_name} {verb} um registro de {origin.lower()} (ID {entity_id})."
        for recipient_id in recipients:
            if event.get("user_id") and int(recipient_id) == int(event["user_id"]):
                continue
            create_notification(
                user_id=int(recipient_id),
                title=title,
                message=message,
                priority=automatic_notification_priority(entity_type, action),
                origin=origin,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            created += 1
    return created


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

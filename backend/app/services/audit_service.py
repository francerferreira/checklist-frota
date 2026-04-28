from app.extensions import db
from app.models.audit_log import AuditLog

def record_status_change(user_id: int, entity_type: str, entity_id: int, old_status: str, new_status: str):
    """
    Garante a rastreabilidade de mudanças críticas no sistema.
    O log é adicionado à sessão atual, mas o commit deve ser feito pelo chamador.
    """
    if old_status == new_status:
        return

    log = AuditLog(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action="STATUS_CHANGE",
        old_value=str(old_status) if old_status else "N/A",
        new_value=str(new_status) if new_status else "N/A"
    )
    db.session.add(log)
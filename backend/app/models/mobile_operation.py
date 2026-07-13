from __future__ import annotations

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class MobileSyncOperation(db.Model):
    """Identifica cada envio do aparelho para evitar duplicidade na reconexao."""

    __tablename__ = "mobile_sync_operations"

    id = db.Column(db.Integer, primary_key=True)
    operation_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    operation_type = db.Column(db.String(30), nullable=False, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    payload_hash = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="PROCESSANDO", index=True)
    result_json = db.Column(db.Text, nullable=True)
    conflict_reason = db.Column(db.String(500), nullable=True)
    occurred_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    processed_at = db.Column(db.DateTime, nullable=True, index=True)

    vehicle = db.relationship("Vehicle", lazy="joined")
    user = db.relationship("User", lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "operation_type IN ('HORIMETRO', 'EMERGENCIA', 'OS_INICIAR', 'OS_CONCLUIR', 'OS_TESTAR', 'OS_LIBERAR')",
            name="ck_mobile_sync_operation_type",
        ),
        db.CheckConstraint(
            "status IN ('PROCESSANDO', 'APLICADA', 'CONFLITO')",
            name="ck_mobile_sync_operation_status",
        ),
    )

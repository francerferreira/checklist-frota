from __future__ import annotations

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class AutomationExecution(db.Model):
    """Registro auditavel dos alertas gerados pela leitura das regras operacionais."""

    __tablename__ = "automation_executions"

    id = db.Column(db.Integer, primary_key=True)
    rule_code = db.Column(db.String(60), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    dedup_key = db.Column(db.String(140), nullable=False, unique=True, index=True)
    severity = db.Column(db.String(20), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="ATIVO", index=True)
    message = db.Column(db.String(500), nullable=False)
    context_json = db.Column(db.Text, nullable=True)
    evaluated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True, index=True)
    acknowledged_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    acknowledged_by = db.relationship("User", foreign_keys=[acknowledged_by_user_id], lazy="joined")
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "severity IN ('BAIXA', 'MEDIA', 'ALTA', 'CRITICA')",
            name="ck_automation_execution_severity",
        ),
        db.CheckConstraint(
            "status IN ('ATIVO', 'RECONHECIDO', 'ENCERRADO')",
            name="ck_automation_execution_status",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_code": self.rule_code,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "severity": self.severity,
            "status": self.status,
            "message": self.message,
            "context_json": self.context_json,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by_user_id": self.acknowledged_by_user_id,
            "created_by_user_id": self.created_by_user_id,
        }

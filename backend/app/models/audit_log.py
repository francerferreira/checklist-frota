from datetime import datetime
from app.extensions import db
from app.utils.timezone import now_manaus_naive

class AuditLog(db.Model):
    """
    Modelo para rastreabilidade e auditoria (Ponto 3 do escopo).
    Registra quem alterou o quê, quando e quais eram os valores antes e depois.
    """
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=now_manaus_naive)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    entity_type = db.Column(db.String(50), nullable=False)  # 'VEHICLE', 'CHECKLIST_ITEM'
    entity_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(50), nullable=False)       # 'STATUS_CHANGE'
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    module = db.Column(db.String(80), nullable=True)
    equipment_id = db.Column(db.Integer, nullable=True)
    record_id = db.Column(db.Integer, nullable=True)
    justification = db.Column(db.Text, nullable=True)
    origin = db.Column(db.String(30), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    device = db.Column(db.String(120), nullable=True)

    user = db.relationship("User", backref="audit_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "user": self.user.nome if self.user else "Sistema",
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action": self.action,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "module": self.module,
            "equipment_id": self.equipment_id,
            "record_id": self.record_id,
            "justification": self.justification,
            "origin": self.origin,
            "ip_address": self.ip_address,
            "device": self.device,
        }

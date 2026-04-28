from datetime import datetime
from app.extensions import db

class AuditLog(db.Model):
    """
    Modelo para rastreabilidade e auditoria (Ponto 3 do escopo).
    Registra quem alterou o quê, quando e quais eram os valores antes e depois.
    """
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    entity_type = db.Column(db.String(50), nullable=False)  # 'VEHICLE', 'CHECKLIST_ITEM'
    entity_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(50), nullable=False)       # 'STATUS_CHANGE'
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)

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
        }
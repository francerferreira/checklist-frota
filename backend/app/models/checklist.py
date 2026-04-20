from __future__ import annotations

from datetime import datetime

from app.extensions import db


class Checklist(db.Model):
    __tablename__ = "checklists"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    vehicle = db.relationship("Vehicle", back_populates="checklists")
    user = db.relationship("User", back_populates="checklists")
    items = db.relationship(
        "ChecklistItem",
        back_populates="checklist",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def to_dict(self, include_items: bool = False) -> dict:
        data = {
            "id": self.id,
            "vehicle": self.vehicle.to_dict(),
            "user": self.user.to_dict(),
            "created_at": self.created_at.isoformat(),
            "total_itens": len(self.items),
            "total_nc": sum(1 for item in self.items if item.status == "NC"),
        }
        if include_items:
            data["itens"] = [item.to_dict() for item in self.items]
        return data


class ChecklistItem(db.Model):
    __tablename__ = "checklist_items"

    id = db.Column(db.Integer, primary_key=True)
    checklist_id = db.Column(db.Integer, db.ForeignKey("checklists.id"), nullable=False, index=True)
    item_nome = db.Column(db.String(160), nullable=False, index=True)
    status = db.Column(db.String(2), nullable=False, index=True)
    observacao = db.Column(db.Text, nullable=True)
    foto_antes = db.Column(db.String(255), nullable=True)
    foto_depois = db.Column(db.String(255), nullable=True)
    codigo_peca = db.Column(db.String(80), nullable=True)
    descricao_peca = db.Column(db.String(255), nullable=True)
    resolved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    resolvido = db.Column(db.Boolean, nullable=False, default=False, index=True)
    data_resolucao = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    checklist = db.relationship("Checklist", back_populates="items")
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_user_id], lazy="joined")

    __table_args__ = (
        db.CheckConstraint("status IN ('OK', 'NC')", name="ck_checklist_item_status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "checklist_id": self.checklist_id,
            "item_nome": self.item_nome,
            "status": self.status,
            "observacao": self.observacao,
            "foto_antes": self.foto_antes,
            "foto_depois": self.foto_depois,
            "codigo_peca": self.codigo_peca,
            "descricao_peca": self.descricao_peca,
            "resolved_by_user_id": self.resolved_by_user_id,
            "resolvido": self.resolvido,
            "data_resolucao": self.data_resolucao.isoformat() if self.data_resolucao else None,
            "created_at": self.created_at.isoformat(),
            "veiculo": self.checklist.vehicle.to_dict(),
            "usuario": self.checklist.user.to_dict(),
            "resolved_by": self.resolved_by.to_dict() if self.resolved_by else None,
        }

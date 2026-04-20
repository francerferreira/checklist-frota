from __future__ import annotations

from datetime import datetime

from app.extensions import db


class MechanicNonConformity(db.Model):
    __tablename__ = "mechanic_non_conformities"

    id = db.Column(db.Integer, primary_key=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    resolved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=True, index=True)

    veiculo_referencia = db.Column(db.String(80), nullable=True, index=True)
    item_nome = db.Column(db.String(160), nullable=False, index=True)
    observacao = db.Column(db.Text, nullable=True)
    observacao_resolucao = db.Column(db.Text, nullable=True)

    foto_antes = db.Column(db.String(255), nullable=True)
    foto_depois = db.Column(db.String(255), nullable=True)
    codigo_peca = db.Column(db.String(80), nullable=True)
    descricao_peca = db.Column(db.String(255), nullable=True)
    quantidade_material = db.Column(db.Integer, nullable=False, default=1)

    resolvido = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    data_resolucao = db.Column(db.DateTime, nullable=True)

    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_user_id], lazy="joined")
    material = db.relationship("Material", lazy="joined")

    __table_args__ = (
        db.CheckConstraint("quantidade_material > 0", name="ck_mechanic_nc_quantity_positive"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_by_user_id": self.created_by_user_id,
            "resolved_by_user_id": self.resolved_by_user_id,
            "material_id": self.material_id,
            "veiculo_referencia": self.veiculo_referencia,
            "item_nome": self.item_nome,
            "observacao": self.observacao,
            "observacao_resolucao": self.observacao_resolucao,
            "foto_antes": self.foto_antes,
            "foto_depois": self.foto_depois,
            "codigo_peca": self.codigo_peca,
            "descricao_peca": self.descricao_peca,
            "quantidade_material": self.quantidade_material,
            "resolvido": self.resolvido,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "data_resolucao": self.data_resolucao.isoformat() if self.data_resolucao else None,
            "created_by": self.created_by.to_dict() if self.created_by else None,
            "resolved_by": self.resolved_by.to_dict() if self.resolved_by else None,
            "material": self.material.to_dict() if self.material else None,
        }

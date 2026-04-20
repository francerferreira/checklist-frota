from __future__ import annotations

from datetime import datetime

from app.extensions import db


class Material(db.Model):
    __tablename__ = "materials"

    id = db.Column(db.Integer, primary_key=True)
    referencia = db.Column(db.String(80), nullable=False, unique=True, index=True)
    descricao = db.Column(db.String(255), nullable=False, index=True)
    aplicacao_tipo = db.Column(db.String(20), nullable=False, default="ambos", index=True)
    foto_path = db.Column(db.String(255), nullable=True)
    quantidade_estoque = db.Column(db.Integer, nullable=False, default=0)
    estoque_minimo = db.Column(db.Integer, nullable=False, default=0)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    movements = db.relationship(
        "MaterialMovement",
        back_populates="material",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        db.CheckConstraint(
            "aplicacao_tipo IN ('cavalo', 'carreta', 'ambos')",
            name="ck_material_aplicacao_tipo",
        ),
        db.CheckConstraint(
            "quantidade_estoque >= 0",
            name="ck_material_quantidade_estoque_non_negative",
        ),
        db.CheckConstraint(
            "estoque_minimo >= 0",
            name="ck_material_estoque_minimo_non_negative",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "referencia": self.referencia,
            "descricao": self.descricao,
            "aplicacao_tipo": self.aplicacao_tipo,
            "foto_path": self.foto_path,
            "quantidade_estoque": self.quantidade_estoque,
            "estoque_minimo": self.estoque_minimo,
            "ativo": self.ativo,
            "baixo_estoque": self.quantidade_estoque <= self.estoque_minimo,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MaterialMovement(db.Model):
    __tablename__ = "material_movements"

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=True, index=True)
    checklist_item_id = db.Column(db.Integer, db.ForeignKey("checklist_items.id"), nullable=True, index=True)
    tipo_movimento = db.Column(db.String(30), nullable=False, index=True)
    quantidade = db.Column(db.Integer, nullable=False)
    saldo_anterior = db.Column(db.Integer, nullable=False)
    saldo_posterior = db.Column(db.Integer, nullable=False)
    observacao = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    material = db.relationship("Material", back_populates="movements")
    user = db.relationship("User", lazy="joined")
    activity = db.relationship("Activity", lazy="joined")
    checklist_item = db.relationship("ChecklistItem", lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "tipo_movimento IN ('ENTRADA', 'SAIDA', 'AJUSTE', 'ATIVIDADE', 'NAO_CONFORMIDADE')",
            name="ck_material_movement_tipo",
        ),
        db.CheckConstraint(
            "quantidade > 0",
            name="ck_material_movement_quantidade_positive",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "material_id": self.material_id,
            "user_id": self.user_id,
            "activity_id": self.activity_id,
            "checklist_item_id": self.checklist_item_id,
            "tipo_movimento": self.tipo_movimento,
            "quantidade": self.quantidade,
            "saldo_anterior": self.saldo_anterior,
            "saldo_posterior": self.saldo_posterior,
            "observacao": self.observacao,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "usuario": self.user.to_dict() if self.user else None,
        }

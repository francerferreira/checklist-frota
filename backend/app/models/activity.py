from __future__ import annotations

from datetime import datetime

from app.extensions import db


class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(160), nullable=False, index=True)
    item_nome = db.Column(db.String(160), nullable=False, index=True)
    tipo_equipamento = db.Column(db.String(20), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=True, index=True)
    quantidade_por_equipamento = db.Column(db.Integer, nullable=False, default=1)
    codigo_peca = db.Column(db.String(80), nullable=True)
    descricao_peca = db.Column(db.String(255), nullable=True)
    fornecedor_peca = db.Column(db.String(160), nullable=True)
    lote_peca = db.Column(db.String(120), nullable=True)
    observacao = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="ABERTA", index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    assigned_mechanic_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    finalized_at = db.Column(db.DateTime, nullable=True)

    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    assigned_mechanic = db.relationship("User", foreign_keys=[assigned_mechanic_user_id], lazy="joined")
    material = db.relationship("Material", lazy="joined")
    items = db.relationship(
        "ActivityItem",
        back_populates="activity",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('ABERTA', 'FINALIZADA')",
            name="ck_activity_status",
        ),
        db.CheckConstraint(
            "quantidade_por_equipamento > 0",
            name="ck_activity_quantidade_por_equipamento_positive",
        ),
    )

    def summary(self) -> dict:
        total = len(self.items)
        installed = sum(1 for item in self.items if item.status_execucao == "INSTALADO")
        not_installed = sum(1 for item in self.items if item.status_execucao == "NAO_INSTALADO")
        pending = sum(1 for item in self.items if item.status_execucao == "PENDENTE")
        return {
            "total": total,
            "instalados": installed,
            "nao_instalados": not_installed,
            "pendentes": pending,
        }

    def to_dict(self, include_items: bool = False) -> dict:
        data = {
            "id": self.id,
            "titulo": self.titulo,
            "item_nome": self.item_nome,
            "tipo_equipamento": self.tipo_equipamento,
            "material_id": self.material_id,
            "material": self.material.to_dict() if self.material else None,
            "quantidade_por_equipamento": self.quantidade_por_equipamento,
            "codigo_peca": self.codigo_peca,
            "descricao_peca": self.descricao_peca,
            "fornecedor_peca": self.fornecedor_peca,
            "lote_peca": self.lote_peca,
            "observacao": self.observacao,
            "status": self.status,
            "assigned_mechanic_user_id": self.assigned_mechanic_user_id,
            "assigned_mechanic": self.assigned_mechanic.to_dict() if self.assigned_mechanic else None,
            "created_at": self.created_at.isoformat(),
            "finalized_at": self.finalized_at.isoformat() if self.finalized_at else None,
            "created_by": self.created_by.to_dict() if self.created_by else None,
            "resumo": self.summary(),
        }
        if include_items:
            data["itens"] = [item.to_dict() for item in self.items]
        return data


class ActivityItem(db.Model):
    __tablename__ = "activity_items"

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=False, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    status_execucao = db.Column(db.String(20), nullable=False, default="PENDENTE", index=True)
    observacao = db.Column(db.Text, nullable=True)
    foto_antes = db.Column(db.String(255), nullable=True)
    foto_depois = db.Column(db.String(255), nullable=True)
    executado_por_nome = db.Column(db.String(120), nullable=True)
    executado_por_login = db.Column(db.String(80), nullable=True)
    instalado_em = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    activity = db.relationship("Activity", back_populates="items")
    vehicle = db.relationship("Vehicle", lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "status_execucao IN ('PENDENTE', 'INSTALADO', 'NAO_INSTALADO')",
            name="ck_activity_item_status_execucao",
        ),
        db.UniqueConstraint("activity_id", "vehicle_id", name="uq_activity_vehicle"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "activity_id": self.activity_id,
            "status_execucao": self.status_execucao,
            "observacao": self.observacao,
            "foto_antes": self.foto_antes,
            "foto_depois": self.foto_depois,
            "executado_por_nome": self.executado_por_nome,
            "executado_por_login": self.executado_por_login,
            "instalado_em": self.instalado_em.isoformat() if self.instalado_em else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "veiculo": self.vehicle.to_dict() if self.vehicle else None,
        }

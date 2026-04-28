from __future__ import annotations

from datetime import datetime

from app.extensions import db


class ChecklistCatalogItem(db.Model):
    __tablename__ = "checklist_catalog_items"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_type = db.Column(db.String(20), nullable=False, index=True)
    item_nome = db.Column(db.String(160), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1, index=True)
    foto_path = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint("vehicle_type", "item_nome", name="uq_checklist_catalog_type_name"),
        db.CheckConstraint(
            "vehicle_type IN ('cavalo', 'carreta', 'carro_simples', 'cavalo_auxiliar', 'ambulancia', 'caminhao_pipa', 'caminhao_brigada', 'onibus', 'van')",
            name="ck_checklist_catalog_vehicle_type",
        ),
        db.CheckConstraint("position > 0", name="ck_checklist_catalog_position_positive"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.vehicle_type,
            "vehicle_type": self.vehicle_type,
            "item_nome": self.item_nome,
            "position": self.position,
            "foto_path": self.foto_path,
            "ativo": self.ativo,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

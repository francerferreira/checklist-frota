from __future__ import annotations

from datetime import datetime

from app.extensions import db


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(16), nullable=False, index=True)
    modelo = db.Column(db.String(120), nullable=False)
    ano = db.Column(db.String(20), nullable=True)
    frota = db.Column(db.String(30), nullable=False, unique=True, index=True)
    tipo = db.Column(db.String(20), nullable=False, index=True)
    chassi = db.Column(db.String(60), nullable=True)
    configuracao = db.Column(db.String(160), nullable=True)
    atividade = db.Column(db.String(160), nullable=True)
    status = db.Column(db.String(30), nullable=True, default="ON", index=True)
    local = db.Column(db.String(120), nullable=True)
    descricao = db.Column(db.String(255), nullable=True)
    foto_path = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    retirado_em = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    checklists = db.relationship(
        "Checklist",
        back_populates="vehicle",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "placa": self.placa,
            "modelo": self.modelo,
            "ano": self.ano,
            "frota": self.frota,
            "tipo": self.tipo,
            "chassi": self.chassi,
            "configuracao": self.configuracao,
            "atividade": self.atividade,
            "status": self.status,
            "local": self.local,
            "descricao": self.descricao,
            "foto_path": self.foto_path,
            "ativo": self.ativo,
            "retirado_em": self.retirado_em.isoformat() if self.retirado_em else None,
        }

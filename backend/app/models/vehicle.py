from __future__ import annotations

from datetime import datetime

from app.extensions import db
from app.utils.timezone import now_manaus_naive


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
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    checklists = db.relationship(
        "Checklist",
        back_populates="vehicle",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    equipment_profile = db.relationship(
        "EquipmentProfile",
        back_populates="vehicle",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )
    equipment_links_as_parent = db.relationship(
        "EquipmentLink",
        foreign_keys="EquipmentLink.parent_vehicle_id",
        back_populates="parent",
        lazy="selectin",
    )
    equipment_links_as_child = db.relationship(
        "EquipmentLink",
        foreign_keys="EquipmentLink.child_vehicle_id",
        back_populates="child",
        lazy="selectin",
    )
    location_movements = db.relationship(
        "EquipmentLocationMovement",
        back_populates="vehicle",
        lazy="dynamic",
    )
    operational_state = db.relationship(
        "EquipmentOperationalState",
        back_populates="vehicle",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )
    status_events = db.relationship(
        "EquipmentStatusEvent",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    hourmeter_readings = db.relationship(
        "HourmeterReading",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    preventive_executions = db.relationship(
        "PreventiveExecution",
        back_populates="vehicle",
        lazy="dynamic",
    )

    def to_dict(self) -> dict:
        profile = self.equipment_profile
        operational_state = self.operational_state
        active_link = next(
            (link for link in self.equipment_links_as_child if link.active),
            None,
        )
        data = {
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
        data.update(
            {
                "mobile_access_code": f"CF-ATIVO-{self.id:06d}",
                "family_id": profile.family_id if profile else None,
                "family": profile.family.to_dict() if profile and profile.family else None,
                "operational_location_id": profile.operational_location_id if profile else None,
                "operational_location": (
                    profile.location.to_dict() if profile and profile.location else None
                ),
                "serial_number": profile.serial_number if profile else None,
                "manufacturer": profile.manufacturer if profile else None,
                "capacity": profile.capacity if profile else None,
                "criticality": profile.criticality if profile else "MEDIA",
                "checklist_available": bool(
                    profile and profile.family and profile.family.checklist_enabled
                ),
                "active_link": active_link.to_dict() if active_link else None,
                "operational_state": (
                    operational_state.to_dict()
                    if operational_state
                    else {
                        "operational_status": "SEM_APONTAMENTO",
                        "status_updated_at": None,
                        "status_reason": None,
                        "status_evidence_path": None,
                        "latest_hourmeter": None,
                        "latest_hourmeter_at": None,
                    }
                ),
            }
        )
        return data

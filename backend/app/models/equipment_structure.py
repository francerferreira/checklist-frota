from __future__ import annotations

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class EquipmentFamily(db.Model):
    __tablename__ = "equipment_families"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255), nullable=True)
    checklist_enabled = db.Column(db.Boolean, nullable=False, default=False, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=now_manaus_naive,
        onupdate=now_manaus_naive,
    )

    profiles = db.relationship("EquipmentProfile", back_populates="family", lazy="select")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "checklist_enabled": self.checklist_enabled,
            "active": self.active,
        }


class OperationalLocation(db.Model):
    __tablename__ = "operational_locations"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    location_type = db.Column(db.String(30), nullable=False, default="OUTRO", index=True)
    parent_id = db.Column(
        db.Integer,
        db.ForeignKey("operational_locations.id"),
        nullable=True,
        index=True,
    )
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=now_manaus_naive,
        onupdate=now_manaus_naive,
    )

    parent = db.relationship(
        "OperationalLocation",
        remote_side=[id],
        backref=db.backref("children", lazy="selectin"),
        lazy="joined",
    )
    profiles = db.relationship("EquipmentProfile", back_populates="location", lazy="select")

    __table_args__ = (
        db.CheckConstraint(
            "location_type IN ('TERMINAL', 'AREA', 'PIER', 'BERCO', 'PATIO', 'OUTRO')",
            name="ck_operational_location_type",
        ),
    )

    def full_name(self) -> str:
        if self.parent:
            return f"{self.parent.name} / {self.name}"
        return self.name

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "full_name": self.full_name(),
            "location_type": self.location_type,
            "parent_id": self.parent_id,
            "parent_name": self.parent.name if self.parent else None,
            "active": self.active,
        }


class EquipmentProfile(db.Model):
    __tablename__ = "equipment_profiles"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicles.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    family_id = db.Column(
        db.Integer,
        db.ForeignKey("equipment_families.id"),
        nullable=False,
        index=True,
    )
    operational_location_id = db.Column(
        db.Integer,
        db.ForeignKey("operational_locations.id"),
        nullable=True,
        index=True,
    )
    serial_number = db.Column(db.String(80), nullable=True, unique=True, index=True)
    manufacturer = db.Column(db.String(120), nullable=True, index=True)
    capacity = db.Column(db.String(80), nullable=True)
    criticality = db.Column(db.String(20), nullable=False, default="MEDIA", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=now_manaus_naive,
        onupdate=now_manaus_naive,
    )

    vehicle = db.relationship("Vehicle", back_populates="equipment_profile")
    family = db.relationship("EquipmentFamily", back_populates="profiles", lazy="joined")
    location = db.relationship("OperationalLocation", back_populates="profiles", lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "criticality IN ('BAIXA', 'MEDIA', 'ALTA', 'CRITICA')",
            name="ck_equipment_profile_criticality",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "family_id": self.family_id,
            "family": self.family.to_dict() if self.family else None,
            "operational_location_id": self.operational_location_id,
            "operational_location": self.location.to_dict() if self.location else None,
            "serial_number": self.serial_number,
            "manufacturer": self.manufacturer,
            "capacity": self.capacity,
            "criticality": self.criticality,
        }


class EquipmentLink(db.Model):
    __tablename__ = "equipment_links"

    id = db.Column(db.Integer, primary_key=True)
    parent_vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicles.id"),
        nullable=False,
        index=True,
    )
    child_vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicles.id"),
        nullable=False,
        index=True,
    )
    link_type = db.Column(db.String(30), nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    ended_at = db.Column(db.DateTime, nullable=True, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    notes = db.Column(db.String(255), nullable=True)
    created_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    parent = db.relationship(
        "Vehicle",
        foreign_keys=[parent_vehicle_id],
        back_populates="equipment_links_as_parent",
        lazy="select",
    )
    child = db.relationship(
        "Vehicle",
        foreign_keys=[child_vehicle_id],
        back_populates="equipment_links_as_child",
        lazy="select",
    )
    created_by = db.relationship("User", lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "link_type IN ('TITULAR', 'RESERVA', 'ACOPLADO', 'OUTRO')",
            name="ck_equipment_link_type",
        ),
        db.CheckConstraint(
            "parent_vehicle_id <> child_vehicle_id",
            name="ck_equipment_link_distinct_assets",
        ),
    )

    @staticmethod
    def _vehicle_summary(vehicle) -> dict | None:
        if not vehicle:
            return None
        return {
            "id": vehicle.id,
            "frota": vehicle.frota,
            "tipo": vehicle.tipo,
            "modelo": vehicle.modelo,
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "parent_vehicle_id": self.parent_vehicle_id,
            "child_vehicle_id": self.child_vehicle_id,
            "link_type": self.link_type,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "active": self.active,
            "notes": self.notes,
            "created_by_user_id": self.created_by_user_id,
            "parent_equipment": self._vehicle_summary(self.parent),
            "child_equipment": self._vehicle_summary(self.child),
        }

from __future__ import annotations

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class Warehouse(db.Model):
    __tablename__ = "warehouses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    location = db.Column(db.String(160), nullable=True)
    warehouse_type = db.Column(db.String(20), nullable=False, default="PRINCIPAL", index=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    stocks = db.relationship("WarehouseStock", back_populates="warehouse", cascade="all, delete-orphan", lazy="selectin")
    locations = db.relationship("WarehouseLocation", back_populates="warehouse", cascade="all, delete-orphan", lazy="selectin")
    transfers_out = db.relationship("WarehouseTransfer", foreign_keys="WarehouseTransfer.source_warehouse_id", back_populates="source_warehouse", lazy="dynamic")
    transfers_in = db.relationship("WarehouseTransfer", foreign_keys="WarehouseTransfer.destination_warehouse_id", back_populates="destination_warehouse", lazy="dynamic")

    def to_dict(self, include_stocks: bool = False) -> dict:
        data = {"id": self.id, "code": self.code, "name": self.name, "location": self.location, "warehouse_type": self.warehouse_type, "active": self.active}
        if include_stocks:
            data["stocks"] = [row.to_dict() for row in self.stocks]
        return data


class WarehouseStock(db.Model):
    __tablename__ = "warehouse_stocks"

    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey("warehouse_locations.id"), nullable=True, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    reserved_quantity = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    warehouse = db.relationship("Warehouse", back_populates="stocks", lazy="joined")
    material = db.relationship("Material", lazy="joined")
    location = db.relationship("WarehouseLocation", back_populates="stocks", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("warehouse_id", "material_id", name="uq_warehouse_stock_material"),
        db.CheckConstraint("quantity >= 0", name="ck_warehouse_stock_quantity"),
        db.CheckConstraint("reserved_quantity >= 0 AND reserved_quantity <= quantity", name="ck_warehouse_stock_reserved"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id, "warehouse_id": self.warehouse_id, "material_id": self.material_id,
            "quantity": self.quantity, "reserved_quantity": self.reserved_quantity,
            "available_quantity": self.quantity - self.reserved_quantity,
            "warehouse": self.warehouse.to_dict() if self.warehouse else None,
            "location": self.location.to_dict() if self.location else None,
            "qr_code": f"MMP-STOCK-{self.id}" if self.warehouse and self.warehouse.warehouse_type == "MMP" else None,
            "material": self.material.to_dict() if self.material else None,
        }


class WarehouseLocation(db.Model):
    __tablename__ = "warehouse_locations"

    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    shelf_code = db.Column(db.String(40), nullable=False)
    location_code = db.Column(db.String(40), nullable=False)
    position_code = db.Column(db.String(40), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    warehouse = db.relationship("Warehouse", back_populates="locations", lazy="joined")
    stocks = db.relationship("WarehouseStock", back_populates="location", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("warehouse_id", "shelf_code", "location_code", "position_code", name="uq_warehouse_location_slot"),
    )

    @property
    def label(self) -> str:
        return f"{self.shelf_code} / {self.location_code} / {self.position_code}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "warehouse_id": self.warehouse_id,
            "shelf_code": self.shelf_code,
            "location_code": self.location_code,
            "position_code": self.position_code,
            "label": self.label,
            "active": self.active,
        }


class WarehouseTransfer(db.Model):
    __tablename__ = "warehouse_transfers"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), nullable=False, unique=True, index=True)
    source_warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    destination_warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="CONCLUIDA", index=True)
    notes = db.Column(db.String(255), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    source_warehouse = db.relationship("Warehouse", foreign_keys=[source_warehouse_id], back_populates="transfers_out", lazy="joined")
    destination_warehouse = db.relationship("Warehouse", foreign_keys=[destination_warehouse_id], back_populates="transfers_in", lazy="joined")
    created_by = db.relationship("User", lazy="joined")
    items = db.relationship("WarehouseTransferItem", back_populates="transfer", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        db.CheckConstraint("status IN ('RASCUNHO', 'CONCLUIDA', 'CANCELADA')", name="ck_warehouse_transfer_status"),
        db.CheckConstraint("source_warehouse_id <> destination_warehouse_id", name="ck_warehouse_transfer_distinct_warehouses"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "source_warehouse": self.source_warehouse.to_dict() if self.source_warehouse else None,
            "destination_warehouse": self.destination_warehouse.to_dict() if self.destination_warehouse else None,
            "status": self.status,
            "notes": self.notes,
            "created_by": self.created_by.to_dict() if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [item.to_dict() for item in self.items],
        }


class WarehouseTransferItem(db.Model):
    __tablename__ = "warehouse_transfer_items"

    id = db.Column(db.Integer, primary_key=True)
    transfer_id = db.Column(db.Integer, db.ForeignKey("warehouse_transfers.id"), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True)
    source_stock_id = db.Column(db.Integer, db.ForeignKey("warehouse_stocks.id"), nullable=False, index=True)
    destination_stock_id = db.Column(db.Integer, db.ForeignKey("warehouse_stocks.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("warehouse_locations.id"), nullable=True, index=True)

    transfer = db.relationship("WarehouseTransfer", back_populates="items")
    material = db.relationship("Material", lazy="joined")
    source_stock = db.relationship("WarehouseStock", foreign_keys=[source_stock_id], lazy="joined")
    destination_stock = db.relationship("WarehouseStock", foreign_keys=[destination_stock_id], lazy="joined")
    location = db.relationship("WarehouseLocation", lazy="joined")

    __table_args__ = (db.CheckConstraint("quantity > 0", name="ck_warehouse_transfer_item_quantity"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "transfer_id": self.transfer_id,
            "material_id": self.material_id,
            "quantity": self.quantity,
            "location": self.location.to_dict() if self.location else None,
            "material": self.material.to_dict() if self.material else None,
            "source_stock_id": self.source_stock_id,
            "destination_stock_id": self.destination_stock_id,
            "qr_code": f"MMP-STOCK-{self.destination_stock_id}",
        }


class MaterialFamilyApplication(db.Model):
    __tablename__ = "material_family_applications"

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True)
    family_id = db.Column(db.Integer, db.ForeignKey("equipment_families.id"), nullable=False, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    material = db.relationship("Material", back_populates="family_applications")
    family = db.relationship("EquipmentFamily", lazy="joined")

    __table_args__ = (db.UniqueConstraint("material_id", "family_id", name="uq_material_family_application"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "material_id": self.material_id, "family_id": self.family_id,
            "active": self.active, "notes": self.notes, "family": self.family.to_dict() if self.family else None,
        }


class WarehouseReservation(db.Model):
    __tablename__ = "warehouse_reservations"

    id = db.Column(db.Integer, primary_key=True)
    maintenance_material_id = db.Column(db.Integer, db.ForeignKey("maintenance_materials.id"), nullable=False, unique=True, index=True)
    warehouse_stock_id = db.Column(db.Integer, db.ForeignKey("warehouse_stocks.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    consumed_quantity = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="RESERVADA", index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    consumed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    maintenance_material = db.relationship("MaintenanceMaterial", lazy="joined")
    warehouse_stock = db.relationship("WarehouseStock", lazy="joined")
    created_by = db.relationship("User", lazy="joined")

    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_warehouse_reservation_quantity"),
        db.CheckConstraint("consumed_quantity >= 0 AND consumed_quantity <= quantity", name="ck_warehouse_reservation_consumed"),
        db.CheckConstraint("status IN ('RESERVADA', 'CONSUMIDA', 'CANCELADA')", name="ck_warehouse_reservation_status"),
    )

    def to_dict(self) -> dict:
        link = self.maintenance_material
        return {
            "id": self.id, "maintenance_material_id": self.maintenance_material_id,
            "warehouse_stock_id": self.warehouse_stock_id, "quantity": self.quantity, "consumed_quantity": self.consumed_quantity, "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "consumed_at": self.consumed_at.isoformat() if self.consumed_at else None,
            "warehouse_stock": self.warehouse_stock.to_dict() if self.warehouse_stock else None,
            "schedule_id": link.schedule_id if link else None, "material_id": link.material_id if link else None,
        }


class TechnicalDocument(db.Model):
    __tablename__ = "technical_documents"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False, index=True)
    document_type = db.Column(db.String(30), nullable=False, index=True)
    revision = db.Column(db.String(30), nullable=False, default="1")
    status = db.Column(db.String(20), nullable=False, default="ATIVO", index=True)
    file_path = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    family_id = db.Column(db.Integer, db.ForeignKey("equipment_families.id"), nullable=True, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True, index=True)
    valid_until = db.Column(db.Date, nullable=True, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    family = db.relationship("EquipmentFamily", lazy="joined")
    vehicle = db.relationship("Vehicle", lazy="joined")
    created_by = db.relationship("User", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("code", "revision", "family_id", "vehicle_id", name="uq_technical_document_revision_scope"),
        db.CheckConstraint("document_type IN ('MANUAL', 'PROCEDIMENTO', 'DIAGRAMA', 'CERTIFICADO', 'OUTRO')", name="ck_technical_document_type"),
        db.CheckConstraint("status IN ('ATIVO', 'ARQUIVADO', 'VENCIDO')", name="ck_technical_document_status"),
        db.CheckConstraint("family_id IS NOT NULL OR vehicle_id IS NOT NULL", name="ck_technical_document_scope"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id, "code": self.code, "title": self.title, "document_type": self.document_type,
            "revision": self.revision, "status": self.status, "file_path": self.file_path,
            "description": self.description, "family_id": self.family_id, "vehicle_id": self.vehicle_id,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "family": self.family.to_dict() if self.family else None,
            "vehicle": self.vehicle.to_dict() if self.vehicle else None,
        }

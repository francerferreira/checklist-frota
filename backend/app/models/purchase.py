from __future__ import annotations

from datetime import date

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    name = db.Column(db.String(180), nullable=False, index=True)
    contact_name = db.Column(db.String(160), nullable=True)
    email = db.Column(db.String(160), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "contact_name": self.contact_name,
            "email": self.email,
            "phone": self.phone,
            "active": self.active,
            "notes": self.notes,
        }


class PurchaseRequest(db.Model):
    __tablename__ = "purchase_requests"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True, index=True)
    maintenance_material_id = db.Column(db.Integer, db.ForeignKey("maintenance_materials.id"), nullable=True, index=True)
    requested_quantity = db.Column(db.Integer, nullable=False)
    received_quantity = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(30), nullable=False, default="SOLICITADA", index=True)
    priority = db.Column(db.String(20), nullable=False, default="MEDIA", index=True)
    expected_date = db.Column(db.Date, nullable=True, index=True)
    observation = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    material = db.relationship("Material", lazy="joined")
    supplier = db.relationship("Supplier", lazy="joined")
    maintenance_material = db.relationship("MaintenanceMaterial", lazy="joined")
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    approved_by = db.relationship("User", foreign_keys=[approved_by_user_id], lazy="joined")
    receipts = db.relationship("PurchaseReceipt", back_populates="purchase_request", cascade="all, delete-orphan", lazy="select")

    __table_args__ = (
        db.CheckConstraint("requested_quantity > 0", name="ck_purchase_request_quantity"),
        db.CheckConstraint("received_quantity >= 0 AND received_quantity <= requested_quantity", name="ck_purchase_request_received"),
        db.CheckConstraint("status IN ('SOLICITADA', 'APROVADA', 'EM_TRANSITO', 'PARCIALMENTE_RECEBIDA', 'RECEBIDA', 'CANCELADA')", name="ck_purchase_request_status"),
        db.CheckConstraint("priority IN ('BAIXA', 'MEDIA', 'ALTA', 'CRITICA')", name="ck_purchase_request_priority"),
    )

    def delayed(self, reference_date: date | None = None) -> bool:
        reference_date = reference_date or date.today()
        return bool(self.expected_date and self.expected_date < reference_date and self.status not in {"RECEBIDA", "CANCELADA"})

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "material_id": self.material_id,
            "supplier_id": self.supplier_id,
            "maintenance_material_id": self.maintenance_material_id,
            "requested_quantity": self.requested_quantity,
            "received_quantity": self.received_quantity,
            "remaining_quantity": self.requested_quantity - self.received_quantity,
            "status": self.status,
            "priority": self.priority,
            "expected_date": self.expected_date.isoformat() if self.expected_date else None,
            "delayed": self.delayed(),
            "observation": self.observation,
            "material": self.material.to_dict() if self.material else None,
            "supplier": self.supplier.to_dict() if self.supplier else None,
        }


class PurchaseReceipt(db.Model):
    __tablename__ = "purchase_receipts"

    id = db.Column(db.Integer, primary_key=True)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey("purchase_requests.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    idempotency_key = db.Column(db.String(80), nullable=False, unique=True, index=True)
    received_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    received_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)

    purchase_request = db.relationship("PurchaseRequest", back_populates="receipts", lazy="joined")
    received_by = db.relationship("User", lazy="joined")

    __table_args__ = (db.CheckConstraint("quantity > 0", name="ck_purchase_receipt_quantity"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "purchase_request_id": self.purchase_request_id,
            "quantity": self.quantity,
            "idempotency_key": self.idempotency_key,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "notes": self.notes,
        }

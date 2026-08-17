from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    name = db.Column(db.String(180), nullable=False, index=True)
    legal_name = db.Column(db.String(220), nullable=True, index=True)
    trade_name = db.Column(db.String(180), nullable=True)
    tax_id = db.Column(db.String(30), nullable=True, index=True)
    contact_name = db.Column(db.String(160), nullable=True)
    email = db.Column(db.String(160), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    homologated = db.Column(db.Boolean, nullable=False, default=False, index=True)
    preferred = db.Column(db.Boolean, nullable=False, default=False, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "legal_name": self.legal_name,
            "trade_name": self.trade_name,
            "tax_id": self.tax_id,
            "contact_name": self.contact_name,
            "email": self.email,
            "phone": self.phone,
            "active": self.active,
            "homologated": self.homologated,
            "preferred": self.preferred,
            "notes": self.notes,
        }


class PurchaseRequest(db.Model):
    __tablename__ = "purchase_requests"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=True, index=True)
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

    company_code = db.Column(db.String(30), nullable=True, index=True)
    branch_code = db.Column(db.String(30), nullable=True, index=True)
    sc_number = db.Column(db.String(60), nullable=True, index=True)
    sc_date = db.Column(db.Date, nullable=True, index=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    requester_raw = db.Column(db.String(180), nullable=True)
    request_type = db.Column(db.String(20), nullable=True, index=True)
    module = db.Column(db.String(40), nullable=True, index=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True, index=True)
    equipment_raw = db.Column(db.String(180), nullable=True)
    work_order_number = db.Column(db.String(80), nullable=True, index=True)
    cost_center = db.Column(db.String(160), nullable=True, index=True)
    justification = db.Column(db.Text, nullable=True)
    external_quote_number = db.Column(db.String(120), nullable=True)
    imported = db.Column(db.Boolean, nullable=False, default=False, index=True)
    import_batch_id = db.Column(db.Integer, db.ForeignKey("purchase_import_batches.id"), nullable=True, index=True)
    data_quality_flags = db.Column(db.JSON, nullable=True)

    material = db.relationship("Material", lazy="joined")
    supplier = db.relationship("Supplier", lazy="joined")
    maintenance_material = db.relationship("MaintenanceMaterial", lazy="joined")
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    approved_by = db.relationship("User", foreign_keys=[approved_by_user_id], lazy="joined")
    receipts = db.relationship("PurchaseReceipt", back_populates="purchase_request", cascade="all, delete-orphan", lazy="select")
    items = db.relationship("PurchaseRequestItem", back_populates="purchase_request", cascade="all, delete-orphan", lazy="selectin")
    requester = db.relationship("User", foreign_keys=[requester_id], lazy="joined")
    equipment = db.relationship("Vehicle", foreign_keys=[equipment_id], lazy="joined")

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
            "sc_number": self.sc_number or self.code,
            "company_code": self.company_code,
            "branch_code": self.branch_code,
            "sc_date": self.sc_date.isoformat() if self.sc_date else None,
            "requester_raw": self.requester_raw,
            "request_type": self.request_type or ("MATERIAL" if self.material_id else None),
            "module": self.module,
            "equipment_id": self.equipment_id,
            "equipment_raw": self.equipment_raw,
            "work_order_number": self.work_order_number,
            "cost_center": self.cost_center,
            "justification": self.justification or self.observation,
            "external_quote_number": self.external_quote_number,
            "imported": self.imported,
            "data_quality_flags": self.data_quality_flags or [],
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
            "items": [item.to_dict() for item in self.items],
        }


class PurchaseServiceCatalog(db.Model):
    __tablename__ = "purchase_service_catalog"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), nullable=False, unique=True, index=True)
    service_name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    specialty = db.Column(db.String(120), nullable=True)
    module = db.Column(db.String(40), nullable=True, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    imported = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "service_name": self.service_name,
            "description": self.description,
            "specialty": self.specialty,
            "module": self.module,
            "active": self.active,
            "imported": self.imported,
        }


class PurchaseRequestItem(db.Model):
    __tablename__ = "purchase_request_items"

    id = db.Column(db.Integer, primary_key=True)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey("purchase_requests.id"), nullable=False, index=True)
    line_number = db.Column(db.Integer, nullable=False)
    item_type = db.Column(db.String(20), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=True, index=True)
    service_catalog_id = db.Column(db.Integer, db.ForeignKey("purchase_service_catalog.id"), nullable=True, index=True)
    product_code_raw = db.Column(db.String(120), nullable=True, index=True)
    description_raw = db.Column(db.Text, nullable=False)
    brand_raw = db.Column(db.String(180), nullable=True)
    manual_reference_raw = db.Column(db.String(180), nullable=True)
    manufacturer_part_number_raw = db.Column(db.String(180), nullable=True)
    quantity_requested = db.Column(db.Numeric(18, 4), nullable=False)
    unit_of_measure = db.Column(db.String(30), nullable=True)
    quantity_received = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    status = db.Column(db.String(30), nullable=False, default="AGUARDANDO_PC", index=True)
    notes = db.Column(db.Text, nullable=True)
    imported = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    purchase_request = db.relationship("PurchaseRequest", back_populates="items")
    material = db.relationship("Material", lazy="joined")
    service_catalog = db.relationship("PurchaseServiceCatalog", lazy="joined")
    order_links = db.relationship("PurchaseOrderItem", back_populates="request_item", lazy="selectin")

    __table_args__ = (
        db.UniqueConstraint("purchase_request_id", "line_number", name="uq_purchase_request_item_line"),
        db.CheckConstraint("quantity_requested > 0", name="ck_purchase_request_item_quantity"),
        db.CheckConstraint("quantity_received >= 0 AND quantity_received <= quantity_requested", name="ck_purchase_request_item_received"),
        db.CheckConstraint("item_type IN ('MATERIAL', 'SERVICO')", name="ck_purchase_request_item_type"),
    )

    def to_dict(self) -> dict:
        requested = Decimal(self.quantity_requested or 0)
        received = Decimal(self.quantity_received or 0)
        return {
            "id": self.id,
            "purchase_request_id": self.purchase_request_id,
            "line_number": self.line_number,
            "item_type": self.item_type,
            "material_id": self.material_id,
            "service_catalog_id": self.service_catalog_id,
            "product_code_raw": self.product_code_raw,
            "description_raw": self.description_raw,
            "brand_raw": self.brand_raw,
            "manual_reference_raw": self.manual_reference_raw,
            "manufacturer_part_number_raw": self.manufacturer_part_number_raw,
            "quantity_requested": float(requested),
            "unit_of_measure": self.unit_of_measure,
            "quantity_received": float(received),
            "remaining_quantity": float(requested - received),
            "status": self.status,
            "material": self.material.to_dict() if self.material else None,
            "service": self.service_catalog.to_dict() if self.service_catalog else None,
        }


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"

    id = db.Column(db.Integer, primary_key=True)
    pc_number = db.Column(db.String(60), nullable=False, index=True)
    pc_date = db.Column(db.Date, nullable=True, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    buyer_raw = db.Column(db.String(180), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True, index=True)
    supplier_raw = db.Column(db.String(220), nullable=True)
    delivery_due_date = db.Column(db.Date, nullable=True, index=True)
    total_value = db.Column(db.Numeric(18, 2), nullable=True)
    payment_terms = db.Column(db.String(180), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="EMITIDO", index=True)
    company_code = db.Column(db.String(30), nullable=True, index=True)
    branch_code = db.Column(db.String(30), nullable=True, index=True)
    imported = db.Column(db.Boolean, nullable=False, default=False, index=True)
    import_batch_id = db.Column(db.Integer, db.ForeignKey("purchase_import_batches.id"), nullable=True, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    buyer = db.relationship("User", foreign_keys=[buyer_id], lazy="joined")
    supplier = db.relationship("Supplier", lazy="joined")
    items = db.relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan", lazy="selectin")
    invoice_links = db.relationship("InvoicePurchaseOrderLink", back_populates="purchase_order", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (db.UniqueConstraint("pc_number", "company_code", "branch_code", name="uq_purchase_order_business_key"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pc_number": self.pc_number,
            "pc_date": self.pc_date.isoformat() if self.pc_date else None,
            "buyer_raw": self.buyer_raw,
            "supplier_raw": self.supplier_raw,
            "delivery_due_date": self.delivery_due_date.isoformat() if self.delivery_due_date else None,
            "total_value": float(self.total_value) if self.total_value is not None else None,
            "payment_terms": self.payment_terms,
            "notes": self.notes,
            "status": self.status,
            "imported": self.imported,
            "supplier": self.supplier.to_dict() if self.supplier else None,
            "items": [item.to_dict() for item in self.items],
            "invoices": [link.invoice.to_dict() for link in self.invoice_links if link.invoice],
        }


class PurchaseOrderItem(db.Model):
    __tablename__ = "purchase_order_items"

    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False, index=True)
    purchase_request_item_id = db.Column(db.Integer, db.ForeignKey("purchase_request_items.id"), nullable=False, index=True)
    quantity_ordered = db.Column(db.Numeric(18, 4), nullable=False)
    unit_price = db.Column(db.Numeric(18, 4), nullable=True)
    total_price = db.Column(db.Numeric(18, 2), nullable=True)
    expected_delivery_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="EMITIDO", index=True)

    purchase_order = db.relationship("PurchaseOrder", back_populates="items")
    request_item = db.relationship("PurchaseRequestItem", back_populates="order_links", lazy="joined")

    __table_args__ = (db.CheckConstraint("quantity_ordered > 0", name="ck_purchase_order_item_quantity"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "purchase_order_id": self.purchase_order_id,
            "purchase_request_item_id": self.purchase_request_item_id,
            "quantity_ordered": float(self.quantity_ordered or 0),
            "unit_price": float(self.unit_price) if self.unit_price is not None else None,
            "total_price": float(self.total_price) if self.total_price is not None else None,
            "expected_delivery_date": self.expected_delivery_date.isoformat() if self.expected_delivery_date else None,
            "status": self.status,
            "request_item": self.request_item.to_dict() if self.request_item else None,
        }


class PurchaseInvoice(db.Model):
    __tablename__ = "purchase_invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(80), nullable=False, index=True)
    series = db.Column(db.String(30), nullable=True, index=True)
    access_key = db.Column(db.String(60), nullable=True, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True, index=True)
    supplier_raw = db.Column(db.String(220), nullable=True)
    invoice_date = db.Column(db.Date, nullable=True, index=True)
    invoice_value = db.Column(db.Numeric(18, 2), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="RECEBIDA", index=True)
    received_at = db.Column(db.DateTime, nullable=True)
    received_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    received_by_raw = db.Column(db.String(180), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    imported = db.Column(db.Boolean, nullable=False, default=False, index=True)
    import_batch_id = db.Column(db.Integer, db.ForeignKey("purchase_import_batches.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    supplier = db.relationship("Supplier", lazy="joined")
    purchase_order_links = db.relationship("InvoicePurchaseOrderLink", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin")
    items = db.relationship("PurchaseInvoiceItem", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (db.UniqueConstraint("supplier_id", "series", "invoice_number", name="uq_purchase_invoice_supplier_series_number"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "invoice_number": self.invoice_number,
            "series": self.series,
            "access_key": self.access_key,
            "supplier_raw": self.supplier_raw,
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None,
            "invoice_value": float(self.invoice_value) if self.invoice_value is not None else None,
            "status": self.status,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "received_by_raw": self.received_by_raw,
            "imported": self.imported,
            "supplier": self.supplier.to_dict() if self.supplier else None,
            "purchase_orders": [link.purchase_order.to_dict() for link in self.purchase_order_links if link.purchase_order],
            "items": [item.to_dict() for item in self.items],
        }


class InvoicePurchaseOrderLink(db.Model):
    __tablename__ = "invoice_purchase_order_links"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("purchase_invoices.id"), nullable=False, index=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False, index=True)
    linked_value = db.Column(db.Numeric(18, 2), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    invoice = db.relationship("PurchaseInvoice", back_populates="purchase_order_links")
    purchase_order = db.relationship("PurchaseOrder", back_populates="invoice_links")

    __table_args__ = (db.UniqueConstraint("invoice_id", "purchase_order_id", name="uq_invoice_purchase_order_link"),)


class PurchaseInvoiceItem(db.Model):
    __tablename__ = "purchase_invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("purchase_invoices.id"), nullable=False, index=True)
    purchase_order_item_id = db.Column(db.Integer, db.ForeignKey("purchase_order_items.id"), nullable=False, index=True)
    quantity_invoiced = db.Column(db.Numeric(18, 4), nullable=True)
    quantity_received = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    received_at = db.Column(db.DateTime, nullable=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    divergence_type = db.Column(db.String(40), nullable=True)
    divergence_notes = db.Column(db.Text, nullable=True)
    accepted = db.Column(db.Boolean, nullable=False, default=True)

    invoice = db.relationship("PurchaseInvoice", back_populates="items")
    purchase_order_item = db.relationship("PurchaseOrderItem", lazy="joined")
    receiver = db.relationship("User", lazy="joined")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "purchase_order_item_id": self.purchase_order_item_id,
            "quantity_invoiced": float(self.quantity_invoiced) if self.quantity_invoiced is not None else None,
            "quantity_received": float(self.quantity_received or 0),
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "divergence_type": self.divergence_type,
            "divergence_notes": self.divergence_notes,
            "accepted": self.accepted,
        }


class PurchaseImportBatch(db.Model):
    __tablename__ = "purchase_import_batches"

    id = db.Column(db.Integer, primary_key=True)
    source_filename = db.Column(db.String(255), nullable=False)
    source_checksum = db.Column(db.String(128), nullable=False, unique=True, index=True)
    started_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    finished_at = db.Column(db.DateTime, nullable=True)
    imported_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    rows_read = db.Column(db.Integer, nullable=False, default=0)
    rows_created = db.Column(db.Integer, nullable=False, default=0)
    rows_updated = db.Column(db.Integer, nullable=False, default=0)
    rows_ignored = db.Column(db.Integer, nullable=False, default=0)
    errors = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="PROCESSANDO", index=True)

    source_rows = db.relationship("PurchaseImportSourceRow", back_populates="batch", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self) -> dict:
        return {"id": self.id, "source_filename": self.source_filename, "source_checksum": self.source_checksum, "started_at": self.started_at.isoformat() if self.started_at else None, "finished_at": self.finished_at.isoformat() if self.finished_at else None, "rows_read": self.rows_read, "rows_created": self.rows_created, "rows_updated": self.rows_updated, "rows_ignored": self.rows_ignored, "errors": self.errors or [], "status": self.status}


class PurchaseImportSourceRow(db.Model):
    __tablename__ = "purchase_import_source_rows"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("purchase_import_batches.id"), nullable=False, index=True)
    source_row_number = db.Column(db.Integer, nullable=False)
    source_hash = db.Column(db.String(128), nullable=False, index=True)
    source_payload = db.Column(db.JSON, nullable=False)
    normalized_entity_ids = db.Column(db.JSON, nullable=True)
    result = db.Column(db.String(20), nullable=False, default="IMPORTADO", index=True)

    batch = db.relationship("PurchaseImportBatch", back_populates="source_rows")

    __table_args__ = (db.UniqueConstraint("batch_id", "source_row_number", name="uq_purchase_import_source_row"),)


class PurchaseProcessEvent(db.Model):
    __tablename__ = "purchase_process_events"

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(40), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    event_type = db.Column(db.String(40), nullable=False, index=True)
    old_status = db.Column(db.String(40), nullable=True)
    new_status = db.Column(db.String(40), nullable=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    comment = db.Column(db.Text, nullable=True)
    event_metadata = db.Column("metadata", db.JSON, nullable=True)


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

"""Create the canonical purchase flow and historical import traceability."""

from alembic import op
import sqlalchemy as sa


revision = "20260816_0017"
down_revision = "20260816_0016"
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table):
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _add_column(table, column):
    if table in _tables() and column.name not in _columns(table):
        op.add_column(table, column)


def _create_index_if_missing(name, table, columns):
    if table not in _tables():
        return
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}
    if name not in indexes:
        op.create_index(name, table, columns)


def upgrade():
    # Keep the existing compatibility API, while adding canonical SC fields.
    for column in (
        sa.Column("legal_name", sa.String(220), nullable=True),
        sa.Column("trade_name", sa.String(180), nullable=True),
        sa.Column("tax_id", sa.String(30), nullable=True),
        sa.Column("homologated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
    ):
        _add_column("suppliers", column)

    for column in (
        sa.Column("company_code", sa.String(30), nullable=True),
        sa.Column("branch_code", sa.String(30), nullable=True),
        sa.Column("sc_number", sa.String(60), nullable=True),
        sa.Column("sc_date", sa.Date(), nullable=True),
        sa.Column("requester_id", sa.Integer(), nullable=True),
        sa.Column("requester_raw", sa.String(180), nullable=True),
        sa.Column("request_type", sa.String(20), nullable=True),
        sa.Column("module", sa.String(40), nullable=True),
        sa.Column("equipment_id", sa.Integer(), nullable=True),
        sa.Column("equipment_raw", sa.String(180), nullable=True),
        sa.Column("work_order_number", sa.String(80), nullable=True),
        sa.Column("cost_center", sa.String(160), nullable=True),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("external_quote_number", sa.String(120), nullable=True),
        sa.Column("imported", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
        sa.Column("data_quality_flags", sa.JSON(), nullable=True),
    ):
        _add_column("purchase_requests", column)

    # Service-only historical requests need a nullable compatibility material_id.
    if "purchase_requests" in _tables() and "material_id" in _columns("purchase_requests"):
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table("purchase_requests", recreate="always") as batch:
                batch.alter_column("material_id", existing_type=sa.Integer(), nullable=True)
        else:
            op.alter_column("purchase_requests", "material_id", existing_type=sa.Integer(), nullable=True)

    tables = _tables()
    if "purchase_import_batches" not in tables:
        op.create_table(
            "purchase_import_batches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_filename", sa.String(255), nullable=False),
            sa.Column("source_checksum", sa.String(128), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("imported_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("rows_read", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rows_created", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rows_updated", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rows_ignored", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("errors", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="PROCESSANDO"),
            sa.UniqueConstraint("source_checksum", name="uq_purchase_import_batch_checksum"),
        )
    if "purchase_import_source_rows" not in tables:
        op.create_table(
            "purchase_import_source_rows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("purchase_import_batches.id"), nullable=False),
            sa.Column("source_row_number", sa.Integer(), nullable=False),
            sa.Column("source_hash", sa.String(128), nullable=False),
            sa.Column("source_payload", sa.JSON(), nullable=False),
            sa.Column("normalized_entity_ids", sa.JSON(), nullable=True),
            sa.Column("result", sa.String(20), nullable=False, server_default="IMPORTADO"),
            sa.UniqueConstraint("batch_id", "source_row_number", name="uq_purchase_import_source_row"),
        )
    if "purchase_service_catalog" not in tables:
        op.create_table(
            "purchase_service_catalog",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(80), nullable=False),
            sa.Column("service_name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("specialty", sa.String(120), nullable=True),
            sa.Column("module", sa.String(40), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("imported", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("code", name="uq_purchase_service_catalog_code"),
        )
    if "purchase_request_items" not in tables:
        op.create_table(
            "purchase_request_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("purchase_request_id", sa.Integer(), sa.ForeignKey("purchase_requests.id"), nullable=False),
            sa.Column("line_number", sa.Integer(), nullable=False),
            sa.Column("item_type", sa.String(20), nullable=False),
            sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=True),
            sa.Column("service_catalog_id", sa.Integer(), sa.ForeignKey("purchase_service_catalog.id"), nullable=True),
            sa.Column("product_code_raw", sa.String(120), nullable=True),
            sa.Column("description_raw", sa.Text(), nullable=False),
            sa.Column("brand_raw", sa.String(180), nullable=True),
            sa.Column("manual_reference_raw", sa.String(180), nullable=True),
            sa.Column("manufacturer_part_number_raw", sa.String(180), nullable=True),
            sa.Column("quantity_requested", sa.Numeric(18, 4), nullable=False),
            sa.Column("unit_of_measure", sa.String(30), nullable=True),
            sa.Column("quantity_received", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("status", sa.String(30), nullable=False, server_default="AGUARDANDO_PC"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("imported", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("purchase_request_id", "line_number", name="uq_purchase_request_item_line"),
        )
    if "purchase_orders" not in tables:
        op.create_table(
            "purchase_orders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("pc_number", sa.String(60), nullable=False),
            sa.Column("pc_date", sa.Date(), nullable=True),
            sa.Column("buyer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("buyer_raw", sa.String(180), nullable=True),
            sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
            sa.Column("supplier_raw", sa.String(220), nullable=True),
            sa.Column("delivery_due_date", sa.Date(), nullable=True),
            sa.Column("total_value", sa.Numeric(18, 2), nullable=True),
            sa.Column("payment_terms", sa.String(180), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="EMITIDO"),
            sa.Column("company_code", sa.String(30), nullable=True),
            sa.Column("branch_code", sa.String(30), nullable=True),
            sa.Column("imported", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("import_batch_id", sa.Integer(), sa.ForeignKey("purchase_import_batches.id"), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("pc_number", "company_code", "branch_code", name="uq_purchase_order_business_key"),
        )
    if "purchase_order_items" not in tables:
        op.create_table(
            "purchase_order_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=False),
            sa.Column("purchase_request_item_id", sa.Integer(), sa.ForeignKey("purchase_request_items.id"), nullable=False),
            sa.Column("quantity_ordered", sa.Numeric(18, 4), nullable=False),
            sa.Column("unit_price", sa.Numeric(18, 4), nullable=True),
            sa.Column("total_price", sa.Numeric(18, 2), nullable=True),
            sa.Column("expected_delivery_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="EMITIDO"),
        )
    if "purchase_invoices" not in tables:
        op.create_table(
            "purchase_invoices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("invoice_number", sa.String(80), nullable=False),
            sa.Column("series", sa.String(30), nullable=True),
            sa.Column("access_key", sa.String(60), nullable=True),
            sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=True),
            sa.Column("supplier_raw", sa.String(220), nullable=True),
            sa.Column("invoice_date", sa.Date(), nullable=True),
            sa.Column("invoice_value", sa.Numeric(18, 2), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="RECEBIDA"),
            sa.Column("received_at", sa.DateTime(), nullable=True),
            sa.Column("received_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("received_by_raw", sa.String(180), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("imported", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("import_batch_id", sa.Integer(), sa.ForeignKey("purchase_import_batches.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("supplier_id", "series", "invoice_number", name="uq_purchase_invoice_supplier_series_number"),
        )
    if "invoice_purchase_order_links" not in tables:
        op.create_table(
            "invoice_purchase_order_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("purchase_invoices.id"), nullable=False),
            sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=False),
            sa.Column("linked_value", sa.Numeric(18, 2), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("invoice_id", "purchase_order_id", name="uq_invoice_purchase_order_link"),
        )
    if "purchase_invoice_items" not in tables:
        op.create_table(
            "purchase_invoice_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("purchase_invoices.id"), nullable=False),
            sa.Column("purchase_order_item_id", sa.Integer(), sa.ForeignKey("purchase_order_items.id"), nullable=False),
            sa.Column("quantity_invoiced", sa.Numeric(18, 4), nullable=True),
            sa.Column("quantity_received", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("received_at", sa.DateTime(), nullable=True),
            sa.Column("receiver_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("divergence_type", sa.String(40), nullable=True),
            sa.Column("divergence_notes", sa.Text(), nullable=True),
            sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "purchase_process_events" not in tables:
        op.create_table(
            "purchase_process_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("entity_type", sa.String(40), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(40), nullable=False),
            sa.Column("old_status", sa.String(40), nullable=True),
            sa.Column("new_status", sa.String(40), nullable=True),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
        )

    for table, name, columns in (
        ("suppliers", "ix_suppliers_tax_id", ["tax_id"]),
        ("purchase_requests", "ix_purchase_requests_sc_number", ["sc_number"]),
        ("purchase_requests", "ix_purchase_requests_module", ["module"]),
        ("purchase_requests", "ix_purchase_requests_imported", ["imported"]),
        ("purchase_request_items", "ix_purchase_request_items_product_code_raw", ["product_code_raw"]),
        ("purchase_request_items", "ix_purchase_request_items_material_id", ["material_id"]),
        ("purchase_orders", "ix_purchase_orders_pc_number", ["pc_number"]),
        ("purchase_invoices", "ix_purchase_invoices_invoice_number", ["invoice_number"]),
        ("purchase_process_events", "ix_purchase_process_events_entity", ["entity_type", "entity_id"]),
    ):
        _create_index_if_missing(name, table, columns)


def downgrade():
    for table in (
        "purchase_process_events",
        "purchase_invoice_items",
        "invoice_purchase_order_links",
        "purchase_invoices",
        "purchase_order_items",
        "purchase_orders",
        "purchase_request_items",
        "purchase_service_catalog",
        "purchase_import_source_rows",
        "purchase_import_batches",
    ):
        if table in _tables():
            op.drop_table(table)

    if "purchase_requests" in _tables():
        for name in ("ix_purchase_requests_sc_number", "ix_purchase_requests_module", "ix_purchase_requests_imported"):
            try:
                op.drop_index(name, table_name="purchase_requests")
            except Exception:
                pass
        columns = _columns("purchase_requests")
        for name in ("data_quality_flags", "import_batch_id", "imported", "external_quote_number", "justification", "cost_center", "work_order_number", "equipment_raw", "equipment_id", "module", "request_type", "requester_raw", "requester_id", "sc_date", "sc_number", "branch_code", "company_code"):
            if name in columns:
                op.drop_column("purchase_requests", name)
    if "suppliers" in _tables():
        try:
            op.drop_index("ix_suppliers_tax_id", table_name="suppliers")
        except Exception:
            pass
        for name in ("preferred", "homologated", "tax_id", "trade_name", "legal_name"):
            if name in _columns("suppliers"):
                op.drop_column("suppliers", name)

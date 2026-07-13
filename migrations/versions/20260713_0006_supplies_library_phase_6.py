"""supplies and technical library phase 6

Revision ID: 20260713_0006
Revises: 20260712_0005
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa


revision = "20260713_0006"
down_revision = "20260712_0005"
branch_labels = None
depends_on = None


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "warehouses" not in tables:
        op.create_table("warehouses", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("code", sa.String(40), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("location", sa.String(160)), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("code", name="uq_warehouse_code"))
        for column in ("code", "name", "active"): op.create_index(f"ix_warehouses_{column}", "warehouses", [column])
        tables.add("warehouses")
    if "warehouse_stocks" not in tables:
        op.create_table("warehouse_stocks", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("warehouse_id", sa.Integer(), nullable=False), sa.Column("material_id", sa.Integer(), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"), sa.Column("reserved_quantity", sa.Integer(), nullable=False, server_default="0"), sa.Column("updated_at", sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]), sa.ForeignKeyConstraint(["material_id"], ["materials.id"]), sa.UniqueConstraint("warehouse_id", "material_id", name="uq_warehouse_stock_material"), sa.CheckConstraint("quantity >= 0", name="ck_warehouse_stock_quantity"), sa.CheckConstraint("reserved_quantity >= 0 AND reserved_quantity <= quantity", name="ck_warehouse_stock_reserved"))
        for column in ("warehouse_id", "material_id"): op.create_index(f"ix_warehouse_stocks_{column}", "warehouse_stocks", [column])
        tables.add("warehouse_stocks")
    if "material_family_applications" not in tables:
        op.create_table("material_family_applications", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("material_id", sa.Integer(), nullable=False), sa.Column("family_id", sa.Integer(), nullable=False), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("notes", sa.String(255)), sa.Column("created_at", sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(["material_id"], ["materials.id"]), sa.ForeignKeyConstraint(["family_id"], ["equipment_families.id"]), sa.UniqueConstraint("material_id", "family_id", name="uq_material_family_application"))
        for column in ("material_id", "family_id", "active"): op.create_index(f"ix_material_family_applications_{column}", "material_family_applications", [column])
        tables.add("material_family_applications")
    if "warehouse_reservations" not in tables:
        op.create_table("warehouse_reservations", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("maintenance_material_id", sa.Integer(), nullable=False), sa.Column("warehouse_stock_id", sa.Integer(), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("consumed_quantity", sa.Integer(), nullable=False, server_default="0"), sa.Column("status", sa.String(20), nullable=False, server_default="RESERVADA"), sa.Column("created_by_user_id", sa.Integer(), nullable=False), sa.Column("consumed_at", sa.DateTime()), sa.Column("created_at", sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(["maintenance_material_id"], ["maintenance_materials.id"]), sa.ForeignKeyConstraint(["warehouse_stock_id"], ["warehouse_stocks.id"]), sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]), sa.UniqueConstraint("maintenance_material_id", name="uq_warehouse_reservation_maintenance_material"), sa.CheckConstraint("quantity > 0", name="ck_warehouse_reservation_quantity"), sa.CheckConstraint("consumed_quantity >= 0 AND consumed_quantity <= quantity", name="ck_warehouse_reservation_consumed"), sa.CheckConstraint("status IN ('RESERVADA', 'CONSUMIDA', 'CANCELADA')", name="ck_warehouse_reservation_status"))
        for column in ("maintenance_material_id", "warehouse_stock_id", "status", "created_by_user_id"): op.create_index(f"ix_warehouse_reservations_{column}", "warehouse_reservations", [column])
        tables.add("warehouse_reservations")
    if "technical_documents" not in tables:
        op.create_table("technical_documents", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("code", sa.String(60), nullable=False), sa.Column("title", sa.String(180), nullable=False), sa.Column("document_type", sa.String(30), nullable=False), sa.Column("revision", sa.String(30), nullable=False, server_default="1"), sa.Column("status", sa.String(20), nullable=False, server_default="ATIVO"), sa.Column("file_path", sa.String(255), nullable=False), sa.Column("description", sa.Text()), sa.Column("family_id", sa.Integer()), sa.Column("vehicle_id", sa.Integer()), sa.Column("valid_until", sa.Date()), sa.Column("created_by_user_id", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(["family_id"], ["equipment_families.id"]), sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]), sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]), sa.UniqueConstraint("code", "revision", "family_id", "vehicle_id", name="uq_technical_document_revision_scope"), sa.CheckConstraint("document_type IN ('MANUAL', 'PROCEDIMENTO', 'DIAGRAMA', 'CERTIFICADO', 'OUTRO')", name="ck_technical_document_type"), sa.CheckConstraint("status IN ('ATIVO', 'ARQUIVADO', 'VENCIDO')", name="ck_technical_document_status"), sa.CheckConstraint("family_id IS NOT NULL OR vehicle_id IS NOT NULL", name="ck_technical_document_scope"))
        for column in ("code", "title", "document_type", "status", "family_id", "vehicle_id", "valid_until", "created_by_user_id"): op.create_index(f"ix_technical_documents_{column}", "technical_documents", [column])


def downgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for name in ("technical_documents", "warehouse_reservations", "material_family_applications", "warehouse_stocks", "warehouses"):
        if name in tables: op.drop_table(name)

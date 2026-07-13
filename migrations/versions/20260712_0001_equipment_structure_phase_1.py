"""equipment structure phase 1

Revision ID: 20260712_0001
Revises: 20260712_0000
Create Date: 2026-07-12 22:37:37.177313

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260712_0001'
down_revision = '20260712_0000'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())

    if 'equipment_families' not in existing_tables:
        op.create_table(
            'equipment_families',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('code', sa.String(length=20), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
            sa.Column('checklist_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('code'),
            sa.UniqueConstraint('name'),
        )
        op.create_index('ix_equipment_families_code', 'equipment_families', ['code'])
        op.create_index('ix_equipment_families_name', 'equipment_families', ['name'])
        op.create_index('ix_equipment_families_active', 'equipment_families', ['active'])
        op.create_index(
            'ix_equipment_families_checklist_enabled',
            'equipment_families',
            ['checklist_enabled'],
        )
        existing_tables.add('equipment_families')

    if 'operational_locations' not in existing_tables:
        op.create_table(
            'operational_locations',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('code', sa.String(length=80), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('location_type', sa.String(length=30), nullable=False, server_default='OUTRO'),
            sa.Column('parent_id', sa.Integer(), nullable=True),
            sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint(
                "location_type IN ('TERMINAL', 'AREA', 'PIER', 'BERCO', 'PATIO', 'OUTRO')",
                name='ck_operational_location_type',
            ),
            sa.ForeignKeyConstraint(['parent_id'], ['operational_locations.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('code'),
        )
        op.create_index('ix_operational_locations_code', 'operational_locations', ['code'])
        op.create_index('ix_operational_locations_name', 'operational_locations', ['name'])
        op.create_index('ix_operational_locations_location_type', 'operational_locations', ['location_type'])
        op.create_index('ix_operational_locations_parent_id', 'operational_locations', ['parent_id'])
        op.create_index('ix_operational_locations_active', 'operational_locations', ['active'])
        existing_tables.add('operational_locations')

    if 'equipment_profiles' not in existing_tables:
        op.create_table(
            'equipment_profiles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('vehicle_id', sa.Integer(), nullable=False),
            sa.Column('family_id', sa.Integer(), nullable=False),
            sa.Column('operational_location_id', sa.Integer(), nullable=True),
            sa.Column('serial_number', sa.String(length=80), nullable=True),
            sa.Column('manufacturer', sa.String(length=120), nullable=True),
            sa.Column('capacity', sa.String(length=80), nullable=True),
            sa.Column('criticality', sa.String(length=20), nullable=False, server_default='MEDIA'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint(
                "criticality IN ('BAIXA', 'MEDIA', 'ALTA', 'CRITICA')",
                name='ck_equipment_profile_criticality',
            ),
            sa.ForeignKeyConstraint(['family_id'], ['equipment_families.id']),
            sa.ForeignKeyConstraint(['operational_location_id'], ['operational_locations.id']),
            sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('serial_number'),
            sa.UniqueConstraint('vehicle_id'),
        )
        op.create_index('ix_equipment_profiles_vehicle_id', 'equipment_profiles', ['vehicle_id'])
        op.create_index('ix_equipment_profiles_family_id', 'equipment_profiles', ['family_id'])
        op.create_index(
            'ix_equipment_profiles_operational_location_id',
            'equipment_profiles',
            ['operational_location_id'],
        )
        op.create_index('ix_equipment_profiles_serial_number', 'equipment_profiles', ['serial_number'])
        op.create_index('ix_equipment_profiles_manufacturer', 'equipment_profiles', ['manufacturer'])
        op.create_index('ix_equipment_profiles_criticality', 'equipment_profiles', ['criticality'])
        existing_tables.add('equipment_profiles')

    if 'equipment_links' not in existing_tables:
        op.create_table(
            'equipment_links',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('parent_vehicle_id', sa.Integer(), nullable=False),
            sa.Column('child_vehicle_id', sa.Integer(), nullable=False),
            sa.Column('link_type', sa.String(length=30), nullable=False),
            sa.Column('started_at', sa.DateTime(), nullable=False),
            sa.Column('ended_at', sa.DateTime(), nullable=True),
            sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('notes', sa.String(length=255), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint(
                "link_type IN ('TITULAR', 'RESERVA', 'ACOPLADO', 'OUTRO')",
                name='ck_equipment_link_type',
            ),
            sa.CheckConstraint(
                'parent_vehicle_id <> child_vehicle_id',
                name='ck_equipment_link_distinct_assets',
            ),
            sa.ForeignKeyConstraint(['child_vehicle_id'], ['vehicles.id']),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['parent_vehicle_id'], ['vehicles.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_equipment_links_parent_vehicle_id', 'equipment_links', ['parent_vehicle_id'])
        op.create_index('ix_equipment_links_child_vehicle_id', 'equipment_links', ['child_vehicle_id'])
        op.create_index('ix_equipment_links_link_type', 'equipment_links', ['link_type'])
        op.create_index('ix_equipment_links_started_at', 'equipment_links', ['started_at'])
        op.create_index('ix_equipment_links_ended_at', 'equipment_links', ['ended_at'])
        op.create_index('ix_equipment_links_active', 'equipment_links', ['active'])
        op.create_index('ix_equipment_links_created_by_user_id', 'equipment_links', ['created_by_user_id'])

    family_rows = (
        ('cavalo', 'Cavalo', True),
        ('carreta', 'Carreta', True),
        ('carro_simples', 'Carro simples', True),
        ('cavalo_auxiliar', 'Cavalo auxiliar', True),
        ('ambulancia', 'Ambulancia', True),
        ('caminhao_pipa', 'Caminhao pipa', True),
        ('caminhao_brigada', 'Caminhao brigada', True),
        ('onibus', 'Onibus', True),
        ('van', 'Van', True),
        ('auxiliar', 'Auxiliar legado', False),
        ('rtg', 'RTG', False),
        ('lbs', 'LBS', False),
        ('spreader', 'Spreader', False),
    )
    existing_codes = {
        row[0] for row in bind.execute(sa.text('SELECT code FROM equipment_families')).fetchall()
    }
    for code, name, checklist_enabled in family_rows:
        if code in existing_codes:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO equipment_families
                    (code, name, checklist_enabled, active, created_at, updated_at)
                VALUES
                    (:code, :name, :checklist_enabled, :active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                'code': code,
                'name': name,
                'checklist_enabled': checklist_enabled,
                'active': True,
            },
        )

    if 'equipment_profiles' in set(sa.inspect(bind).get_table_names()):
        bind.execute(
            sa.text(
                """
                INSERT INTO equipment_profiles
                    (vehicle_id, family_id, criticality, created_at, updated_at)
                SELECT vehicles.id, equipment_families.id, 'MEDIA', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                FROM vehicles
                JOIN equipment_families ON equipment_families.code = LOWER(vehicles.tipo)
                LEFT JOIN equipment_profiles ON equipment_profiles.vehicle_id = vehicles.id
                WHERE equipment_profiles.id IS NULL
                """
            )
        )


def downgrade():
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table_name in (
        'equipment_links',
        'equipment_profiles',
        'operational_locations',
        'equipment_families',
    ):
        if table_name in existing_tables:
            op.drop_table(table_name)

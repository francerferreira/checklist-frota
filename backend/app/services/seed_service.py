from __future__ import annotations

from flask import current_app

from app.extensions import db
from app.models import User, Vehicle, WashQueueItem
from app.services.checklist_catalog import seed_checklist_catalog_items
from app.services.availability_service import seed_operational_states
from app.services.equipment_structure_service import seed_equipment_structure
from app.services.inventory_import_service import discover_inventory_file, import_inventory_data
from app.services.wash_service import discover_wash_file, ensure_auxiliary_vehicles, sync_wash_queue


def seed_reference_data() -> None:
    _seed_initial_admin()

    db.session.commit()
    seed_equipment_structure()
    seed_checklist_catalog_items()

    if Vehicle.query.count() == 0:
        inventory_file = discover_inventory_file(current_app.config.get("INVENTORY_FILE"))
        if inventory_file:
            import_inventory_data(inventory_file)

    if not current_app.config.get("PORTUARY_ONLY_MODE"):
        wash_file = discover_wash_file(current_app.config.get("WASH_CONTROL_FILE"))
        ensure_auxiliary_vehicles(wash_file)
        if WashQueueItem.query.count() == 0:
            sync_wash_queue(wash_file)
    seed_operational_states()


def _seed_initial_admin() -> None:
    """Create an admin only when an explicit, strong bootstrap secret exists."""
    login = current_app.config.get("INITIAL_ADMIN_LOGIN", "")
    password = current_app.config.get("INITIAL_ADMIN_PASSWORD", "")
    if not login and not password:
        return
    if not login or not password:
        raise RuntimeError("INITIAL_ADMIN_LOGIN e INITIAL_ADMIN_PASSWORD devem ser informados juntos.")
    if len(password) < 12:
        raise RuntimeError("INITIAL_ADMIN_PASSWORD deve ter pelo menos 12 caracteres.")
    if User.query.filter_by(login=login).first():
        return

    admin = User(nome=current_app.config.get("INITIAL_ADMIN_NAME") or "Administrador", login=login, tipo="admin")
    admin.set_password(password)
    db.session.add(admin)

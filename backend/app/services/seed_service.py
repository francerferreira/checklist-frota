from __future__ import annotations

from flask import current_app

from app.extensions import db
from app.models import User, Vehicle, WashQueueItem
from app.services.checklist_catalog import seed_checklist_catalog_items
from app.services.inventory_import_service import discover_inventory_file, import_inventory_data
from app.services.wash_service import discover_wash_file, ensure_auxiliary_vehicles, sync_wash_queue


def seed_reference_data() -> None:
    if not User.query.filter_by(login="admin").first():
        admin = User(nome="Administrador", login="admin", tipo="admin")
        admin.set_password("123456")
        db.session.add(admin)

    if not User.query.filter_by(login="gestor").first():
        gestor = User(nome="Gestor Operacional", login="gestor", tipo="gestor")
        gestor.set_password("123456")
        db.session.add(gestor)

    if not User.query.filter_by(login="motorista").first():
        motorista = User(nome="Motorista Padrao", login="motorista", tipo="motorista")
        motorista.set_password("123456")
        db.session.add(motorista)

    if not User.query.filter_by(login="mecanico").first():
        mecanico = User(nome="Mecanico Padrao", login="mecanico", tipo="mecanico")
        mecanico.set_password("123456")
        db.session.add(mecanico)

    db.session.commit()
    seed_checklist_catalog_items()

    if Vehicle.query.count() == 0:
        inventory_file = discover_inventory_file(current_app.config.get("INVENTORY_FILE"))
        if inventory_file:
            import_inventory_data(inventory_file)

    wash_file = discover_wash_file(current_app.config.get("WASH_CONTROL_FILE"))
    ensure_auxiliary_vehicles(wash_file)
    if WashQueueItem.query.count() == 0:
        sync_wash_queue(wash_file)

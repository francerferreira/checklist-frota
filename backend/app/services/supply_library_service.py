from __future__ import annotations

from datetime import date
import secrets

from app.extensions import db
from app.models import (
    EquipmentFamily, MaintenanceMaterial, Material, MaterialFamilyApplication, TechnicalDocument,
    Vehicle, Warehouse, WarehouseLocation, WarehouseReservation, WarehouseStock, WarehouseTransfer, WarehouseTransferItem,
)
from app.services.audit_service import record_event
from app.utils.timezone import now_manaus_naive


DOCUMENT_TYPES = {"MANUAL", "PROCEDIMENTO", "DIAGRAMA", "CERTIFICADO", "OUTRO"}
DOCUMENT_STATUSES = {"ATIVO", "ARQUIVADO", "VENCIDO"}
WAREHOUSE_TYPES = {"PRINCIPAL", "MMP"}


def _clean(value) -> str | None:
    value = str(value or "").strip()
    return value or None


def _positive_int(value, field: str, *, allow_zero: bool = False) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} invalido.") from exc
    if number < 0 or (number == 0 and not allow_zero):
        raise ValueError(f"{field} deve ser maior que zero.")
    return number


def list_warehouses() -> list[dict]:
    return [row.to_dict() for row in Warehouse.query.order_by(Warehouse.warehouse_type.asc(), Warehouse.name.asc()).all()]


def create_warehouse(payload: dict) -> Warehouse:
    code, name = _clean(payload.get("code")), _clean(payload.get("name"))
    if not code or not name:
        raise ValueError("Informe código e nome do depósito.")
    if Warehouse.query.filter_by(code=code.upper()).first():
        raise ValueError("Já existe depósito com este código.")
    warehouse_type = str(payload.get("warehouse_type") or "PRINCIPAL").strip().upper()
    if warehouse_type not in WAREHOUSE_TYPES:
        raise ValueError("Tipo de estoque invalido. Use PRINCIPAL ou MMP.")
    row = Warehouse(code=code.upper(), name=name, location=_clean(payload.get("location")), warehouse_type=warehouse_type, active=bool(payload.get("active", True)))
    db.session.add(row); db.session.commit()
    return row


def update_warehouse(warehouse_id: int, payload: dict) -> Warehouse:
    row = db.session.get(Warehouse, warehouse_id)
    if not row:
        raise LookupError("Depósito não encontrado.")
    code, name = _clean(payload.get("code")), _clean(payload.get("name"))
    if not code or not name:
        raise ValueError("Informe código e nome do depósito.")
    duplicate = Warehouse.query.filter(Warehouse.code == code.upper(), Warehouse.id != row.id).first()
    if duplicate:
        raise ValueError("Já existe depósito com este código.")
    warehouse_type = str(payload.get("warehouse_type") or row.warehouse_type or "PRINCIPAL").strip().upper()
    if warehouse_type not in WAREHOUSE_TYPES:
        raise ValueError("Tipo de estoque invalido. Use PRINCIPAL ou MMP.")
    row.code, row.name, row.location, row.warehouse_type = code.upper(), name, _clean(payload.get("location")), warehouse_type
    row.active = bool(payload.get("active", row.active)); db.session.commit()
    return row


def list_warehouse_stocks(warehouse_id: int | None = None) -> list[dict]:
    query = WarehouseStock.query
    if warehouse_id:
        query = query.filter_by(warehouse_id=warehouse_id)
    return [row.to_dict() for row in query.order_by(WarehouseStock.updated_at.desc()).all()]


def list_mmp_stocks() -> list[dict]:
    return [
        row.to_dict()
        for row in WarehouseStock.query.join(Warehouse).filter(Warehouse.warehouse_type == "MMP", Warehouse.active.is_(True)).order_by(WarehouseStock.updated_at.desc()).all()
    ]


def list_warehouse_locations(warehouse_id: int | None = None) -> list[dict]:
    query = WarehouseLocation.query
    if warehouse_id:
        query = query.filter_by(warehouse_id=warehouse_id)
    return [row.to_dict() for row in query.order_by(WarehouseLocation.shelf_code.asc(), WarehouseLocation.location_code.asc(), WarehouseLocation.position_code.asc()).all()]


def create_warehouse_location(payload: dict) -> WarehouseLocation:
    warehouse_id = _positive_int(payload.get("warehouse_id"), "Depósito")
    warehouse = db.session.get(Warehouse, warehouse_id)
    if not warehouse or not warehouse.active:
        raise ValueError("Depósito ativo não encontrado.")
    shelf_code = _clean(payload.get("shelf_code"))
    location_code = _clean(payload.get("location_code"))
    position_code = _clean(payload.get("position_code"))
    if not shelf_code or not location_code or not position_code:
        raise ValueError("Informe prateleira, local e posição.")
    duplicate = WarehouseLocation.query.filter_by(warehouse_id=warehouse_id, shelf_code=shelf_code.upper(), location_code=location_code.upper(), position_code=position_code.upper()).first()
    if duplicate:
        raise ValueError("Este local já existe no depósito.")
    row = WarehouseLocation(warehouse_id=warehouse_id, shelf_code=shelf_code.upper(), location_code=location_code.upper(), position_code=position_code.upper(), active=bool(payload.get("active", True)))
    db.session.add(row); db.session.commit()
    return row


def update_warehouse_location(location_id: int, payload: dict) -> WarehouseLocation:
    row = db.session.get(WarehouseLocation, location_id)
    if not row:
        raise LookupError("Local não encontrado.")
    warehouse_id = _positive_int(payload.get("warehouse_id", row.warehouse_id), "Depósito")
    warehouse = db.session.get(Warehouse, warehouse_id)
    if not warehouse or not warehouse.active:
        raise ValueError("Depósito ativo não encontrado.")
    shelf_code = _clean(payload.get("shelf_code", row.shelf_code))
    location_code = _clean(payload.get("location_code", row.location_code))
    position_code = _clean(payload.get("position_code", row.position_code))
    if not shelf_code or not location_code or not position_code:
        raise ValueError("Informe prateleira, local e posição.")
    duplicate = WarehouseLocation.query.filter(
        WarehouseLocation.warehouse_id == warehouse_id,
        WarehouseLocation.shelf_code == shelf_code.upper(),
        WarehouseLocation.location_code == location_code.upper(),
        WarehouseLocation.position_code == position_code.upper(),
        WarehouseLocation.id != row.id,
    ).first()
    if duplicate:
        raise ValueError("Este local já existe no depósito.")
    row.warehouse_id = warehouse_id
    row.shelf_code = shelf_code.upper()
    row.location_code = location_code.upper()
    row.position_code = position_code.upper()
    row.active = bool(payload.get("active", row.active))
    db.session.commit()
    return row


def _warehouse_by_type(warehouse_type: str) -> Warehouse:
    row = Warehouse.query.filter_by(warehouse_type=warehouse_type, active=True).order_by(Warehouse.id.asc()).first()
    if not row:
        raise ValueError(f"Nenhum depósito ativo do tipo {warehouse_type} foi configurado.")
    return row


def create_warehouse_transfer(payload: dict, *, user_id: int) -> WarehouseTransfer:
    source_id = payload.get("source_warehouse_id")
    destination_id = payload.get("destination_warehouse_id")
    source = db.session.get(Warehouse, int(source_id)) if source_id else _warehouse_by_type("PRINCIPAL")
    destination = db.session.get(Warehouse, int(destination_id)) if destination_id else _warehouse_by_type("MMP")
    if not source or not destination or not source.active or not destination.active:
        raise ValueError("Depósito de origem ou destino não encontrado.")
    if source.warehouse_type != "PRINCIPAL" or destination.warehouse_type != "MMP":
        raise ValueError("A transferência deve sair do Armazém Principal e chegar ao Estoque MMP.")
    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        raise ValueError("Selecione pelo menos um material para transferir.")

    transfer = WarehouseTransfer(
        code=f"MMP-TRF-{now_manaus_naive().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2).upper()}",
        source_warehouse_id=source.id,
        destination_warehouse_id=destination.id,
        status="CONCLUIDA",
        notes=_clean(payload.get("notes")),
        created_by_user_id=user_id,
    )
    db.session.add(transfer)
    db.session.flush()

    for item_payload in items:
        material_id = _positive_int(item_payload.get("material_id"), "Material")
        quantity = _positive_int(item_payload.get("quantity"), "Quantidade")
        material = db.session.get(Material, material_id)
        source_stock = WarehouseStock.query.filter_by(warehouse_id=source.id, material_id=material_id).with_for_update().first()
        if not material or not material.ativo or not source_stock:
            raise ValueError("Material sem saldo cadastrado no Armazém Principal.")
        if source_stock.quantity - source_stock.reserved_quantity < quantity:
            raise ValueError(f"Saldo insuficiente no Armazém Principal para {material.referencia}.")
        location_id = _positive_int(item_payload.get("location_id"), "Local")
        location = db.session.get(WarehouseLocation, location_id)
        if not location or location.warehouse_id != destination.id or not location.active:
            raise ValueError("Local de destino inválido para o Estoque MMP.")
        destination_stock = WarehouseStock.query.filter_by(warehouse_id=destination.id, material_id=material_id).with_for_update().first()
        if destination_stock and destination_stock.location_id and destination_stock.location_id != location.id:
            raise ValueError(f"{material.referencia} já está em outro local do Estoque MMP.")
        if not destination_stock:
            destination_stock = WarehouseStock(warehouse_id=destination.id, material_id=material_id, quantity=0, location_id=location.id)
            db.session.add(destination_stock)
            db.session.flush()
        destination_stock.location_id = location.id
        source_stock.quantity -= quantity
        destination_stock.quantity += quantity
        transfer.items.append(WarehouseTransferItem(material_id=material_id, source_stock_id=source_stock.id, destination_stock_id=destination_stock.id, quantity=quantity, location_id=location.id))

    record_event(user_id=user_id, entity_type="WAREHOUSE_TRANSFER", entity_id=transfer.id, action="TRANSFER_TO_MMP", new_value=str({"module": "MATERIAIS_E_COMPRAS", "origin": "WEB", "transfer": transfer.to_dict()}))
    db.session.commit()
    return transfer


def list_warehouse_transfers(limit: int = 100) -> list[dict]:
    rows = WarehouseTransfer.query.order_by(WarehouseTransfer.created_at.desc()).limit(max(1, min(int(limit or 100), 500))).all()
    return [row.to_dict() for row in rows]


def lookup_mmp_qr(qr_code: str) -> dict:
    code = str(qr_code or "").strip().upper()
    prefix = "MMP-STOCK-"
    if not code.startswith(prefix):
        raise ValueError("QR Code de material MMP inválido.")
    try:
        stock_id = int(code.removeprefix(prefix))
    except ValueError as exc:
        raise ValueError("QR Code de material MMP inválido.") from exc
    stock = db.session.get(WarehouseStock, stock_id)
    if not stock or not stock.warehouse or stock.warehouse.warehouse_type != "MMP":
        raise LookupError("Material não encontrado no Estoque MMP.")
    return stock.to_dict()


def issue_mmp_stock(payload: dict, *, user_id: int) -> dict:
    from app.services.material_service import register_material_movement

    stock_data = lookup_mmp_qr(payload.get("qr_code"))
    stock = db.session.get(WarehouseStock, stock_data["id"])
    quantity = _positive_int(payload.get("quantity"), "Quantidade")
    vehicle_id = _positive_int(payload.get("vehicle_id"), "Equipamento")
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.ativo:
        raise ValueError("Equipamento ativo não encontrado.")
    application = _clean(payload.get("application"))
    if not application:
        raise ValueError("Informe a aplicação do material.")
    if stock.quantity - stock.reserved_quantity < quantity:
        raise ValueError("Saldo disponível insuficiente no Estoque MMP.")
    if not material_is_applicable_to_vehicle(stock.material, vehicle_id):
        raise ValueError("O material não está liberado para a família deste equipamento.")
    movement = register_material_movement(
        stock.material,
        quantity=quantity,
        movement_type="ATIVIDADE",
        delta=-quantity,
        observation=f"Saída do Estoque MMP para {vehicle.frota or vehicle.placa}: {application}",
        warehouse_stock_id=stock.id,
        vehicle_id=vehicle_id,
        application=application,
    )
    stock.quantity -= quantity
    record_event(user_id=user_id, entity_type="MMP_STOCK", entity_id=stock.id, action="APPLICATION_OUT", new_value=str({"module": "MATERIAIS_E_COMPRAS", "origin": "WEB", "material_id": stock.material_id, "quantity": quantity, "vehicle_id": vehicle_id, "application": application}))
    db.session.commit()
    return {"stock": stock.to_dict(), "movement": movement.to_dict(), "vehicle": vehicle.to_dict()}


def initialize_warehouse_stock(payload: dict) -> WarehouseStock:
    warehouse_id = _positive_int(payload.get("warehouse_id"), "Depósito")
    material_id = _positive_int(payload.get("material_id"), "Material")
    quantity = _positive_int(payload.get("quantity"), "Quantidade", allow_zero=True)
    warehouse, material = db.session.get(Warehouse, warehouse_id), db.session.get(Material, material_id)
    if not warehouse or not warehouse.active:
        raise ValueError("Depósito ativo não encontrado.")
    if not material or not material.ativo:
        raise ValueError("Material ativo não encontrado.")
    if WarehouseStock.query.filter_by(warehouse_id=warehouse_id, material_id=material_id).first():
        raise ValueError("Este material já possui saldo neste depósito.")
    assigned = sum(int(row.quantity or 0) for row in WarehouseStock.query.filter_by(material_id=material_id).all())
    if assigned + quantity > int(material.quantidade_estoque or 0):
        raise ValueError("A distribuição por depósitos não pode ultrapassar o saldo atual do material.")
    row = WarehouseStock(warehouse_id=warehouse_id, material_id=material_id, quantity=quantity)
    db.session.add(row); db.session.commit()
    return row


def adjust_warehouse_stock(stock_id: int, payload: dict, *, user_id: int) -> WarehouseStock:
    from app.services.material_service import register_material_movement

    stock = db.session.get(WarehouseStock, stock_id)
    if not stock:
        raise LookupError("Saldo de depósito não encontrado.")
    quantity = _positive_int(payload.get("quantity"), "Quantidade")
    movement_type = str(payload.get("movement_type") or "AJUSTE").upper()
    if movement_type not in {"ENTRADA", "SAIDA", "AJUSTE"}:
        raise ValueError("Tipo de movimentação inválido.")
    delta = quantity if movement_type == "ENTRADA" else -quantity
    if stock.quantity + delta < stock.reserved_quantity:
        raise ValueError("A saída deixaria o depósito abaixo da quantidade reservada.")
    register_material_movement(stock.material, quantity=quantity, movement_type=movement_type, delta=delta, observation=_clean(payload.get("observation")))
    stock.quantity += delta
    db.session.commit()
    return stock


def set_material_family_applications(material_id: int, payload: dict) -> list[dict]:
    material = db.session.get(Material, material_id)
    if not material:
        raise LookupError("Material não encontrado.")
    family_ids = sorted({int(value) for value in (payload.get("family_ids") or []) if str(value).strip()})
    families = EquipmentFamily.query.filter(EquipmentFamily.id.in_(family_ids)).all() if family_ids else []
    if len(families) != len(family_ids):
        raise ValueError("Uma ou mais famílias não foram encontradas.")
    existing = {row.family_id: row for row in material.family_applications}
    for row in material.family_applications:
        row.active = row.family_id in family_ids
    for family_id in family_ids:
        if family_id in existing:
            existing[family_id].active = True
        else:
            db.session.add(MaterialFamilyApplication(material_id=material.id, family_id=family_id, active=True))
    db.session.commit()
    return [row.to_dict() for row in MaterialFamilyApplication.query.filter_by(material_id=material.id, active=True).all()]


def material_is_applicable_to_vehicle(material: Material, vehicle_id: int) -> bool:
    applications = [row for row in material.family_applications if row.active]
    if not applications:
        return True
    vehicle = db.session.get(Vehicle, vehicle_id)
    family_id = vehicle.equipment_profile.family_id if vehicle and vehicle.equipment_profile else None
    return bool(family_id and any(row.family_id == family_id for row in applications))


def reserve_warehouse_material(payload: dict, *, user_id: int) -> WarehouseReservation:
    maintenance_material_id = _positive_int(payload.get("maintenance_material_id"), "Material da manutenção")
    stock_id = _positive_int(payload.get("warehouse_stock_id"), "Saldo do depósito")
    quantity = _positive_int(payload.get("quantity"), "Quantidade")
    link, stock = db.session.get(MaintenanceMaterial, maintenance_material_id), db.session.get(WarehouseStock, stock_id)
    if not link or not stock or stock.material_id != link.material_id:
        raise ValueError("Material e saldo do depósito não correspondem.")
    existing = WarehouseReservation.query.filter_by(maintenance_material_id=link.id).first()
    if existing and existing.status == "RESERVADA":
        raise ValueError("Já existe reserva ativa para este material de manutenção.")
    if quantity > stock.quantity - stock.reserved_quantity:
        raise ValueError("Saldo disponível insuficiente no depósito.")
    stock.reserved_quantity += quantity
    link.quantity_reserved = max(int(link.quantity_reserved or 0), quantity)
    link.status = "RESERVADO"
    reservation = existing or WarehouseReservation(maintenance_material_id=link.id, warehouse_stock_id=stock.id, quantity=quantity, created_by_user_id=user_id)
    if existing:
        existing.warehouse_stock_id, existing.quantity, existing.status, existing.created_by_user_id = stock.id, quantity, "RESERVADA", user_id
    else:
        db.session.add(reservation)
    db.session.commit()
    return reservation


def consume_warehouse_reservation(maintenance_material_id: int, quantity: int) -> None:
    reservation = WarehouseReservation.query.filter_by(maintenance_material_id=maintenance_material_id, status="RESERVADA").first()
    if not reservation:
        return
    stock = reservation.warehouse_stock
    remaining = int(reservation.quantity or 0) - int(reservation.consumed_quantity or 0)
    if quantity > remaining or not stock or stock.quantity < quantity or stock.reserved_quantity < quantity:
        raise ValueError("Reserva de depósito insuficiente para concluir a OS.")
    stock.quantity -= quantity; stock.reserved_quantity -= quantity; reservation.consumed_quantity += quantity
    if reservation.consumed_quantity >= reservation.quantity:
        reservation.status, reservation.consumed_at = "CONSUMIDA", now_manaus_naive()


def _parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Validade inválida.") from exc


def list_technical_documents(*, vehicle_id: int | None = None, include_archived: bool = False) -> list[dict]:
    query = TechnicalDocument.query
    if vehicle_id:
        vehicle = db.session.get(Vehicle, vehicle_id)
        if not vehicle:
            raise LookupError("Equipamento não encontrado.")
        family_id = vehicle.equipment_profile.family_id if vehicle.equipment_profile else None
        query = query.filter(db.or_(TechnicalDocument.vehicle_id == vehicle_id, TechnicalDocument.family_id == family_id))
    if not include_archived:
        query = query.filter(TechnicalDocument.status == "ATIVO")
    rows = query.order_by(TechnicalDocument.updated_at.desc()).all()
    today = date.today()
    return [{**row.to_dict(), "effective_status": "VENCIDO" if row.valid_until and row.valid_until < today else row.status} for row in rows]


def create_technical_document(payload: dict, user_id: int) -> TechnicalDocument:
    code, title, file_path = _clean(payload.get("code")), _clean(payload.get("title")), _clean(payload.get("file_path"))
    doc_type = str(payload.get("document_type") or "").upper()
    family_id, vehicle_id = payload.get("family_id"), payload.get("vehicle_id")
    if not code or not title or not file_path:
        raise ValueError("Informe código, título e arquivo do documento.")
    if doc_type not in DOCUMENT_TYPES:
        raise ValueError("Tipo de documento inválido.")
    if not family_id and not vehicle_id:
        raise ValueError("Vincule o documento a uma família ou equipamento.")
    if family_id and not db.session.get(EquipmentFamily, int(family_id)):
        raise ValueError("Família não encontrada.")
    if vehicle_id and not db.session.get(Vehicle, int(vehicle_id)):
        raise ValueError("Equipamento não encontrado.")
    row = TechnicalDocument(code=code.upper(), title=title, document_type=doc_type, revision=_clean(payload.get("revision")) or "1", status="ATIVO", file_path=file_path, description=_clean(payload.get("description")), family_id=int(family_id) if family_id else None, vehicle_id=int(vehicle_id) if vehicle_id else None, valid_until=_parse_date(payload.get("valid_until")), created_by_user_id=user_id)
    db.session.add(row); db.session.commit()
    return row


def update_technical_document(document_id: int, payload: dict) -> TechnicalDocument:
    row = db.session.get(TechnicalDocument, document_id)
    if not row:
        raise LookupError("Documento técnico não encontrado.")
    status = str(payload.get("status") or row.status).upper()
    if status not in DOCUMENT_STATUSES:
        raise ValueError("Status do documento inválido.")
    for field in ("title", "revision", "file_path", "description"):
        if field in payload:
            value = _clean(payload.get(field))
            if field in {"title", "revision", "file_path"} and not value:
                raise ValueError("Dados obrigatórios do documento não podem ficar vazios.")
            setattr(row, field, value)
    if "valid_until" in payload:
        row.valid_until = _parse_date(payload.get("valid_until"))
    row.status = status; db.session.commit()
    return row

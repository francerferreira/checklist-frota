from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
import os
from pathlib import Path
import re
import tempfile

from flask import Blueprint, current_app, g, request, send_file
from sqlalchemy import case, func, or_
from sqlalchemy import text as sa_text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import InvoicePurchaseOrderLink, MaintenanceMaterial, Material, PurchaseImportBatch, PurchaseInvoice, PurchaseInvoiceItem, PurchaseOrder, PurchaseOrderItem, PurchaseProcessEvent, PurchaseReceipt, PurchaseReportRun, PurchaseReportSchedule, PurchaseRequest, PurchaseRequestItem, PurchaseServiceCatalog, Supplier, User, Vehicle
from app.services.auth_service import auth_required, user_has_management_access
from app.services.audit_service import record_event
from app.services.material_service import register_material_movement
from app.services.purchase_import_service import import_purchase_workbook
from app.services.purchase_report_export_service import export_purchase_report_pdf, export_purchase_report_xlsx
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive


bp = Blueprint("purchases", __name__)
PRIORITIES = {"BAIXA", "MEDIA", "ALTA", "CRITICA"}


def _request_list_options():
    """Carrega as relações usadas pelos cartões sem repetir consultas por item."""
    return (
        joinedload(PurchaseRequest.material),
        joinedload(PurchaseRequest.supplier),
        selectinload(PurchaseRequest.items).joinedload(PurchaseRequestItem.material),
        selectinload(PurchaseRequest.items).joinedload(PurchaseRequestItem.service_catalog),
        selectinload(PurchaseRequest.items).selectinload(PurchaseRequestItem.order_links),
    )


def _order_list_options():
    """Mantém a lista de PCs leve; o histórico completo é carregado somente ao abrir o cartão."""
    return (
        joinedload(PurchaseOrder.supplier),
        selectinload(PurchaseOrder.items).joinedload(PurchaseOrderItem.request_item),
        selectinload(PurchaseOrder.invoice_links).joinedload(InvoicePurchaseOrderLink.invoice),
    )


def _clean(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _fts_entity_ids(search: str, entity_type: str) -> set[int] | None:
    """Consulta o índice FTS5 local; retorna None quando a base ainda não o possui."""
    if db.engine.dialect.name != "sqlite":
        return None
    tokens = re.findall(r"[0-9A-Za-zÀ-ÿ]+", str(search or "").lower())
    if not tokens:
        return set()
    match = " AND ".join(f'"{token}"*' for token in tokens)
    try:
        rows = db.session.execute(
            sa_text(
                "SELECT entity_id FROM purchase_search_fts "
                "WHERE entity_type = :entity_type AND purchase_search_fts MATCH :match"
            ),
            {"entity_type": entity_type, "match": match},
        )
    except OperationalError:
        return None
    return {int(row[0]) for row in rows}


def _postgres_fts_clause(column, search: str):
    if not db.engine.dialect.name.startswith("postgresql"):
        return None
    return func.to_tsvector("simple", func.coalesce(column, "")).op("@@")(
        func.plainto_tsquery("simple", search)
    )


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "sim", "yes", "on"}


def _positive_int(value, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} invalida.") from exc
    if number <= 0:
        raise ValueError(f"{field} deve ser maior que zero.")
    return number


def _positive_decimal(value, field: str) -> Decimal:
    try:
        number = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} invalida.") from exc
    if number <= 0:
        raise ValueError(f"{field} deve ser maior que zero.")
    return number


def _non_negative_decimal(value, field: str) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} invalido.") from exc
    if number < 0:
        raise ValueError(f"{field} nao pode ser negativo.")
    return number


def _parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Data prevista invalida.") from exc


def _normalize_request_items(payload: dict) -> list[dict]:
    """Normaliza o payload novo de itens e preserva o formato legado de uma SC."""
    raw_items = payload.get("items")
    if raw_items is None:
        raw_items = [{
            "item_type": "MATERIAL",
            "material_id": payload.get("material_id"),
            "quantity": payload.get("requested_quantity"),
            "unit_of_measure": payload.get("unit_of_measure"),
            "maintenance_material_id": payload.get("maintenance_material_id"),
        }]
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("Adicione pelo menos um item na solicitacao.")
    if len(raw_items) > 200:
        raise ValueError("A solicitacao pode ter no maximo 200 itens.")

    normalized = []
    for position, raw in enumerate(raw_items, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Item {position} invalido.")
        item_type = str(raw.get("item_type") or raw.get("type") or "MATERIAL").strip().upper()
        if item_type in {"SERVICE", "SERVICO", "SERVIÇO"}:
            item_type = "SERVICO"
        elif item_type != "MATERIAL":
            raise ValueError(f"Tipo do item {position} invalido.")
        quantity = _positive_int(raw.get("quantity", raw.get("quantity_requested")), f"Quantidade do item {position}")
        material = None
        service = None
        if item_type == "MATERIAL":
            material_id = _positive_int(raw.get("material_id"), f"Material do item {position}")
            material = db.session.get(Material, material_id)
            if not material or not material.ativo:
                raise ValueError(f"Material ativo do item {position} nao encontrado.")
            description = _clean(raw.get("description_raw")) or material.descricao
            product_code = _clean(raw.get("product_code_raw")) or material.referencia
        else:
            service_id = raw.get("service_catalog_id")
            if service_id not in (None, ""):
                service = db.session.get(PurchaseServiceCatalog, _positive_int(service_id, f"Servico do item {position}"))
                if not service or not service.active:
                    raise ValueError(f"Servico ativo do item {position} nao encontrado.")
            description = _clean(raw.get("description_raw")) or (service.service_name if service else None)
            if not description:
                raise ValueError(f"Informe a descricao do servico no item {position}.")
            product_code = _clean(raw.get("product_code_raw"))
        normalized.append({
            "line_number": position,
            "item_type": item_type,
            "material": material,
            "service": service,
            "product_code_raw": product_code,
            "description_raw": description,
            "brand_raw": _clean(raw.get("brand_raw")),
            "manual_reference_raw": _clean(raw.get("manual_reference_raw")),
            "manufacturer_part_number_raw": _clean(raw.get("manufacturer_part_number_raw")),
            "quantity_requested": quantity,
            "unit_of_measure": _clean(raw.get("unit_of_measure")) or "UN",
            "notes": _clean(raw.get("notes")),
        })
    return normalized


def _parse_money(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Valor da nota fiscal invalido.") from exc
    if amount < 0:
        raise ValueError("Valor da nota fiscal nao pode ser negativo.")
    return amount


def _guard_management():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar compras.", status_code=403)
    return None


def _guard_admin():
    if g.current_user.tipo != "admin":
        return api_response(False, error="Somente o administrador pode executar esta acao.", status_code=403)
    return None


def _run(action, *, status_code: int = 200):
    try:
        return api_response(True, data=action(), status_code=status_code)
    except LookupError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=404)
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)


@bp.get("/compras/provedores")
@bp.get("/compras/fornecedores")
@auth_required
def list_suppliers():
    denied = _guard_admin()
    if denied:
        return denied
    query = Supplier.query
    if search := _clean(request.args.get("q")):
        term = f"%{search}%"
        query = query.filter(or_(Supplier.code.ilike(term), Supplier.name.ilike(term), Supplier.legal_name.ilike(term), Supplier.trade_name.ilike(term)))
    if status := _clean(request.args.get("status")):
        query = query.filter(Supplier.active.is_(status.upper() == "ATIVO"))
    return api_response(True, data=[row.to_dict() for row in query.order_by(Supplier.active.desc(), Supplier.name.asc()).all()])


@bp.post("/compras/provedores")
@bp.post("/compras/fornecedores")
@auth_required
def create_supplier():
    denied = _guard_admin()
    if denied:
        return denied

    def action():
        payload = request.get_json(silent=True) or {}
        code, name = _clean(payload.get("code")), _clean(payload.get("name"))
        if not code or not name:
            raise ValueError("Informe codigo e nome do provedor.")
        if Supplier.query.filter_by(code=code.upper()).first():
            raise ValueError("Ja existe provedor com este codigo.")
        supplier = Supplier(
            code=code.upper(), name=name, legal_name=_clean(payload.get("legal_name")),
            trade_name=_clean(payload.get("trade_name")), tax_id=_clean(payload.get("tax_id")),
            contact_name=_clean(payload.get("contact_name")),
            email=_clean(payload.get("email")), phone=_clean(payload.get("phone")),
            notes=_clean(payload.get("notes")), active=_as_bool(payload.get("active"), True),
            homologated=_as_bool(payload.get("homologated")), preferred=_as_bool(payload.get("preferred")),
        )
        db.session.add(supplier)
        db.session.flush()
        record_event(user_id=g.current_user.id, entity_type="SUPPLIER", entity_id=supplier.id, action="CREATED", new_value=supplier.to_dict())
        db.session.commit()
        return supplier.to_dict()

    return _run(action, status_code=201)


@bp.put("/compras/provedores/<int:provider_id>")
@bp.put("/compras/fornecedores/<int:provider_id>")
@auth_required
def update_supplier(provider_id: int):
    denied = _guard_admin()
    if denied:
        return denied

    def action():
        supplier = db.session.get(Supplier, provider_id)
        if not supplier:
            raise LookupError("Provedor nao encontrado.")
        payload = request.get_json(silent=True) or {}
        code = _clean(payload.get("code", supplier.code))
        name = _clean(payload.get("name", supplier.name))
        if not code or not name:
            raise ValueError("Informe codigo e nome do provedor.")
        duplicate = Supplier.query.filter(Supplier.code == code.upper(), Supplier.id != supplier.id).first()
        if duplicate:
            raise ValueError("Ja existe provedor com este codigo.")
        supplier.code = code.upper()
        supplier.name = name
        supplier.legal_name = _clean(payload.get("legal_name"))
        supplier.trade_name = _clean(payload.get("trade_name"))
        supplier.tax_id = _clean(payload.get("tax_id"))
        supplier.contact_name = _clean(payload.get("contact_name"))
        supplier.email = _clean(payload.get("email"))
        supplier.phone = _clean(payload.get("phone"))
        supplier.notes = _clean(payload.get("notes"))
        supplier.active = _as_bool(payload.get("active"), supplier.active)
        supplier.homologated = _as_bool(payload.get("homologated"), supplier.homologated)
        supplier.preferred = _as_bool(payload.get("preferred"), supplier.preferred)
        record_event(user_id=g.current_user.id, entity_type="SUPPLIER", entity_id=supplier.id, action="UPDATED", new_value=supplier.to_dict())
        db.session.commit()
        return supplier.to_dict()

    return _run(action)


@bp.get("/compras/solicitacoes")
@auth_required
def list_purchase_requests():
    denied = _guard_management()
    if denied:
        return denied
    page_requested = "page" in request.args or "per_page" in request.args
    page = max(1, request.args.get("page", 1, type=int) or 1)
    per_page = min(100, max(1, request.args.get("per_page", 100, type=int) or 100))
    query = PurchaseRequest.query.options(*_request_list_options()).order_by(PurchaseRequest.created_at.desc())
    if str(request.args.get("modo") or "").strip().upper() == "OPERACIONAL":
        query = query.filter(~PurchaseRequest.status.in_({"RECEBIDA", "CANCELADA"}))
    search = _clean(request.args.get("q"))
    if search:
        term = f"%{search[:120]}%"
        search_clauses = [
            PurchaseRequest.code.ilike(term),
            PurchaseRequest.sc_number.ilike(term),
            PurchaseRequest.module.ilike(term),
            PurchaseRequest.requester_raw.ilike(term),
            PurchaseRequest.equipment_raw.ilike(term),
            PurchaseRequest.cost_center.ilike(term),
            PurchaseRequest.supplier.has(or_(Supplier.code.ilike(term), Supplier.name.ilike(term), Supplier.trade_name.ilike(term))),
        ]
        sqlite_fts = {entity: _fts_entity_ids(search, entity) for entity in ("REQUEST", "MATERIAL", "REQUEST_ITEM", "SERVICE", "SUPPLIER")}
        postgres_fts = [
            _postgres_fts_clause(Material.descricao, search),
            _postgres_fts_clause(PurchaseRequestItem.description_raw, search),
            _postgres_fts_clause(PurchaseServiceCatalog.service_name, search),
        ]
        if all(value is not None for value in sqlite_fts.values()):
            search_clauses.extend([
                PurchaseRequest.id.in_(sqlite_fts["REQUEST"]),
                PurchaseRequest.material_id.in_(sqlite_fts["MATERIAL"]),
                PurchaseRequest.items.any(PurchaseRequestItem.id.in_(sqlite_fts["REQUEST_ITEM"])),
                PurchaseRequest.items.any(PurchaseRequestItem.service_catalog_id.in_(sqlite_fts["SERVICE"])),
                PurchaseRequest.supplier_id.in_(sqlite_fts["SUPPLIER"]),
            ])
        elif not all(clause is not None for clause in postgres_fts):
            search_clauses.extend([
                PurchaseRequest.material.has(or_(Material.referencia.ilike(term), Material.descricao.ilike(term))),
                PurchaseRequest.items.any(or_(
                    PurchaseRequestItem.product_code_raw.ilike(term),
                    PurchaseRequestItem.description_raw.ilike(term),
                    PurchaseRequestItem.manual_reference_raw.ilike(term),
                    PurchaseRequestItem.material.has(or_(Material.referencia.ilike(term), Material.descricao.ilike(term))),
                    PurchaseRequestItem.service_catalog.has(or_(PurchaseServiceCatalog.code.ilike(term), PurchaseServiceCatalog.service_name.ilike(term))),
                )),
            ])
        search_clauses.extend(clause for clause in postgres_fts if clause is not None)
        query = query.filter(or_(*search_clauses))
    status_filter = str(request.args.get("status") or "TODOS").strip().upper()
    if status_filter and status_filter != "TODOS":
        query = query.filter(or_(
            PurchaseRequest.status == status_filter,
            PurchaseRequest.items.any(PurchaseRequestItem.status == status_filter),
        ))
    sort_key = str(request.args.get("sort") or "RECENTES").strip().upper()
    if sort_key == "PRIORIDADE":
        query = query.order_by(None).order_by(
            case(
                (PurchaseRequest.priority == "CRITICA", 0),
                (PurchaseRequest.priority == "ALTA", 1),
                (PurchaseRequest.priority == "MEDIA", 2),
                (PurchaseRequest.priority == "BAIXA", 3),
                else_=4,
            ),
            PurchaseRequest.created_at.desc(),
        )
    elif sort_key == "PROVEDOR_PREFERENCIAL":
        query = query.order_by(None).outerjoin(PurchaseRequest.supplier).order_by(
            Supplier.preferred.desc(),
            Supplier.name.asc(),
            PurchaseRequest.created_at.desc(),
        )
    if not page_requested:
        rows = query.all()
        return api_response(True, data=[row.to_dict() for row in rows])
    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    return api_response(True, data={
        "items": [row.to_dict() for row in rows],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        },
    })


@bp.get("/compras/indicadores")
@auth_required
def purchase_operational_indicators():
    """Resumo leve e canônico das etapas abertas do fluxo SC → PC → NF."""
    denied = _guard_management()
    if denied:
        return denied
    active_request = ~PurchaseRequest.status.in_({"RECEBIDA", "CANCELADA"})
    item_query = PurchaseRequestItem.query.join(PurchaseRequest).filter(active_request)
    open_requests = db.session.query(func.count(PurchaseRequest.id)).filter(active_request).scalar() or 0
    pending_pc_items = item_query.filter(PurchaseRequestItem.status.in_({"AGUARDANDO_PC", "PC_PARCIAL"})).count()
    pending_nf_items = item_query.filter(PurchaseRequestItem.status == "AGUARDANDO_NF").count()
    return api_response(True, data={
        "open_requests": int(open_requests),
        "pending_pc_items": int(pending_pc_items),
        "pending_nf_items": int(pending_nf_items),
    })


def _update_purchase_item_pc_status(request_item: PurchaseRequestItem) -> None:
    ordered = request_item.ordered_quantity
    requested = Decimal(request_item.quantity_requested or 0)
    if ordered <= 0:
        request_item.status = "AGUARDANDO_PC"
    elif ordered < requested:
        request_item.status = "PC_PARCIAL"
    else:
        request_item.status = "AGUARDANDO_NF"


def _refresh_request_pc_status(purchase: PurchaseRequest) -> None:
    if not purchase.items:
        return
    for request_item in purchase.items:
        _update_purchase_item_pc_status(request_item)
    if all(item.remaining_order_quantity <= 0 for item in purchase.items):
        purchase.status = "EM_TRANSITO"
    elif purchase.status not in {"CANCELADA", "RECEBIDA", "PARCIALMENTE_RECEBIDA"}:
        purchase.status = "APROVADA"


@bp.get("/compras/pedidos/pendentes")
@auth_required
def list_pending_purchase_order_items():
    denied = _guard_management()
    if denied:
        return denied
    pending = []
    requests = (
        PurchaseRequest.query.options(*_request_list_options())
        .filter(PurchaseRequest.status.in_({"APROVADA", "EM_TRANSITO"}))
        .order_by(PurchaseRequest.created_at.asc())
        .all()
    )
    for purchase in requests:
        items = [item.to_dict() for item in purchase.items if item.remaining_order_quantity > 0]
        if not items:
            continue
        pending.append({
            "purchase_request_id": purchase.id,
            "sc_number": purchase.sc_number or purchase.code,
            "sc_date": purchase.sc_date.isoformat() if purchase.sc_date else None,
            "status": purchase.status,
            "request_type": purchase.request_type,
            "module": purchase.module,
            "equipment_raw": purchase.equipment_raw,
            "requester_raw": purchase.requester_raw,
            "priority": purchase.priority,
            "items": items,
        })
    return api_response(True, data=pending)


@bp.get("/compras/pedidos")
@auth_required
def list_purchase_orders():
    denied = _guard_management()
    if denied:
        return denied
    page_requested = "page" in request.args or "per_page" in request.args or "q" in request.args
    page = max(1, request.args.get("page", 1, type=int) or 1)
    per_page = min(100, max(1, request.args.get("per_page", 100, type=int) or 100))
    search = _clean(request.args.get("q"))
    query = PurchaseOrder.query
    if search:
        query = query.filter(PurchaseOrder.pc_number.ilike(f"%{search}%"))
    total = query.count()
    rows = (
        query.options(*_order_list_options())
        .order_by(PurchaseOrder.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    data = [row.to_dict() for row in rows]
    if not page_requested:
        return api_response(True, data=data)
    return api_response(True, data={
        "items": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        },
    })


@bp.get("/compras/pedidos/<int:order_id>/historico")
@auth_required
def get_purchase_order_history(order_id: int):
    """Detalhe sob demanda de um PC, sem pesar o carregamento do quadro."""
    denied = _guard_management()
    if denied:
        return denied
    order = (
        PurchaseOrder.query.options(
            *_order_list_options(),
            selectinload(PurchaseOrder.items)
            .joinedload(PurchaseOrderItem.request_item)
            .joinedload(PurchaseRequestItem.purchase_request),
        )
        .filter(PurchaseOrder.id == order_id)
        .first()
    )
    if not order:
        return api_response(False, error="Pedido de compra nao encontrado.", status_code=404)

    order_item_ids = [item.id for item in order.items]
    invoice_items = []
    if order_item_ids:
        invoice_items = (
            PurchaseInvoiceItem.query.options(joinedload(PurchaseInvoiceItem.invoice))
            .filter(PurchaseInvoiceItem.purchase_order_item_id.in_(order_item_ids))
            .all()
        )
    invoice_items_by_order_item: dict[int, list[PurchaseInvoiceItem]] = {}
    for invoice_item in invoice_items:
        invoice_items_by_order_item.setdefault(invoice_item.purchase_order_item_id, []).append(invoice_item)

    item_history = []
    for order_item in order.items:
        request_item = order_item.request_item
        purchase = request_item.purchase_request if request_item else None
        related_invoices = invoice_items_by_order_item.get(order_item.id, [])
        item_history.append({
            "id": order_item.id,
            "sc_number": purchase.sc_number if purchase else None,
            "sc_status": purchase.status if purchase else None,
            "description": request_item.description_raw if request_item else None,
            "item_type": request_item.item_type if request_item else None,
            "quantity_ordered": float(order_item.quantity_ordered or 0),
            "quantity_invoiced": float(sum((Decimal(item.quantity_invoiced or 0) for item in related_invoices), Decimal("0"))),
            "quantity_received": float(sum((Decimal(item.quantity_received or 0) for item in related_invoices), Decimal("0"))),
            "invoices": [{
                "id": item.invoice.id if item.invoice else None,
                "number": item.invoice.invoice_number if item.invoice else None,
                "series": item.invoice.series if item.invoice else None,
                "status": item.invoice.status if item.invoice else None,
                "date": item.invoice.invoice_date.isoformat() if item.invoice and item.invoice.invoice_date else None,
                "quantity_invoiced": float(item.quantity_invoiced or 0),
                "quantity_received": float(item.quantity_received or 0),
            } for item in related_invoices],
        })

    invoice_ids = [link.invoice_id for link in order.invoice_links]
    events = PurchaseProcessEvent.query.filter(
        (PurchaseProcessEvent.entity_type == "PURCHASE_ORDER") & (PurchaseProcessEvent.entity_id == order.id)
        | ((PurchaseProcessEvent.entity_type == "PURCHASE_INVOICE") & PurchaseProcessEvent.entity_id.in_(invoice_ids or [-1]))
    ).order_by(PurchaseProcessEvent.timestamp.desc()).limit(50).all()
    return api_response(True, data={
        "order": order.to_dict(),
        "items": item_history,
        "events": [{
            "type": event.event_type,
            "old_status": event.old_status,
            "new_status": event.new_status,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "comment": event.comment,
        } for event in events],
    })


@bp.post("/compras/pedidos")
@auth_required
def create_purchase_order():
    denied = _guard_management()
    if denied:
        return denied

    def action():
        payload = request.get_json(silent=True) or {}
        pc_number = _clean(payload.get("pc_number"))
        if not pc_number:
            raise ValueError("Informe o numero do PC.")
        company_code = _clean(payload.get("company_code"))
        branch_code = _clean(payload.get("branch_code"))
        duplicate = PurchaseOrder.query.filter_by(pc_number=pc_number, company_code=company_code, branch_code=branch_code).first()
        if duplicate:
            raise ValueError("Ja existe um PC com este numero para esta empresa e filial.")
        raw_items = payload.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("Selecione pelo menos um item pendente da SC.")
        if len(raw_items) > 200:
            raise ValueError("O PC pode ter no maximo 200 itens.")

        supplier_id = payload.get("supplier_id")
        supplier = None
        if supplier_id not in (None, ""):
            supplier = db.session.get(Supplier, _positive_int(supplier_id, "Provedor"))
            if not supplier or not supplier.active:
                raise ValueError("Provedor ativo nao encontrado.")
        supplier_raw = _clean(payload.get("supplier_raw"))
        if not supplier and not supplier_raw:
            raise ValueError("Informe o provedor do PC.")

        buyer = g.current_user
        buyer_id = payload.get("buyer_id")
        if buyer_id not in (None, ""):
            buyer = db.session.get(User, _positive_int(buyer_id, "Comprador"))
            if not buyer or not buyer.ativo:
                raise ValueError("Comprador ativo nao encontrado.")
        default_delivery_date = _parse_date(payload.get("delivery_due_date"))
        order_items = []
        affected_requests = {}
        for position, raw in enumerate(raw_items, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"Item {position} invalido.")
            request_item_id = _positive_int(raw.get("purchase_request_item_id"), f"Item da SC {position}")
            request_item = db.session.get(PurchaseRequestItem, request_item_id)
            if not request_item:
                raise LookupError(f"Item da SC {position} nao encontrado.")
            purchase = request_item.purchase_request
            if purchase.status not in {"APROVADA", "EM_TRANSITO"}:
                raise ValueError(f"A SC {purchase.sc_number or purchase.code} precisa estar aprovada antes do PC.")
            remaining = request_item.remaining_order_quantity
            quantity = _positive_decimal(raw.get("quantity_ordered", raw.get("quantity")), f"Quantidade do item {position}")
            if quantity > remaining:
                raise ValueError(f"Quantidade do item {position} excede o saldo pendente da SC.")
            unit_price = _non_negative_decimal(raw.get("unit_price"), f"Preco unitario do item {position}")
            total_price = _non_negative_decimal(raw.get("total_price"), f"Total do item {position}")
            if total_price is None and unit_price is not None:
                total_price = (quantity * unit_price).quantize(Decimal("0.01"))
            expected_delivery_date = _parse_date(raw.get("expected_delivery_date")) or default_delivery_date
            order_items.append({
                "request_item": request_item,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "expected_delivery_date": expected_delivery_date,
            })
            affected_requests[purchase.id] = purchase

        order = PurchaseOrder(
            pc_number=pc_number, pc_date=_parse_date(payload.get("pc_date")) or date.today(),
            buyer_id=buyer.id, buyer_raw=buyer.nome, supplier_id=supplier.id if supplier else None,
            supplier_raw=supplier_raw or (supplier.name if supplier else None),
            delivery_due_date=default_delivery_date, total_value=_non_negative_decimal(payload.get("total_value"), "Valor total do PC"),
            payment_terms=_clean(payload.get("payment_terms")), notes=_clean(payload.get("notes")),
            status="EMITIDO", company_code=company_code, branch_code=branch_code,
            created_by_user_id=g.current_user.id,
        )
        db.session.add(order)
        db.session.flush()
        for item_data in order_items:
            db.session.add(PurchaseOrderItem(
                purchase_order_id=order.id,
                purchase_request_item_id=item_data["request_item"].id,
                request_item=item_data["request_item"],
                quantity_ordered=item_data["quantity"],
                unit_price=item_data["unit_price"],
                total_price=item_data["total_price"],
                expected_delivery_date=item_data["expected_delivery_date"],
                status="EMITIDO",
            ))
        db.session.flush()
        for purchase in affected_requests.values():
            _refresh_request_pc_status(purchase)
        db.session.add(PurchaseProcessEvent(
            entity_type="PURCHASE_ORDER", entity_id=order.id, event_type="PC_EMITIDO",
            new_status="EMITIDO", actor_id=g.current_user.id,
            event_metadata={"purchase_request_ids": list(affected_requests), "item_count": len(order_items)},
        ))
        db.session.commit()
        return {"purchase_order": order.to_dict(), "purchase_request_ids": list(affected_requests)}

    return _run(action, status_code=201)


def _invoice_quantities(order_item: PurchaseOrderItem) -> tuple[Decimal, Decimal]:
    rows = PurchaseInvoiceItem.query.filter_by(purchase_order_item_id=order_item.id).all()
    invoiced = sum((Decimal(row.quantity_invoiced or 0) for row in rows), Decimal("0"))
    received = sum((Decimal(row.quantity_received or 0) for row in rows), Decimal("0"))
    return invoiced, received


def _invoice_item_summary(invoice_item: PurchaseInvoiceItem) -> dict:
    order_item = invoice_item.purchase_order_item
    request_item = order_item.request_item if order_item else None
    quantity_invoiced = Decimal(invoice_item.quantity_invoiced or 0)
    quantity_received = Decimal(invoice_item.quantity_received or 0)
    return {
        "id": invoice_item.id,
        "invoice_id": invoice_item.invoice_id,
        "purchase_order_item_id": invoice_item.purchase_order_item_id,
        "purchase_order_id": order_item.purchase_order_id if order_item else None,
        "pc_number": order_item.purchase_order.pc_number if order_item and order_item.purchase_order else None,
        "purchase_request_item_id": request_item.id if request_item else None,
        "sc_number": request_item.purchase_request.sc_number if request_item and request_item.purchase_request else None,
        "item_type": request_item.item_type if request_item else None,
        "description_raw": request_item.description_raw if request_item else None,
        "material": request_item.material.to_dict() if request_item and request_item.material else None,
        "quantity_ordered": float(order_item.quantity_ordered) if order_item else 0,
        "quantity_invoiced": float(quantity_invoiced),
        "remaining_invoice_quantity": float(max(Decimal("0"), Decimal(order_item.quantity_ordered or 0) - quantity_invoiced)) if order_item else 0,
        "quantity_received": float(quantity_received),
        "remaining_receipt_quantity": float(max(Decimal("0"), quantity_invoiced - quantity_received)),
        "status": invoice_item.invoice.status if invoice_item.invoice else None,
    }


def _refresh_request_invoice_status(purchase: PurchaseRequest) -> None:
    if not purchase.items:
        return
    for request_item in purchase.items:
        ordered = request_item.ordered_quantity
        requested = Decimal(request_item.quantity_requested or 0)
        invoiced = sum((_invoice_quantities(order_link)[0] for order_link in request_item.order_links), Decimal("0"))
        received = Decimal(request_item.quantity_received or 0)
        if received >= requested:
            request_item.status = "RECEBIDA"
        elif received > 0:
            request_item.status = "PARCIALMENTE_RECEBIDA"
        elif ordered < requested:
            request_item.status = "PC_PARCIAL" if ordered > 0 else "AGUARDANDO_PC"
        elif invoiced < ordered:
            request_item.status = "AGUARDANDO_NF"
        else:
            request_item.status = "AGUARDANDO_RECEBIMENTO"
    if all(Decimal(item.quantity_received or 0) >= Decimal(item.quantity_requested or 0) for item in purchase.items):
        purchase.status = "RECEBIDA"
    elif any(Decimal(item.quantity_received or 0) > 0 for item in purchase.items):
        purchase.status = "PARCIALMENTE_RECEBIDA"
    elif all(item.remaining_order_quantity <= 0 for item in purchase.items):
        purchase.status = "EM_TRANSITO"


@bp.get("/compras/notas/pendentes")
@auth_required
def list_pending_purchase_invoices():
    denied = _guard_management()
    if denied:
        return denied
    page_requested = "page" in request.args or "per_page" in request.args
    page = max(1, request.args.get("page", 1, type=int) or 1)
    per_page = min(100, max(1, request.args.get("per_page", 100, type=int) or 100))
    search = _clean(request.args.get("q"))
    status_filter = str(request.args.get("status") or "TODOS").strip().upper()
    term = f"%{search[:120]}%" if search else None
    pending_nf = []
    invoiced_by_order_item = (
        db.session.query(
            PurchaseInvoiceItem.purchase_order_item_id.label("purchase_order_item_id"),
            func.coalesce(func.sum(PurchaseInvoiceItem.quantity_invoiced), 0).label("quantity_invoiced"),
        )
        .group_by(PurchaseInvoiceItem.purchase_order_item_id)
        .subquery()
    )
    orders_query = None
    if status_filter in {"TODOS", "AGUARDANDO_NF"}:
        orders_query = (
            PurchaseOrder.query
            .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .join(PurchaseRequestItem, PurchaseRequestItem.id == PurchaseOrderItem.purchase_request_item_id)
            .outerjoin(PurchaseRequest, PurchaseRequest.id == PurchaseRequestItem.purchase_request_id)
            .outerjoin(Material, Material.id == PurchaseRequestItem.material_id)
            .outerjoin(PurchaseServiceCatalog, PurchaseServiceCatalog.id == PurchaseRequestItem.service_catalog_id)
            .outerjoin(invoiced_by_order_item, invoiced_by_order_item.c.purchase_order_item_id == PurchaseOrderItem.id)
            .group_by(PurchaseOrder.id)
            .having(func.sum(PurchaseOrderItem.quantity_ordered - func.coalesce(invoiced_by_order_item.c.quantity_invoiced, 0)) > 0)
            .order_by(PurchaseOrder.created_at.desc())
        )
        if term:
            search_clauses = [
                PurchaseOrder.pc_number.ilike(term),
                PurchaseOrder.supplier_raw.ilike(term),
                PurchaseRequest.sc_number.ilike(term),
                PurchaseRequest.requester_raw.ilike(term),
                PurchaseRequestItem.product_code_raw.ilike(term),
            ]
            sqlite_fts = {entity: _fts_entity_ids(search, entity) for entity in ("PC", "MATERIAL", "REQUEST", "REQUEST_ITEM", "SERVICE", "SUPPLIER")}
            postgres_fts = [
                _postgres_fts_clause(Material.descricao, search),
                _postgres_fts_clause(PurchaseRequestItem.description_raw, search),
                _postgres_fts_clause(PurchaseServiceCatalog.service_name, search),
            ]
            if all(value is not None for value in sqlite_fts.values()):
                search_clauses.extend([
                    PurchaseOrder.id.in_(sqlite_fts["PC"]),
                    PurchaseRequest.id.in_(sqlite_fts["REQUEST"]),
                    PurchaseRequestItem.id.in_(sqlite_fts["REQUEST_ITEM"]),
                    PurchaseRequestItem.material_id.in_(sqlite_fts["MATERIAL"]),
                    PurchaseRequestItem.service_catalog_id.in_(sqlite_fts["SERVICE"]),
                    PurchaseOrder.supplier_id.in_(sqlite_fts["SUPPLIER"]),
                ])
            elif not all(clause is not None for clause in postgres_fts):
                search_clauses.extend([
                    PurchaseRequestItem.description_raw.ilike(term),
                    Material.referencia.ilike(term),
                    Material.descricao.ilike(term),
                    PurchaseServiceCatalog.code.ilike(term),
                    PurchaseServiceCatalog.service_name.ilike(term),
                ])
            search_clauses.extend(clause for clause in postgres_fts if clause is not None)
            orders_query = orders_query.filter(or_(*search_clauses))
    total_pending_nf = orders_query.count() if orders_query is not None else 0
    orders = orders_query.offset((page - 1) * per_page).limit(per_page).all() if page_requested and orders_query is not None else (orders_query.all() if orders_query is not None else [])
    for order in orders:
        pending_items = []
        for order_item in order.items:
            invoiced, received = _invoice_quantities(order_item)
            remaining = Decimal(order_item.quantity_ordered or 0) - invoiced
            if remaining > 0:
                item = order_item.request_item
                pending_items.append({
                    "purchase_order_item_id": order_item.id,
                    "purchase_request_item_id": item.id if item else None,
                    "item_type": item.item_type if item else None,
                    "description_raw": item.description_raw if item else None,
                    "material": item.material.to_dict() if item and item.material else None,
                    "quantity_ordered": float(order_item.quantity_ordered or 0),
                    "quantity_invoiced": float(invoiced),
                    "remaining_invoice_quantity": float(remaining),
                    "quantity_received": float(received),
                    "sc_number": item.purchase_request.sc_number if item and item.purchase_request else None,
                })
        if pending_items:
            pending_nf.append({
                "purchase_order_id": order.id,
                "pc_number": order.pc_number,
                "pc_date": order.pc_date.isoformat() if order.pc_date else None,
                "supplier_id": order.supplier_id,
                "supplier_raw": order.supplier_raw or (order.supplier.name if order.supplier else None),
                "total_value": float(order.total_value) if order.total_value is not None else None,
                "status": order.status,
                "items": pending_items,
            })
    pending_receipts = []
    receipt_query = None
    if status_filter in {"TODOS", "AGUARDANDO_RECEBIMENTO"}:
        receipt_query = (
            PurchaseInvoiceItem.query
            .join(PurchaseInvoice, PurchaseInvoice.id == PurchaseInvoiceItem.invoice_id)
            .join(PurchaseOrderItem, PurchaseOrderItem.id == PurchaseInvoiceItem.purchase_order_item_id)
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
            .join(PurchaseRequestItem, PurchaseRequestItem.id == PurchaseOrderItem.purchase_request_item_id)
            .outerjoin(PurchaseRequest, PurchaseRequest.id == PurchaseRequestItem.purchase_request_id)
            .outerjoin(Material, Material.id == PurchaseRequestItem.material_id)
            .outerjoin(PurchaseServiceCatalog, PurchaseServiceCatalog.id == PurchaseRequestItem.service_catalog_id)
            .filter(func.coalesce(PurchaseInvoiceItem.quantity_received, 0) < func.coalesce(PurchaseInvoiceItem.quantity_invoiced, 0))
            .order_by(PurchaseInvoiceItem.id.desc())
        )
        if term:
            search_clauses = [
                PurchaseInvoice.invoice_number.ilike(term),
                PurchaseInvoice.series.ilike(term),
                PurchaseInvoice.supplier_raw.ilike(term),
                PurchaseOrder.pc_number.ilike(term),
                PurchaseOrder.supplier_raw.ilike(term),
                PurchaseRequest.sc_number.ilike(term),
                PurchaseRequestItem.product_code_raw.ilike(term),
            ]
            sqlite_fts = {entity: _fts_entity_ids(search, entity) for entity in ("NF", "PC", "MATERIAL", "REQUEST", "REQUEST_ITEM", "SERVICE", "SUPPLIER")}
            postgres_fts = [
                _postgres_fts_clause(Material.descricao, search),
                _postgres_fts_clause(PurchaseRequestItem.description_raw, search),
                _postgres_fts_clause(PurchaseServiceCatalog.service_name, search),
            ]
            if all(value is not None for value in sqlite_fts.values()):
                search_clauses.extend([
                    PurchaseInvoice.id.in_(sqlite_fts["NF"]),
                    PurchaseOrder.id.in_(sqlite_fts["PC"]),
                    PurchaseRequest.id.in_(sqlite_fts["REQUEST"]),
                    PurchaseRequestItem.id.in_(sqlite_fts["REQUEST_ITEM"]),
                    PurchaseRequestItem.material_id.in_(sqlite_fts["MATERIAL"]),
                    PurchaseRequestItem.service_catalog_id.in_(sqlite_fts["SERVICE"]),
                    PurchaseInvoice.supplier_id.in_(sqlite_fts["SUPPLIER"]),
                ])
            elif not all(clause is not None for clause in postgres_fts):
                search_clauses.extend([
                    PurchaseRequestItem.description_raw.ilike(term),
                    Material.referencia.ilike(term),
                    Material.descricao.ilike(term),
                    PurchaseServiceCatalog.code.ilike(term),
                    PurchaseServiceCatalog.service_name.ilike(term),
                ])
            search_clauses.extend(clause for clause in postgres_fts if clause is not None)
            receipt_query = receipt_query.filter(or_(*search_clauses))
    total_pending_receipts = receipt_query.count() if receipt_query is not None else 0
    invoice_items = receipt_query.offset((page - 1) * per_page).limit(per_page).all() if page_requested and receipt_query is not None else (receipt_query.all() if receipt_query is not None else [])
    for invoice_item in invoice_items:
        summary = _invoice_item_summary(invoice_item)
        if summary["remaining_receipt_quantity"] > 0:
            invoice = invoice_item.invoice
            summary.update({
                "invoice_number": invoice.invoice_number if invoice else None,
                "invoice_series": invoice.series if invoice else None,
                "invoice_date": invoice.invoice_date.isoformat() if invoice and invoice.invoice_date else None,
                "invoice_value": float(invoice.invoice_value) if invoice and invoice.invoice_value is not None else None,
            })
            pending_receipts.append(summary)
    if not page_requested:
        return api_response(True, data={"pending_nf": pending_nf, "pending_receipts": pending_receipts})
    return api_response(True, data={
        "pending_nf": pending_nf,
        "pending_receipts": pending_receipts,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "pending_nf": {"total": total_pending_nf, "total_pages": max(1, (total_pending_nf + per_page - 1) // per_page)},
            "pending_receipts": {"total": total_pending_receipts, "total_pages": max(1, (total_pending_receipts + per_page - 1) // per_page)},
        },
    })


@bp.post("/compras/notas")
@auth_required
def create_purchase_invoice():
    denied = _guard_management()
    if denied:
        return denied

    def action():
        payload = request.get_json(silent=True) or {}
        purchase_order_id = _positive_int(payload.get("purchase_order_id"), "PC")
        order = db.session.get(PurchaseOrder, purchase_order_id)
        if not order:
            raise LookupError("Pedido de compra nao encontrado.")
        invoice_number = _clean(payload.get("invoice_number"))
        if not invoice_number:
            raise ValueError("Informe o numero da NF.")
        series = _clean(payload.get("series"))
        supplier_id = order.supplier_id
        supplier = order.supplier
        duplicate = PurchaseInvoice.query.filter(
            PurchaseInvoice.invoice_number == invoice_number,
            PurchaseInvoice.series == series,
            PurchaseInvoice.supplier_id == supplier_id,
        ).first()
        if duplicate:
            raise ValueError("Ja existe uma NF com este numero, serie e provedor.")
        raw_items = payload.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("Selecione pelo menos um item do PC para a NF.")
        selected = []
        seen = set()
        for position, raw in enumerate(raw_items, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"Item da NF {position} invalido.")
            order_item_id = _positive_int(raw.get("purchase_order_item_id"), f"Item da NF {position}")
            if order_item_id in seen:
                raise ValueError("Nao repita itens na mesma NF.")
            seen.add(order_item_id)
            order_item = db.session.get(PurchaseOrderItem, order_item_id)
            if not order_item or order_item.purchase_order_id != order.id:
                raise ValueError(f"Item da NF {position} nao pertence ao PC selecionado.")
            invoiced, _ = _invoice_quantities(order_item)
            remaining = Decimal(order_item.quantity_ordered or 0) - invoiced
            quantity = _positive_decimal(raw.get("quantity_invoiced", raw.get("quantity")), f"Quantidade faturada do item {position}")
            if quantity > remaining:
                raise ValueError(f"Quantidade faturada do item {position} excede o saldo do PC.")
            selected.append((order_item, quantity))
        invoice = PurchaseInvoice(
            invoice_number=invoice_number, series=series, access_key=_clean(payload.get("access_key")),
            supplier_id=supplier_id, supplier_raw=order.supplier_raw or (supplier.name if supplier else None),
            invoice_date=_parse_date(payload.get("invoice_date")) or date.today(),
            invoice_value=_parse_money(payload.get("invoice_value")), status="AGUARDANDO_RECEBIMENTO",
            notes=_clean(payload.get("notes")), file_path=_clean(payload.get("file_path")),
        )
        db.session.add(invoice)
        db.session.flush()
        db.session.add(InvoicePurchaseOrderLink(invoice_id=invoice.id, purchase_order_id=order.id, linked_value=invoice.invoice_value))
        affected_requests = {}
        for order_item, quantity in selected:
            db.session.add(PurchaseInvoiceItem(invoice_id=invoice.id, purchase_order_item_id=order_item.id, quantity_invoiced=quantity))
            affected_requests[order_item.request_item.purchase_request.id] = order_item.request_item.purchase_request
        db.session.flush()
        order.status = "AGUARDANDO_RECEBIMENTO" if all(_invoice_quantities(item)[0] >= Decimal(item.quantity_ordered or 0) for item in order.items) else "NF_PARCIAL"
        for purchase in affected_requests.values():
            _refresh_request_invoice_status(purchase)
        db.session.add(PurchaseProcessEvent(
            entity_type="PURCHASE_INVOICE", entity_id=invoice.id, event_type="NF_REGISTRADA",
            new_status=invoice.status, actor_id=g.current_user.id,
            event_metadata={"purchase_order_id": order.id, "item_count": len(selected)},
        ))
        db.session.commit()
        return {"invoice": invoice.to_dict(), "purchase_order_id": order.id}

    return _run(action, status_code=201)


@bp.post("/compras/notas/<int:invoice_id>/recebimentos")
@auth_required
def receive_purchase_invoice_item(invoice_id: int):
    denied = _guard_management()
    if denied:
        return denied

    def action():
        payload = request.get_json(silent=True) or {}
        key = _clean(payload.get("idempotency_key"))
        if not key:
            raise ValueError("Informe a chave de idempotencia do recebimento.")
        existing = PurchaseReceipt.query.filter_by(idempotency_key=key).first()
        if existing:
            return {"invoice": existing.purchase_invoice.to_dict() if existing.purchase_invoice else None, "receipt": existing.to_dict()}
        invoice = db.session.get(PurchaseInvoice, invoice_id)
        if not invoice:
            raise LookupError("Nota fiscal nao encontrada.")
        invoice_item_id = _positive_int(payload.get("invoice_item_id"), "Item da NF")
        invoice_item = db.session.get(PurchaseInvoiceItem, invoice_item_id)
        if not invoice_item or invoice_item.invoice_id != invoice.id:
            raise ValueError("Item nao pertence a esta NF.")
        quantity = _positive_int(payload.get("quantity_received"), "Quantidade recebida")
        remaining = Decimal(invoice_item.quantity_invoiced or 0) - Decimal(invoice_item.quantity_received or 0)
        if Decimal(quantity) > remaining:
            raise ValueError("Quantidade recebida excede o saldo da NF.")
        order_item = invoice_item.purchase_order_item
        request_item = order_item.request_item
        purchase = request_item.purchase_request
        receipt = PurchaseReceipt(
            purchase_request_id=purchase.id, quantity=quantity, idempotency_key=key,
            received_by_user_id=g.current_user.id, notes=_clean(payload.get("notes")),
            invoice_number=invoice.invoice_number, invoice_series=invoice.series,
            invoice_date=invoice.invoice_date, invoice_value=invoice.invoice_value,
            invoice_file_path=invoice.file_path, purchase_invoice_id=invoice.id,
            purchase_order_item_id=order_item.id,
        )
        if request_item.item_type == "MATERIAL":
            if not request_item.material:
                raise ValueError("Material do item nao encontrado para entrada no estoque.")
            register_material_movement(
                request_item.material, quantity=quantity, movement_type="ENTRADA", delta=quantity,
                observation=f"Recebimento da NF {invoice.invoice_number} do PC {order_item.purchase_order.pc_number}",
            )
        invoice_item.quantity_received += quantity
        invoice_item.received_at = now_manaus_naive()
        invoice_item.receiver_id = g.current_user.id
        request_item.quantity_received += quantity
        purchase.received_quantity += quantity
        db.session.add(receipt)
        db.session.flush()
        _refresh_request_invoice_status(purchase)
        invoice.status = "RECEBIDA" if all(Decimal(item.quantity_received or 0) >= Decimal(item.quantity_invoiced or 0) for item in invoice.items) else "RECEBIMENTO_PARCIAL"
        if invoice.status == "RECEBIDA":
            invoice.received_at = now_manaus_naive()
            invoice.received_by_user_id = g.current_user.id
            invoice.received_by_raw = g.current_user.nome
        order = order_item.purchase_order
        order_invoice_items = [
            invoice_item
            for order_item in order.items
            for invoice_item in PurchaseInvoiceItem.query.filter_by(purchase_order_item_id=order_item.id).all()
        ]
        if order_invoice_items and all(Decimal(item.quantity_received or 0) >= Decimal(item.quantity_invoiced or 0) for item in order_invoice_items):
            order.status = "RECEBIDA"
        db.session.add(PurchaseProcessEvent(
            entity_type="PURCHASE_INVOICE", entity_id=invoice.id, event_type="RECEBIMENTO_REGISTRADO",
            new_status=invoice.status, actor_id=g.current_user.id,
            event_metadata={"invoice_item_id": invoice_item.id, "quantity_received": quantity},
        ))
        db.session.commit()
        return {"invoice": invoice.to_dict(), "receipt": receipt.to_dict(), "purchase_request": purchase.to_dict()}

    return _run(action)


def _central_process_item_summary(item: PurchaseRequestItem) -> dict:
    purchase = item.purchase_request
    requested = Decimal(item.quantity_requested or 0)
    ordered = item.ordered_quantity
    invoiced = Decimal("0")
    received = Decimal(item.quantity_received or 0)
    purchase_orders = []
    for order_item in item.order_links:
        order_invoiced, _ = _invoice_quantities(order_item)
        invoiced += order_invoiced
        invoices = PurchaseInvoiceItem.query.filter_by(purchase_order_item_id=order_item.id).all()
        purchase_orders.append({
            "id": order_item.purchase_order_id,
            "pc_number": order_item.purchase_order.pc_number if order_item.purchase_order else None,
            "supplier_raw": order_item.purchase_order.supplier_raw if order_item.purchase_order else None,
            "quantity_ordered": float(order_item.quantity_ordered or 0),
            "quantity_invoiced": float(order_invoiced),
            "quantity_received": float(sum((Decimal(invoice_item.quantity_received or 0) for invoice_item in invoices), Decimal("0"))),
            "invoices": [
                {
                    "id": invoice_item.invoice_id,
                    "invoice_number": invoice_item.invoice.invoice_number if invoice_item.invoice else None,
                    "series": invoice_item.invoice.series if invoice_item.invoice else None,
                    "status": invoice_item.invoice.status if invoice_item.invoice else None,
                }
                for invoice_item in invoices
            ],
        })
    if received >= requested:
        status = "RECEBIDA"
        next_action = "CONCLUIDO"
    elif received > 0:
        status = "PARCIALMENTE_RECEBIDA"
        next_action = "RECEBER_SALDO"
    elif ordered < requested:
        status = "PC_PARCIAL" if ordered > 0 else "AGUARDANDO_PC"
        next_action = "EMITIR_PC"
    elif invoiced < ordered:
        status = "AGUARDANDO_NF"
        next_action = "REGISTRAR_NF"
    else:
        status = "AGUARDANDO_RECEBIMENTO"
        next_action = "RECEBER_MATERIAL"
    return {
        "id": item.id,
        "purchase_request_id": purchase.id if purchase else None,
        "sc_number": purchase.sc_number or purchase.code if purchase else None,
        "sc_date": purchase.sc_date.isoformat() if purchase and purchase.sc_date else None,
        "request_status": purchase.status if purchase else None,
        "item_status": status,
        "next_action": next_action,
        "item_type": item.item_type,
        "description_raw": item.description_raw,
        "product_code_raw": item.product_code_raw,
        "material": item.material.to_dict() if item.material else None,
        "module": purchase.module if purchase else None,
        "equipment_raw": purchase.equipment_raw if purchase else None,
        "requester_raw": purchase.requester_raw if purchase else None,
        "priority": purchase.priority if purchase else None,
        "cost_center": purchase.cost_center if purchase else None,
        "requested_quantity": float(requested),
        "ordered_quantity": float(ordered),
        "invoiced_quantity": float(invoiced),
        "received_quantity": float(received),
        "remaining_quantity": float(max(Decimal("0"), requested - received)),
        "updated_at": item.updated_at.isoformat() if item.updated_at else (purchase.updated_at.isoformat() if purchase and purchase.updated_at else None),
        "purchase_orders": purchase_orders,
    }


@bp.get("/compras/central-processos")
@auth_required
def purchase_process_center():
    denied = _guard_management()
    if denied:
        return denied
    status_filter = _clean(request.args.get("status"))
    type_filter = _clean(request.args.get("item_type"))
    search = (_clean(request.args.get("q")) or "").lower()
    page = max(1, request.args.get("page", 1, type=int) or 1)
    per_page = min(100, max(1, request.args.get("per_page", 100, type=int) or 100))
    try:
        date_from = _parse_date(request.args.get("date_from"))
        date_to = _parse_date(request.args.get("date_to"))
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    if date_from and date_to and date_from > date_to:
        return api_response(False, error="O período inicial não pode ser maior que o final.", status_code=400)
    # Preserva a mesma janela operacional já usada pela Central (500 SCs mais recentes),
    # mas entrega somente os 100 itens mais recentes para a tela.
    recent_request_ids = [
        row[0]
        for row in db.session.query(PurchaseRequest.id)
        .order_by(PurchaseRequest.created_at.desc())
        .limit(500)
        .all()
    ]
    query = PurchaseRequestItem.query.join(PurchaseRequest).filter(PurchaseRequest.id.in_(recent_request_ids))
    if date_from:
        query = query.filter(PurchaseRequest.sc_date >= date_from)
    if date_to:
        query = query.filter(PurchaseRequest.sc_date <= date_to)
    if status_filter:
        query = query.filter(PurchaseRequestItem.status == status_filter.upper())
    if type_filter:
        query = query.filter(PurchaseRequestItem.item_type == type_filter.upper())
    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            PurchaseRequest.sc_number.ilike(like),
            PurchaseRequest.code.ilike(like),
            PurchaseRequestItem.description_raw.ilike(like),
            PurchaseRequestItem.product_code_raw.ilike(like),
            PurchaseRequest.module.ilike(like),
            PurchaseRequest.equipment_raw.ilike(like),
            PurchaseRequest.requester_raw.ilike(like),
        ))
    total_items = query.count()
    items = (
        query.options(
            joinedload(PurchaseRequestItem.purchase_request),
            joinedload(PurchaseRequestItem.material),
            joinedload(PurchaseRequestItem.service_catalog),
            selectinload(PurchaseRequestItem.order_links).joinedload(PurchaseOrderItem.purchase_order),
        )
        .order_by(PurchaseRequestItem.updated_at.desc(), PurchaseRequestItem.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    rows = [_central_process_item_summary(item) for item in items]
    status_counts = {}
    type_counts = {}
    for row in rows:
        status_counts[row["item_status"]] = status_counts.get(row["item_status"], 0) + 1
        type_counts[row["item_type"]] = type_counts.get(row["item_type"], 0) + 1
    return api_response(True, data={
        "summary": {
            "items": len(rows),
            "total_items": total_items,
            "display_limit": per_page,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (total_items + per_page - 1) // per_page),
            "processes": len({row["purchase_request_id"] for row in rows}),
            "status_counts": status_counts,
            "type_counts": type_counts,
            "pending_pc": sum(1 for row in rows if row["item_status"] in {"AGUARDANDO_PC", "PC_PARCIAL"}),
            "pending_nf": sum(1 for row in rows if row["item_status"] == "AGUARDANDO_NF"),
            "pending_receipt": sum(1 for row in rows if row["item_status"] == "AGUARDANDO_RECEBIMENTO"),
        },
        "items": rows,
    })


def _build_purchase_report_data(date_from: date | None = None, date_to: date | None = None) -> dict:
    rows = []
    for purchase in PurchaseRequest.query.order_by(PurchaseRequest.created_at.desc()).limit(500).all():
        reference_date = purchase.sc_date or (purchase.created_at.date() if purchase.created_at else None)
        if date_from and (not reference_date or reference_date < date_from):
            continue
        if date_to and (not reference_date or reference_date > date_to):
            continue
        rows.extend(_central_process_item_summary(item) for item in purchase.items)
    by_status = {}
    by_type = {}
    by_module = {}
    by_provider = {}
    for row in rows:
        by_status[row["item_status"]] = by_status.get(row["item_status"], 0) + 1
        type_bucket = by_type.setdefault(row["item_type"] or "NAO_INFORMADO", {"items": 0, "requested": 0, "received": 0})
        type_bucket["items"] += 1
        type_bucket["requested"] += row["requested_quantity"]
        type_bucket["received"] += row["received_quantity"]
        module = row["module"] or "NAO_INFORMADO"
        by_module[module] = by_module.get(module, 0) + 1
        for order in row["purchase_orders"]:
            provider = order["supplier_raw"] or "NAO INFORMADO"
            by_provider[provider] = by_provider.get(provider, 0) + 1
    return {
        "summary": {
            "processes": len({row["purchase_request_id"] for row in rows}),
            "items": len(rows),
            "requested_quantity": sum(row["requested_quantity"] for row in rows),
            "ordered_quantity": sum(row["ordered_quantity"] for row in rows),
            "invoiced_quantity": sum(row["invoiced_quantity"] for row in rows),
            "received_quantity": sum(row["received_quantity"] for row in rows),
            "remaining_quantity": sum(row["remaining_quantity"] for row in rows),
        },
        "by_status": by_status,
        "by_type": by_type,
        "by_module": by_module,
        "by_provider": by_provider,
        "items": rows,
    }


@bp.get("/compras/relatorios/resumo")
@auth_required
def purchase_report_summary():
    denied = _guard_management()
    if denied:
        return denied
    try:
        date_from = _parse_date(request.args.get("date_from"))
        date_to = _parse_date(request.args.get("date_to"))
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    if date_from and date_to and date_from > date_to:
        return api_response(False, error="O período inicial não pode ser maior que o final.", status_code=400)
    rows = []
    for purchase in PurchaseRequest.query.order_by(PurchaseRequest.created_at.desc()).limit(500).all():
        reference_date = purchase.sc_date or (purchase.created_at.date() if purchase.created_at else None)
        if date_from and (not reference_date or reference_date < date_from):
            continue
        if date_to and (not reference_date or reference_date > date_to):
            continue
        rows.extend(_central_process_item_summary(item) for item in purchase.items)
    by_status = {}
    by_type = {}
    by_module = {}
    by_provider = {}
    for row in rows:
        by_status[row["item_status"]] = by_status.get(row["item_status"], 0) + 1
        type_bucket = by_type.setdefault(row["item_type"] or "NAO_INFORMADO", {"items": 0, "requested": 0, "received": 0})
        type_bucket["items"] += 1
        type_bucket["requested"] += row["requested_quantity"]
        type_bucket["received"] += row["received_quantity"]
        module = row["module"] or "NAO_INFORMADO"
        by_module[module] = by_module.get(module, 0) + 1
        for order in row["purchase_orders"]:
            provider = order["supplier_raw"] or "NAO INFORMADO"
            by_provider[provider] = by_provider.get(provider, 0) + 1
    return api_response(True, data={
        "summary": {
            "processes": len({row["purchase_request_id"] for row in rows}),
            "items": len(rows),
            "requested_quantity": sum(row["requested_quantity"] for row in rows),
            "ordered_quantity": sum(row["ordered_quantity"] for row in rows),
            "invoiced_quantity": sum(row["invoiced_quantity"] for row in rows),
            "received_quantity": sum(row["received_quantity"] for row in rows),
            "remaining_quantity": sum(row["remaining_quantity"] for row in rows),
        },
        "by_status": by_status,
        "by_type": by_type,
        "by_module": by_module,
        "by_provider": by_provider,
        "items": rows,
    })


def _report_datetime(value) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise ValueError("Informe uma data e hora validas para o agendamento.") from exc


def _report_file_path(filename: str) -> Path:
    root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    target = (root / "relatorios" / "compras" / filename).resolve()
    if root not in target.parents:
        raise ValueError("Caminho de relatorio invalido.")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _generate_purchase_report_file(data: dict, export_format: str, filename: str, generated_by: str) -> Path:
    path = _report_file_path(filename)
    if export_format == "PDF":
        return export_purchase_report_pdf(data, path, generated_by=generated_by)
    return export_purchase_report_xlsx(data, path, generated_by=generated_by)


@bp.get("/compras/relatorios/exportar")
@auth_required
def export_purchase_report():
    denied = _guard_management()
    if denied:
        return denied
    export_format = str(request.args.get("formato") or request.args.get("format") or "XLSX").strip().upper()
    if export_format not in {"PDF", "XLSX"}:
        return api_response(False, error="Formato invalido. Use PDF ou XLSX.", status_code=400)
    try:
        date_from = _parse_date(request.args.get("date_from"))
        date_to = _parse_date(request.args.get("date_to"))
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    if date_from and date_to and date_from > date_to:
        return api_response(False, error="O periodo inicial nao pode ser maior que o final.", status_code=400)
    data = _build_purchase_report_data(date_from, date_to)
    data["period_label"] = f"{date_from.isoformat() if date_from else 'inicio'} a {date_to.isoformat() if date_to else 'hoje'}"
    suffix = "pdf" if export_format == "PDF" else "xlsx"
    filename = f"relatorio_compras_{date_from.isoformat() if date_from else 'inicio'}_{date_to.isoformat() if date_to else 'hoje'}.{suffix}"
    tmp = tempfile.NamedTemporaryFile(prefix="compras_export_", suffix=f".{suffix}", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        if export_format == "PDF":
            export_purchase_report_pdf(data, tmp_path, generated_by=g.current_user.nome or g.current_user.login)
            mimetype = "application/pdf"
        else:
            export_purchase_report_xlsx(data, tmp_path, generated_by=g.current_user.nome or g.current_user.login)
            mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        content = BytesIO(tmp_path.read_bytes())
        content.seek(0)
    finally:
        tmp_path.unlink(missing_ok=True)
    return send_file(content, mimetype=mimetype, as_attachment=True, download_name=filename)


@bp.get("/compras/relatorios/automaticos")
@auth_required
def list_purchase_report_schedules():
    denied = _guard_admin()
    if denied:
        return denied
    schedules = PurchaseReportSchedule.query.order_by(PurchaseReportSchedule.active.desc(), PurchaseReportSchedule.next_run_at.asc()).all()
    return api_response(True, data=[schedule.to_dict() for schedule in schedules])


@bp.post("/compras/relatorios/automaticos")
@auth_required
def create_purchase_report_schedule():
    denied = _guard_admin()
    if denied:
        return denied

    def action():
        payload = request.get_json(silent=True) or {}
        name = _clean(payload.get("name"))
        frequency = str(payload.get("frequency") or "MONTHLY").strip().upper()
        export_format = str(payload.get("export_format") or payload.get("format") or "XLSX").strip().upper()
        if not name:
            raise ValueError("Informe o nome do relatorio automatico.")
        if frequency not in {"WEEKLY", "MONTHLY"}:
            raise ValueError("Frequencia invalida. Use WEEKLY ou MONTHLY.")
        if export_format not in {"PDF", "XLSX"}:
            raise ValueError("Formato invalido. Use PDF ou XLSX.")
        period_days = _positive_int(payload.get("period_days") or (7 if frequency == "WEEKLY" else 30), "Periodo")
        if period_days > 366:
            raise ValueError("O periodo automatico nao pode ultrapassar 366 dias.")
        next_run_at = _report_datetime(payload.get("next_run_at")) or (now_manaus_naive() + timedelta(days=1))
        schedule = PurchaseReportSchedule(name=name, frequency=frequency, period_days=period_days, export_format=export_format, filter_status=_clean(payload.get("filter_status")), filter_item_type=_clean(payload.get("filter_item_type")), next_run_at=next_run_at, active=bool(payload.get("active", True)), created_by_user_id=g.current_user.id)
        db.session.add(schedule)
        db.session.commit()
        return schedule.to_dict()
    return _run(action, status_code=201)


@bp.put("/compras/relatorios/automaticos/<int:schedule_id>")
@auth_required
def update_purchase_report_schedule(schedule_id: int):
    denied = _guard_admin()
    if denied:
        return denied

    def action():
        schedule = db.session.get(PurchaseReportSchedule, schedule_id)
        if not schedule:
            raise LookupError("Agendamento de relatorio nao encontrado.")
        payload = request.get_json(silent=True) or {}
        if "name" in payload:
            schedule.name = _clean(payload.get("name")) or schedule.name
        if "active" in payload:
            schedule.active = bool(payload.get("active"))
        if "next_run_at" in payload:
            schedule.next_run_at = _report_datetime(payload.get("next_run_at")) or schedule.next_run_at
        db.session.commit()
        return schedule.to_dict()
    return _run(action)


@bp.delete("/compras/relatorios/automaticos/<int:schedule_id>")
@auth_required
def delete_purchase_report_schedule(schedule_id: int):
    denied = _guard_admin()
    if denied:
        return denied
    schedule = db.session.get(PurchaseReportSchedule, schedule_id)
    if not schedule:
        return api_response(False, error="Agendamento de relatorio nao encontrado.", status_code=404)
    schedule.active = False
    db.session.commit()
    return api_response(True, data=schedule.to_dict())


@bp.post("/compras/relatorios/automaticos/executar")
@auth_required
def execute_purchase_report_schedules():
    denied = _guard_admin()
    if denied:
        return denied
    requested_id = request.args.get("schedule_id", type=int)
    now = now_manaus_naive()
    query = PurchaseReportSchedule.query.filter_by(active=True)
    if requested_id:
        query = query.filter_by(id=requested_id)
    else:
        query = query.filter(PurchaseReportSchedule.next_run_at <= now)
    schedules = query.order_by(PurchaseReportSchedule.next_run_at.asc()).all()
    runs = []
    for schedule in schedules:
        period_to = date.today() - timedelta(days=1)
        period_from = period_to - timedelta(days=max(schedule.period_days, 1) - 1)
        run = PurchaseReportRun(schedule_id=schedule.id, export_format=schedule.export_format, period_from=period_from, period_to=period_to, status="PROCESSANDO", started_at=now, created_by_user_id=g.current_user.id)
        db.session.add(run)
        db.session.flush()
        try:
            data = _build_purchase_report_data(period_from, period_to)
            data["period_label"] = f"{period_from.isoformat()} a {period_to.isoformat()}"
            suffix = "pdf" if schedule.export_format == "PDF" else "xlsx"
            filename = f"compras_automatico_{schedule.id}_{period_to.isoformat()}.{suffix}"
            path = _generate_purchase_report_file(data, schedule.export_format, filename, g.current_user.nome or g.current_user.login)
            run.filename = filename
            run.file_path = str(path)
            run.status = "CONCLUIDO"
            run.finished_at = now_manaus_naive()
            schedule.last_run_at = run.finished_at
            schedule.next_run_at = schedule.next_run_at + timedelta(days=7 if schedule.frequency == "WEEKLY" else 30)
            runs.append(run.to_dict())
        except Exception as exc:
            run.status = "ERRO"
            run.error_message = str(exc)
            run.finished_at = now_manaus_naive()
            runs.append(run.to_dict())
    db.session.commit()
    return api_response(True, data={"executed": len(runs), "runs": runs})


@bp.get("/compras/relatorios/automaticos/runs/<int:run_id>/download")
@auth_required
def download_purchase_report_run(run_id: int):
    denied = _guard_management()
    if denied:
        return denied
    run = db.session.get(PurchaseReportRun, run_id)
    if not run or run.status != "CONCLUIDO" or not run.file_path:
        return api_response(False, error="Arquivo do relatorio nao encontrado.", status_code=404)
    root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    path = Path(run.file_path).resolve()
    if root not in path.parents or not path.is_file():
        return api_response(False, error="Arquivo do relatorio nao esta disponivel.", status_code=404)
    mimetype = "application/pdf" if run.export_format == "PDF" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return send_file(path, mimetype=mimetype, as_attachment=True, download_name=run.filename or path.name)


@bp.get("/compras/solicitacoes/<int:purchase_id>")
@auth_required
def get_purchase_request(purchase_id: int):
    denied = _guard_management()
    if denied:
        return denied
    row = db.session.get(PurchaseRequest, purchase_id)
    if not row:
        return api_response(False, error="Solicitacao de compra nao encontrada.", status_code=404)
    data = row.to_dict()
    data["created_at"] = row.created_at.isoformat() if row.created_at else None
    data["approved_at"] = row.approved_at.isoformat() if row.approved_at else None
    data["created_by"] = row.created_by.to_dict() if row.created_by else None
    data["approved_by"] = row.approved_by.to_dict() if row.approved_by else None
    data["receipts"] = [
        {**receipt.to_dict(), "received_by": receipt.received_by.to_dict() if receipt.received_by else None}
        for receipt in sorted(row.receipts, key=lambda item: (item.received_at, item.id), reverse=True)
    ]
    return api_response(True, data=data)


@bp.post("/compras/solicitacoes")
@auth_required
def create_purchase_request():
    denied = _guard_management()
    if denied:
        return denied

    def action():
        payload = request.get_json(silent=True) or {}
        items = _normalize_request_items(payload)
        first_material = next((item["material"] for item in items if item["material"]), None)
        supplier_id = payload.get("supplier_id")
        supplier = None
        if supplier_id not in (None, ""):
            supplier = db.session.get(Supplier, _positive_int(supplier_id, "Provedor"))
            if not supplier or not supplier.active:
                raise ValueError("Provedor ativo nao encontrado.")
        link_id = payload.get("maintenance_material_id")
        link = None
        if link_id not in (None, ""):
            link = db.session.get(MaintenanceMaterial, _positive_int(link_id, "Material de manutencao"))
            if not link or not first_material or link.material_id != first_material.id or len(items) != 1:
                raise ValueError("Vinculo de manutencao invalido para este material.")
        priority = str(payload.get("priority") or "MEDIA").strip().upper()
        if priority not in PRIORITIES:
            raise ValueError("Prioridade invalida.")
        equipment_id = payload.get("equipment_id")
        equipment = None
        if equipment_id not in (None, ""):
            equipment = db.session.get(Vehicle, _positive_int(equipment_id, "Equipamento"))
            if not equipment:
                raise ValueError("Equipamento nao encontrado.")
        item_types = {item["item_type"] for item in items}
        request_type = "MISTO" if len(item_types) > 1 else next(iter(item_types))
        requested_quantity = sum(item["quantity_requested"] for item in items)
        requester_id = payload.get("requester_id")
        requester = g.current_user
        if requester_id not in (None, ""):
            requester = db.session.get(User, _positive_int(requester_id, "Solicitante"))
            if not requester or not requester.ativo:
                raise ValueError("Solicitante ativo nao encontrado.")
        purchase = PurchaseRequest(
            code="SC-PEND", material_id=first_material.id if first_material else None, supplier_id=supplier.id if supplier else None,
            maintenance_material_id=link.id if link else None,
            requested_quantity=requested_quantity,
            priority=priority, expected_date=_parse_date(payload.get("expected_date")),
            observation=_clean(payload.get("observation")), created_by_user_id=g.current_user.id,
            company_code=_clean(payload.get("company_code")), branch_code=_clean(payload.get("branch_code")),
            sc_date=_parse_date(payload.get("sc_date")) or date.today(),
            requester_id=requester.id, requester_raw=_clean(payload.get("requester_raw")) or requester.nome,
            request_type=request_type, module=_clean(payload.get("module")),
            equipment_id=equipment.id if equipment else None, equipment_raw=_clean(payload.get("equipment_raw")),
            work_order_number=_clean(payload.get("work_order_number")),
            cost_center=_clean(payload.get("cost_center")),
            justification=_clean(payload.get("justification")) or _clean(payload.get("observation")),
            external_quote_number=_clean(payload.get("external_quote_number")),
        )
        db.session.add(purchase)
        db.session.flush()
        purchase.code = f"SC-{purchase.id:06d}"
        purchase.sc_number = purchase.code
        for item_data in items:
            item = PurchaseRequestItem(
                purchase_request_id=purchase.id,
                line_number=item_data["line_number"],
                item_type=item_data["item_type"],
                material_id=item_data["material"].id if item_data["material"] else None,
                service_catalog_id=item_data["service"].id if item_data["service"] else None,
                product_code_raw=item_data["product_code_raw"],
                description_raw=item_data["description_raw"],
                brand_raw=item_data["brand_raw"],
                manual_reference_raw=item_data["manual_reference_raw"],
                manufacturer_part_number_raw=item_data["manufacturer_part_number_raw"],
                quantity_requested=item_data["quantity_requested"],
                unit_of_measure=item_data["unit_of_measure"],
                notes=item_data["notes"],
            )
            db.session.add(item)
        if link:
            link.status = "EM_COMPRAS"
        db.session.commit()
        return purchase.to_dict()

    return _run(action, status_code=201)


@bp.post("/compras/solicitacoes/<int:purchase_id>/aprovar")
@auth_required
def approve_purchase_request(purchase_id: int):
    denied = _guard_admin()
    if denied:
        return denied

    def action():
        purchase = db.session.get(PurchaseRequest, purchase_id)
        if not purchase:
            raise LookupError("Solicitacao de compra nao encontrada.")
        if purchase.status != "SOLICITADA":
            raise ValueError("Somente solicitacoes pendentes podem ser aprovadas.")
        purchase.status = "APROVADA"
        purchase.approved_by_user_id = g.current_user.id
        purchase.approved_at = now_manaus_naive()
        db.session.commit()
        return purchase.to_dict()

    return _run(action)


@bp.post("/compras/solicitacoes/<int:purchase_id>/recebimentos")
@auth_required
def receive_purchase_request(purchase_id: int):
    denied = _guard_management()
    if denied:
        return denied

    def action():
        payload = request.get_json(silent=True) or {}
        key = _clean(payload.get("idempotency_key"))
        if not key:
            raise ValueError("Informe a chave de idempotencia do recebimento.")
        existing = PurchaseReceipt.query.filter_by(idempotency_key=key).first()
        if existing:
            if existing.purchase_request_id != purchase_id:
                raise ValueError("Chave de idempotencia ja usada em outra solicitacao.")
            return existing.purchase_request.to_dict()
        purchase = db.session.get(PurchaseRequest, purchase_id)
        if not purchase:
            raise LookupError("Solicitacao de compra nao encontrada.")
        if purchase.status not in {"APROVADA", "EM_TRANSITO", "PARCIALMENTE_RECEBIDA"}:
            raise ValueError("A solicitacao precisa estar aprovada antes do recebimento.")
        if purchase.items and (len(purchase.items) != 1 or purchase.items[0].item_type != "MATERIAL"):
            raise ValueError("O recebimento por item sera habilitado na etapa de NF.")
        quantity = _positive_int(payload.get("quantity"), "Quantidade recebida")
        if quantity > purchase.requested_quantity - purchase.received_quantity:
            raise ValueError("Quantidade recebida excede o saldo da solicitacao.")
        invoice_number = _clean(payload.get("invoice_number"))
        invoice_series = _clean(payload.get("invoice_series"))
        invoice_date = _parse_date(payload.get("invoice_date"))
        invoice_value = _parse_money(payload.get("invoice_value"))
        invoice_file_path = _clean(payload.get("invoice_file_path"))
        receipt = PurchaseReceipt(
            purchase_request_id=purchase.id, quantity=quantity, idempotency_key=key,
            received_by_user_id=g.current_user.id, notes=_clean(payload.get("notes")),
            invoice_number=invoice_number, invoice_series=invoice_series,
            invoice_date=invoice_date, invoice_value=invoice_value,
            invoice_file_path=invoice_file_path,
        )
        register_material_movement(
            purchase.material, quantity=quantity, movement_type="ENTRADA", delta=quantity,
            observation=f"Recebimento da compra {purchase.code}",
        )
        purchase.received_quantity += quantity
        purchase.status = "RECEBIDA" if purchase.received_quantity == purchase.requested_quantity else "PARCIALMENTE_RECEBIDA"
        if purchase.items:
            request_item = purchase.items[0]
            request_item.quantity_received += quantity
            request_item.status = "RECEBIDA" if request_item.quantity_received == request_item.quantity_requested else "PARCIALMENTE_RECEBIDA"
        db.session.add(receipt)
        db.session.commit()
        return purchase.to_dict()

    return _run(action)


@bp.get("/compras/importacoes")
@auth_required
def list_purchase_imports():
    denied = _guard_admin()
    if denied:
        return denied
    rows = PurchaseImportBatch.query.order_by(PurchaseImportBatch.started_at.desc()).limit(50).all()
    return api_response(True, data=[row.to_dict() for row in rows])


@bp.post("/compras/importacoes")
@auth_required
def import_purchase_source():
    denied = _guard_admin()
    if denied:
        return denied

    temporary_path = None
    try:
        upload = request.files.get("file")
        if upload and upload.filename:
            suffix = os.path.splitext(upload.filename)[1] or ".xlsx"
            handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            temporary_path = handle.name
            upload.save(temporary_path)
            handle.close()
            source_path = temporary_path
        else:
            payload = request.get_json(silent=True) or {}
            source_path = payload.get("source_path")
            if not source_path:
                return api_response(False, error="Envie o arquivo Excel no campo file ou informe source_path.", status_code=400)
        result = import_purchase_workbook(source_path, user_id=g.current_user.id)
        return api_response(True, data=result, status_code=201 if result.get("status") == "CONCLUIDO" else 200)
    except FileNotFoundError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=404)
    except (ValueError, OSError) as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass


@bp.get("/compras/materiais/<int:material_id>/historico")
@auth_required
def material_purchase_history(material_id: int):
    denied = _guard_management()
    if denied:
        return denied
    material = db.session.get(Material, material_id)
    if not material:
        return api_response(False, error="Material nao encontrado.", status_code=404)
    items = PurchaseRequestItem.query.filter_by(material_id=material_id).order_by(PurchaseRequestItem.created_at.desc()).all()
    request_dates = [item.purchase_request.sc_date for item in items if item.purchase_request and item.purchase_request.sc_date]
    requested = sum((item.quantity_requested or 0 for item in items), 0)
    received = sum((item.quantity_received or 0 for item in items), 0)
    return api_response(True, data={
        "material": material.to_dict(),
        "summary": {
            "first_request": min(request_dates).isoformat() if request_dates else None,
            "last_request": max(request_dates).isoformat() if request_dates else None,
            "requested_quantity": float(requested),
            "received_quantity": float(received),
            "open_quantity": float(requested - received),
            "purchase_requests": len({item.purchase_request_id for item in items}),
        },
        "items": [
            {
                **item.to_dict(),
                "purchase_request": {
                    "id": item.purchase_request.id,
                    "sc_number": item.purchase_request.sc_number or item.purchase_request.code,
                    "sc_date": item.purchase_request.sc_date.isoformat() if item.purchase_request.sc_date else None,
                    "status": item.purchase_request.status,
                    "module": item.purchase_request.module,
                } if item.purchase_request else None,
            }
            for item in items
        ],
    })

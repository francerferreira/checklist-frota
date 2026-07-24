from __future__ import annotations

from datetime import date

from flask import Blueprint, g, request

from app.extensions import db
from app.models import MaintenanceMaterial, Material, PurchaseReceipt, PurchaseRequest, Supplier
from app.services.auth_service import auth_required, user_has_management_access
from app.services.material_service import register_material_movement
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive


bp = Blueprint("purchases", __name__)
PRIORITIES = {"BAIXA", "MEDIA", "ALTA", "CRITICA"}


def _clean(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _positive_int(value, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} invalida.") from exc
    if number <= 0:
        raise ValueError(f"{field} deve ser maior que zero.")
    return number


def _parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Data prevista invalida.") from exc


def _guard_management():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar compras.", status_code=403)
    return None


def _guard_admin():
    if g.current_user.tipo != "admin":
        return api_response(False, error="Somente o administrador pode aprovar solicitações.", status_code=403)
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


@bp.get("/compras/fornecedores")
@auth_required
def list_suppliers():
    denied = _guard_management()
    if denied:
        return denied
    return api_response(True, data=[row.to_dict() for row in Supplier.query.order_by(Supplier.active.desc(), Supplier.name.asc()).all()])


@bp.post("/compras/fornecedores")
@auth_required
def create_supplier():
    denied = _guard_management()
    if denied:
        return denied

    def action():
        payload = request.get_json(silent=True) or {}
        code, name = _clean(payload.get("code")), _clean(payload.get("name"))
        if not code or not name:
            raise ValueError("Informe codigo e nome do fornecedor.")
        if Supplier.query.filter_by(code=code.upper()).first():
            raise ValueError("Ja existe fornecedor com este codigo.")
        supplier = Supplier(
            code=code.upper(), name=name, contact_name=_clean(payload.get("contact_name")),
            email=_clean(payload.get("email")), phone=_clean(payload.get("phone")),
            notes=_clean(payload.get("notes")), active=bool(payload.get("active", True)),
        )
        db.session.add(supplier)
        db.session.commit()
        return supplier.to_dict()

    return _run(action, status_code=201)


@bp.get("/compras/solicitacoes")
@auth_required
def list_purchase_requests():
    denied = _guard_management()
    if denied:
        return denied
    rows = PurchaseRequest.query.order_by(PurchaseRequest.created_at.desc()).all()
    return api_response(True, data=[row.to_dict() for row in rows])


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
        material_id = _positive_int(payload.get("material_id"), "Material")
        material = db.session.get(Material, material_id)
        if not material or not material.ativo:
            raise ValueError("Material ativo nao encontrado.")
        supplier_id = payload.get("supplier_id")
        supplier = None
        if supplier_id not in (None, ""):
            supplier = db.session.get(Supplier, _positive_int(supplier_id, "Fornecedor"))
            if not supplier or not supplier.active:
                raise ValueError("Fornecedor ativo nao encontrado.")
        link_id = payload.get("maintenance_material_id")
        link = None
        if link_id not in (None, ""):
            link = db.session.get(MaintenanceMaterial, _positive_int(link_id, "Material de manutencao"))
            if not link or link.material_id != material.id:
                raise ValueError("Vinculo de manutencao invalido para este material.")
        priority = str(payload.get("priority") or "MEDIA").strip().upper()
        if priority not in PRIORITIES:
            raise ValueError("Prioridade invalida.")
        purchase = PurchaseRequest(
            code="SC-PEND", material_id=material.id, supplier_id=supplier.id if supplier else None,
            maintenance_material_id=link.id if link else None,
            requested_quantity=_positive_int(payload.get("requested_quantity"), "Quantidade solicitada"),
            priority=priority, expected_date=_parse_date(payload.get("expected_date")),
            observation=_clean(payload.get("observation")), created_by_user_id=g.current_user.id,
        )
        db.session.add(purchase)
        db.session.flush()
        purchase.code = f"SC-{purchase.id:06d}"
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
        quantity = _positive_int(payload.get("quantity"), "Quantidade recebida")
        if quantity > purchase.requested_quantity - purchase.received_quantity:
            raise ValueError("Quantidade recebida excede o saldo da solicitacao.")
        receipt = PurchaseReceipt(
            purchase_request_id=purchase.id, quantity=quantity, idempotency_key=key,
            received_by_user_id=g.current_user.id, notes=_clean(payload.get("notes")),
        )
        register_material_movement(
            purchase.material, quantity=quantity, movement_type="ENTRADA", delta=quantity,
            observation=f"Recebimento da compra {purchase.code}",
        )
        purchase.received_quantity += quantity
        purchase.status = "RECEBIDA" if purchase.received_quantity == purchase.requested_quantity else "PARCIALMENTE_RECEBIDA"
        db.session.add(receipt)
        db.session.commit()
        return purchase.to_dict()

    return _run(action)

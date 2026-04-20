from __future__ import annotations

from datetime import datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_

from app.extensions import db
from app.models import Material, MechanicNonConformity
from app.services.auth_service import auth_required, user_has_mechanic_workspace_access
from app.services.material_service import register_material_movement

bp = Blueprint("mechanic_non_conformities", __name__)


def _guard_workspace_access():
    if not user_has_mechanic_workspace_access(g.current_user):
        return jsonify({"error": "Somente admin, gestor ou mecanico podem acessar este modulo."}), 403
    return None


def _resolve_positive_quantity(value, *, field_name: str = "Quantidade do material") -> int:
    try:
        quantity = int(value or 1)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} invalida.")
    if quantity <= 0:
        raise ValueError(f"{field_name} deve ser maior que zero.")
    return quantity


def _apply_material_on_resolution(item: MechanicNonConformity, payload: dict) -> None:
    material_id = payload.get("material_id")
    if not material_id:
        return

    material = Material.query.get(material_id)
    if not material or not material.ativo:
        raise ValueError("Material informado e invalido ou esta inativo.")

    quantity = _resolve_positive_quantity(payload.get("quantidade_material"))
    register_material_movement(
        material,
        quantity=quantity,
        movement_type="NAO_CONFORMIDADE",
        delta=-quantity,
        observation=f"Baixa para resolucao de NC mecanica: {item.item_nome}",
    )
    item.material_id = material.id
    item.quantidade_material = quantity
    item.codigo_peca = material.referencia
    item.descricao_peca = material.descricao


@bp.get("/mecanico/nao_conformidades")
@auth_required
def list_mechanic_non_conformities():
    denied = _guard_workspace_access()
    if denied:
        return denied

    query = MechanicNonConformity.query.order_by(MechanicNonConformity.created_at.desc())
    status_filter = (request.args.get("status") or "").strip().lower()
    search = (request.args.get("q") or "").strip()
    creator_id = request.args.get("created_by_user_id")
    scope = (request.args.get("escopo") or "").strip().lower()

    if status_filter == "abertas":
        query = query.filter(MechanicNonConformity.resolvido.is_(False))
    elif status_filter == "resolvidas":
        query = query.filter(MechanicNonConformity.resolvido.is_(True))

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                MechanicNonConformity.item_nome.ilike(pattern),
                MechanicNonConformity.veiculo_referencia.ilike(pattern),
                MechanicNonConformity.observacao.ilike(pattern),
            )
        )

    if g.current_user.tipo == "mecanico":
        query = query.filter(MechanicNonConformity.created_by_user_id == g.current_user.id)
    elif creator_id:
        try:
            creator_id_int = int(creator_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Filtro de criador invalido."}), 400
        query = query.filter(MechanicNonConformity.created_by_user_id == creator_id_int)
    elif scope == "minhas":
        query = query.filter(MechanicNonConformity.created_by_user_id == g.current_user.id)

    return jsonify([item.to_dict() for item in query.all()])


@bp.post("/mecanico/nao_conformidades")
@auth_required
def create_mechanic_non_conformity():
    denied = _guard_workspace_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    item_name = (payload.get("item_nome") or "").strip()
    if not item_name:
        return jsonify({"error": "Informe o nome da nao conformidade."}), 400

    item = MechanicNonConformity(
        created_by_user_id=g.current_user.id,
        veiculo_referencia=(payload.get("veiculo_referencia") or "").strip() or None,
        item_nome=item_name,
        observacao=(payload.get("observacao") or "").strip() or None,
        foto_antes=(payload.get("foto_antes") or "").strip() or None,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@bp.put("/mecanico/nao_conformidades/<int:item_id>/resolver")
@auth_required
def resolve_mechanic_non_conformity(item_id: int):
    denied = _guard_workspace_access()
    if denied:
        return denied

    item = MechanicNonConformity.query.get_or_404(item_id)
    if g.current_user.tipo == "mecanico" and item.created_by_user_id != g.current_user.id:
        return jsonify({"error": "Somente o mecanico criador pode resolver esta nao conformidade."}), 403

    payload = request.get_json(silent=True) or {}
    item.resolvido = True
    item.resolved_by_user_id = g.current_user.id
    item.data_resolucao = datetime.utcnow()
    item.foto_depois = (payload.get("foto_depois") or item.foto_depois or "").strip() or None
    item.observacao_resolucao = (payload.get("observacao_resolucao") or payload.get("observacao") or "").strip() or None
    item.codigo_peca = (payload.get("codigo_peca") or item.codigo_peca or "").strip() or None
    item.descricao_peca = (payload.get("descricao_peca") or item.descricao_peca or "").strip() or None

    try:
        _apply_material_on_resolution(item, payload)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    return jsonify(item.to_dict())

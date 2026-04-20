from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models import ChecklistItem, Material, Vehicle
from app.services.auth_service import auth_required, user_can_resolve_non_conformity
from app.services.material_service import register_material_movement

bp = Blueprint("non_conformities", __name__)


@bp.get("/nao_conformidades")
@auth_required
def list_non_conformities():
    query = ChecklistItem.query.filter_by(status="NC").order_by(ChecklistItem.created_at.desc())

    item_type = request.args.get("tipo")
    vehicle_identifier = request.args.get("veiculo")
    status_filter = request.args.get("status")

    if item_type:
        query = query.filter(ChecklistItem.item_nome.ilike(f"%{item_type}%"))

    if vehicle_identifier:
        pattern = f"%{vehicle_identifier}%"
        query = query.join(ChecklistItem.checklist).join(Vehicle).filter(
            (Vehicle.frota.ilike(pattern)) | (Vehicle.placa.ilike(pattern))
        )

    if status_filter == "abertas":
        query = query.filter(ChecklistItem.resolvido.is_(False))
    elif status_filter == "resolvidas":
        query = query.filter(ChecklistItem.resolvido.is_(True))

    return jsonify([item.to_dict() for item in query.all()])


@bp.put("/nao_conformidade/<int:item_id>/resolver")
@auth_required
def resolve_non_conformity(item_id: int):
    if not user_can_resolve_non_conformity(g.current_user):
        return jsonify({"error": "Somente admin, gestor ou mecanico podem resolver nao conformidades."}), 403

    item = ChecklistItem.query.get_or_404(item_id)
    if item.status != "NC":
        return jsonify({"error": "O item informado nao e uma nao conformidade."}), 400

    payload = request.get_json(silent=True) or {}
    material_id = payload.get("material_id")
    quantidade_material = payload.get("quantidade_material")
    item.resolvido = True
    item.data_resolucao = datetime.utcnow()
    item.resolved_by_user_id = g.current_user.id
    item.foto_depois = payload.get("foto_depois") or item.foto_depois
    item.codigo_peca = (payload.get("codigo_peca") or item.codigo_peca or "").strip() or None
    item.descricao_peca = (payload.get("descricao_peca") or item.descricao_peca or "").strip() or None
    if payload.get("observacao"):
        current_observation = item.observacao or ""
        suffix = payload["observacao"].strip()
        item.observacao = f"{current_observation}\nResolucao: {suffix}".strip()

    if material_id:
        material = Material.query.get(material_id)
        if not material or not material.ativo:
            return jsonify({"error": "Material informado e invalido ou esta inativo."}), 400
        try:
            quantidade = int(quantidade_material or 1)
        except (TypeError, ValueError):
            return jsonify({"error": "Quantidade do material invalida."}), 400
        if quantidade <= 0:
            return jsonify({"error": "Quantidade do material deve ser maior que zero."}), 400

        try:
            register_material_movement(
                material,
                quantity=quantidade,
                movement_type="NAO_CONFORMIDADE",
                delta=-quantidade,
                observation=f"Baixa para resolucao de {item.item_nome}",
                checklist_item_id=item.id,
            )
            item.codigo_peca = material.referencia
            item.descricao_peca = material.descricao
        except ValueError as exc:
            db.session.rollback()
            return jsonify({"error": str(exc)}), 400

    db.session.commit()
    return jsonify(item.to_dict())

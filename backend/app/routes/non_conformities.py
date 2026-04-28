from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models import Activity, ActivityItem, ChecklistItem, Material, User, Vehicle
from app.services.auth_service import auth_required, user_can_resolve_non_conformity, user_has_management_access
from app.services.material_service import register_material_movement
from app.services.audit_service import record_status_change
from app.utils.filters import apply_item_search
from app.utils.responses import api_response

bp = Blueprint("non_conformities", __name__)
_NC_ORIGIN_TAG = "[ORIGEM:NC#{id}]"

class NCStatus:
    """Centraliza os estados para evitar 'strings mágicas' espalhadas no código"""
    TYPE_NC = "NC"
    OPEN = "ABERTA"
    RESOLVED = "RESOLVIDA"

# --- UTILITÁRIOS ---

def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@bp.get("/nao_conformidades")
@auth_required
def list_non_conformities():
    # Uso do NCStatus.TYPE_NC em vez de "NC"
    query = ChecklistItem.query.filter_by(status=NCStatus.TYPE_NC).order_by(ChecklistItem.created_at.desc())

    vehicle_identifier = request.args.get("veiculo")
    status_filter = request.args.get("status")

    # Centralização da busca por item
    query = apply_item_search(query, ChecklistItem, request.args.get("tipo"))

    if vehicle_identifier:
        pattern = f"%{vehicle_identifier}%"
        query = query.join(ChecklistItem.checklist).join(Vehicle).filter(
            (Vehicle.frota.ilike(pattern)) | (Vehicle.placa.ilike(pattern))
        )

    if status_filter == "abertas":
        query = query.filter(ChecklistItem.resolvido.is_(False))
    elif status_filter == "resolvidas":
        query = query.filter(ChecklistItem.resolvido.is_(True))

    return api_response(True, data=[item.to_dict() for item in query.all()])


@bp.put("/nao_conformidade/<int:item_id>/resolver")
@auth_required
def resolve_non_conformity(item_id: int):
    if not user_can_resolve_non_conformity(g.current_user):
        return api_response(False, error="Acesso negado para resolução.", status_code=403)

    item = ChecklistItem.query.get_or_404(item_id)
    if item.status != NCStatus.TYPE_NC:
        return api_response(False, error="O item informado não é uma não conformidade.", status_code=400)
    
    old_state = "RESOLVIDA" if item.resolvido else "ABERTA"

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
            return api_response(False, error="Material inválido ou inativo.", status_code=400)
        try:
            quantidade = int(quantidade_material or 1)
        except (TypeError, ValueError):
            return api_response(False, error="Quantidade do material inválida.", status_code=400)
        if quantidade <= 0:
            return api_response(False, error="Quantidade deve ser maior que zero.", status_code=400)

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
            return api_response(False, error=str(exc), status_code=400)
    
    record_status_change(g.current_user.id, "CHECKLIST_ITEM", item.id, old_state, "RESOLVIDA")

    db.session.commit()
    return api_response(True, data=item.to_dict())


@bp.post("/nao_conformidade/<int:item_id>/atividade")
@auth_required
def create_activity_from_non_conformity(item_id: int):
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Acesso negado para abertura de atividade.", status_code=403)

    item = ChecklistItem.query.get_or_404(item_id)
    if item.status != "NC":
        return api_response(False, error="O item informado não é uma não conformidade.", status_code=400)

    vehicle = item.checklist.vehicle
    payload = request.get_json(silent=True) or {}

    source_tag = _NC_ORIGIN_TAG.format(id=item.id)
    duplicate_open = (
        Activity.query.join(ActivityItem, ActivityItem.activity_id == Activity.id)
        .filter(
            Activity.status == "ABERTA",
            ActivityItem.vehicle_id == vehicle.id,
            Activity.observacao.ilike(f"%{source_tag}%"),
        )
        .order_by(Activity.created_at.desc())
        .first()
    )
    if duplicate_open and not bool(payload.get("permitir_duplicada")):
        err = (f"Já existe atividade aberta vinculada a esta não conformidade: #{duplicate_open.id}. "
               "Finalize a atividade existente ou confirme a abertura duplicada.")
        return api_response(False, error=err, status_code=409)

    item_nome = _clean(payload.get("item_nome")) or item.item_nome
    titulo = _clean(payload.get("titulo")) or f"Tratativa NC - {vehicle.frota} - {item_nome}"

    material = None
    material_id = payload.get("material_id")
    if material_id:
        material = Material.query.get(material_id)
        if not material or not material.ativo:
            return api_response(False, error="Material informado é inválido ou inativo.", status_code=400)

    try:
        quantidade_por_equipamento = max(1, int(payload.get("quantidade_por_equipamento") or 1))
    except (TypeError, ValueError):
        return api_response(False, error="Quantidade por equipamento inválida.", status_code=400)

    assigned_mechanic = None
    assigned_mechanic_id = payload.get("assigned_mechanic_user_id")
    if assigned_mechanic_id:
        assigned_mechanic = User.query.get(assigned_mechanic_id)
        if not assigned_mechanic or assigned_mechanic.tipo != "mecanico" or not assigned_mechanic.ativo:
            return api_response(False, error="Mecânico direcionado inválido ou inativo.", status_code=400)

    observation_lines = []
    user_observation = _clean(payload.get("observacao"))
    if user_observation:
        observation_lines.append(user_observation)
    observation_lines.append(f"Origem: Nao conformidade #{item.id}")
    observation_lines.append(source_tag)
    composed_observation = "\n".join(observation_lines)

    activity = Activity(
        titulo=titulo,
        item_nome=item_nome,
        tipo_equipamento=(vehicle.tipo or "misto").lower(),
        material_id=material.id if material else None,
        quantidade_por_equipamento=quantidade_por_equipamento,
        codigo_peca=_clean(payload.get("codigo_peca")) or item.codigo_peca or (material.referencia if material else None),
        descricao_peca=_clean(payload.get("descricao_peca")) or item.descricao_peca or (material.descricao if material else None),
        fornecedor_peca=_clean(payload.get("fornecedor_peca")),
        lote_peca=_clean(payload.get("lote_peca")),
        observacao=composed_observation,
        created_by_user_id=g.current_user.id,
        assigned_mechanic_user_id=assigned_mechanic.id if assigned_mechanic else None,
    )
    db.session.add(activity)
    db.session.flush()

    db.session.add(
        ActivityItem(
            activity_id=activity.id,
            vehicle_id=vehicle.id,
            foto_antes=item.foto_antes,
            status_execucao="PENDENTE",
        )
    )

    db.session.commit()
    return api_response(True, data=activity.to_dict(include_items=True), status_code=201)

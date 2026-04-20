from __future__ import annotations

from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models import Activity, ActivityItem, Material, User, Vehicle
from app.services.auth_service import auth_required, user_has_management_access
from app.services.material_service import apply_activity_stock_change

bp = Blueprint("activities", __name__)


def _guard_management_access():
    if not user_has_management_access(g.current_user):
        return jsonify({"error": "Somente admin ou gestor podem gerenciar atividades."}), 403
    return None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _activity_query():
    query = Activity.query.order_by(Activity.created_at.desc())
    tipo = request.args.get("tipo")
    status = request.args.get("status")
    item = request.args.get("item")
    assigned_mechanic_id = request.args.get("mecanico_id", type=int)
    only_mine = request.args.get("minhas") == "true"

    if g.current_user.tipo == "mecanico":
        query = query.filter(
            (Activity.assigned_mechanic_user_id == g.current_user.id)
            | (Activity.assigned_mechanic_user_id.is_(None))
        )
    elif assigned_mechanic_id:
        query = query.filter(Activity.assigned_mechanic_user_id == assigned_mechanic_id)
    elif only_mine:
        query = query.filter(Activity.assigned_mechanic_user_id == g.current_user.id)

    if tipo:
        query = query.filter(Activity.tipo_equipamento == tipo.lower())
    if status:
        query = query.filter(Activity.status == status.upper())
    if item:
        query = query.filter(Activity.item_nome.ilike(f"%{item}%"))
    return query


@bp.get("/atividades")
@auth_required
def list_activities():
    return jsonify([activity.to_dict() for activity in _activity_query().all()])


@bp.get("/atividades/<int:activity_id>")
@auth_required
def get_activity(activity_id: int):
    activity = Activity.query.get_or_404(activity_id)
    return jsonify(activity.to_dict(include_items=True))


@bp.post("/atividades")
@auth_required
def create_activity():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    vehicle_ids = payload.get("vehicle_ids") or []
    item_nome = _clean(payload.get("item_nome"))
    if not item_nome:
        return jsonify({"error": "Informe o modulo ou componente da atividade."}), 400
    if not vehicle_ids:
        return jsonify({"error": "Selecione ao menos um equipamento para a atividade."}), 400

    vehicles = Vehicle.query.filter(Vehicle.id.in_(vehicle_ids)).order_by(Vehicle.frota.asc()).all()
    if len(vehicles) != len(set(vehicle_ids)):
        return jsonify({"error": "Ha equipamentos invalidos na selecao."}), 400

    tipos = {vehicle.tipo for vehicle in vehicles}
    tipo_equipamento = payload.get("tipo_equipamento")
    if not tipo_equipamento:
        tipo_equipamento = tipos.pop() if len(tipos) == 1 else "misto"
    tipo_equipamento = str(tipo_equipamento).strip().lower()

    titulo = _clean(payload.get("titulo")) or f"Troca em massa - {item_nome}"
    material_id = payload.get("material_id")
    material = None
    if material_id:
        material = Material.query.get(material_id)
        if not material or not material.ativo:
            return jsonify({"error": "Material informado e invalido ou esta inativo."}), 400

    try:
        quantidade_por_equipamento = max(1, int(payload.get("quantidade_por_equipamento") or 1))
    except (TypeError, ValueError):
        return jsonify({"error": "Quantidade por equipamento invalida."}), 400

    assigned_mechanic_id = payload.get("assigned_mechanic_user_id")
    assigned_mechanic = None
    if assigned_mechanic_id:
        assigned_mechanic = User.query.get(assigned_mechanic_id)
        if not assigned_mechanic or assigned_mechanic.tipo != "mecanico" or not assigned_mechanic.ativo:
            return jsonify({"error": "Mecanico direcionado invalido ou inativo."}), 400

    activity = Activity(
        titulo=titulo,
        item_nome=item_nome,
        tipo_equipamento=tipo_equipamento,
        material_id=material.id if material else None,
        quantidade_por_equipamento=quantidade_por_equipamento,
        codigo_peca=_clean(payload.get("codigo_peca")) or (material.referencia if material else None),
        descricao_peca=_clean(payload.get("descricao_peca")) or (material.descricao if material else None),
        fornecedor_peca=_clean(payload.get("fornecedor_peca")),
        lote_peca=_clean(payload.get("lote_peca")),
        observacao=_clean(payload.get("observacao")),
        created_by_user_id=g.current_user.id,
        assigned_mechanic_user_id=assigned_mechanic.id if assigned_mechanic else None,
    )
    db.session.add(activity)
    db.session.flush()

    for vehicle in vehicles:
        db.session.add(
            ActivityItem(
                activity_id=activity.id,
                vehicle_id=vehicle.id,
                status_execucao="PENDENTE",
            )
        )

    db.session.commit()
    return jsonify(activity.to_dict(include_items=True)), 201


@bp.put("/atividades/<int:activity_id>/itens/<int:item_id>")
@auth_required
def update_activity_item(activity_id: int, item_id: int):
    activity = Activity.query.get_or_404(activity_id)
    item = ActivityItem.query.filter_by(id=item_id, activity_id=activity.id).first_or_404()
    payload = request.get_json(silent=True) or {}
    previous_status = item.status_execucao

    status_execucao = str(payload.get("status_execucao") or item.status_execucao).strip().upper()
    if status_execucao not in {"PENDENTE", "INSTALADO", "NAO_INSTALADO"}:
        return jsonify({"error": "Status da atividade invalido."}), 400

    item.status_execucao = status_execucao
    item.observacao = _clean(payload.get("observacao")) or item.observacao
    item.foto_antes = _clean(payload.get("foto_antes")) or item.foto_antes
    item.foto_depois = _clean(payload.get("foto_depois")) or item.foto_depois
    if status_execucao == "PENDENTE":
        item.instalado_em = None
        item.executado_por_nome = None
        item.executado_por_login = None
    else:
        item.instalado_em = datetime.utcnow()
        item.executado_por_nome = g.current_user.nome
        item.executado_por_login = g.current_user.login

    try:
        apply_activity_stock_change(
            activity.material,
            previous_status=previous_status,
            new_status=status_execucao,
            quantity_per_equipment=activity.quantidade_por_equipamento,
            activity_id=activity.id,
            vehicle_label=item.vehicle.frota if item.vehicle else "equipamento",
        )
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    resumo = activity.summary()
    all_done = resumo["pendentes"] == 0
    activity.status = "FINALIZADA" if all_done else "ABERTA"
    activity.finalized_at = datetime.utcnow() if all_done else None

    db.session.commit()
    return jsonify(activity.to_dict(include_items=True))

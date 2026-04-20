from __future__ import annotations

from datetime import datetime, time

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func

from app.extensions import db
from app.models import Material, MaterialMovement
from app.services.auth_service import auth_required, user_has_management_access
from app.services.material_service import register_material_movement

bp = Blueprint("materials", __name__)


def _guard_management_access():
    if not user_has_management_access(g.current_user):
        return jsonify({"error": "Somente admin ou gestor podem gerenciar materiais."}), 403
    return None


def _clean(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_positive_int(value, *, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError("Informe um numero inteiro valido.")
    if number < 0:
        raise ValueError("O valor informado nao pode ser negativo.")
    return number


def _parse_date(value: str | None, *, end_of_day: bool = False):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip())
    except ValueError:
        raise ValueError("Data invalida. Use o formato YYYY-MM-DD.")
    if len(str(value).strip()) <= 10:
        parsed_date = parsed.date()
        return datetime.combine(parsed_date, time.max if end_of_day else time.min)
    return parsed


@bp.get("/materiais")
@auth_required
def list_materials():
    query = Material.query.order_by(Material.descricao.asc())
    tipo = request.args.get("tipo")
    search = request.args.get("q")
    ativos = request.args.get("ativos", "true")
    baixo_estoque = request.args.get("baixo_estoque")

    if tipo:
        query = query.filter(Material.aplicacao_tipo.in_([tipo.lower(), "ambos"]))
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (Material.referencia.ilike(pattern))
            | (Material.descricao.ilike(pattern))
        )
    if ativos != "all":
        query = query.filter(Material.ativo.is_(ativos == "true"))

    materials = query.all()
    if baixo_estoque == "true":
        materials = [material for material in materials if material.quantidade_estoque <= material.estoque_minimo]
    return jsonify([material.to_dict() for material in materials])


@bp.get("/materiais/relatorio")
@auth_required
def material_report():
    try:
        date_from = _parse_date(request.args.get("data_inicial"))
        date_to = _parse_date(request.args.get("data_final"), end_of_day=True)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    materials = Material.query.order_by(Material.descricao.asc()).all()
    low_stock_rows = []
    for material in materials:
        if material.quantidade_estoque <= material.estoque_minimo:
            low_stock_rows.append(
                {
                    "id": material.id,
                    "referencia": material.referencia,
                    "descricao": material.descricao,
                    "aplicacao_tipo": material.aplicacao_tipo,
                    "quantidade_estoque": material.quantidade_estoque,
                    "estoque_minimo": material.estoque_minimo,
                    "deficit": max(material.estoque_minimo - material.quantidade_estoque, 0),
                }
            )

    movements_query = MaterialMovement.query
    if date_from:
        movements_query = movements_query.filter(MaterialMovement.created_at >= date_from)
    if date_to:
        movements_query = movements_query.filter(MaterialMovement.created_at <= date_to)

    consumption_types = ("SAIDA", "ATIVIDADE", "NAO_CONFORMIDADE")
    consumption_rows = (
        db.session.query(
            Material.id.label("material_id"),
            Material.referencia.label("referencia"),
            Material.descricao.label("descricao"),
            func.sum(MaterialMovement.quantidade).label("consumo_total"),
            func.max(MaterialMovement.created_at).label("ultimo_consumo"),
        )
        .join(MaterialMovement, MaterialMovement.material_id == Material.id)
        .filter(MaterialMovement.tipo_movimento.in_(consumption_types))
    )
    if date_from:
        consumption_rows = consumption_rows.filter(MaterialMovement.created_at >= date_from)
    if date_to:
        consumption_rows = consumption_rows.filter(MaterialMovement.created_at <= date_to)
    consumption_rows = (
        consumption_rows.group_by(Material.id, Material.referencia, Material.descricao)
        .order_by(func.sum(MaterialMovement.quantidade).desc(), Material.descricao.asc())
        .all()
    )

    consumption = [
        {
            "material_id": row.material_id,
            "referencia": row.referencia,
            "descricao": row.descricao,
            "consumo_total": int(row.consumo_total or 0),
            "ultimo_consumo": row.ultimo_consumo.isoformat() if row.ultimo_consumo else None,
        }
        for row in consumption_rows
    ]
    ranking = consumption[:5]

    total_stock = sum(int(material.quantidade_estoque or 0) for material in materials)
    total_consumed = sum(item["consumo_total"] for item in consumption)

    return jsonify(
        {
            "periodo": {
                "data_inicial": date_from.date().isoformat() if date_from else None,
                "data_final": date_to.date().isoformat() if date_to else None,
            },
            "resumo": {
                "total_materiais": len(materials),
                "abaixo_minimo": len(low_stock_rows),
                "saldo_total": total_stock,
                "consumo_total_periodo": total_consumed,
            },
            "baixo_estoque": low_stock_rows,
            "consumo_periodo": consumption,
            "ranking_uso": ranking,
        }
    )


@bp.post("/materiais")
@auth_required
def create_material():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    referencia = _clean(payload.get("referencia"))
    descricao = _clean(payload.get("descricao"))
    aplicacao_tipo = (_clean(payload.get("aplicacao_tipo")) or "ambos").lower()

    if not referencia or not descricao:
        return jsonify({"error": "Referencia e descricao sao obrigatorias."}), 400
    if aplicacao_tipo not in {"cavalo", "carreta", "ambos"}:
        return jsonify({"error": "Aplicacao do material invalida."}), 400
    if Material.query.filter(Material.referencia == referencia).first():
        return jsonify({"error": "Ja existe um material com esta referencia."}), 400

    try:
        quantidade_estoque = _as_positive_int(payload.get("quantidade_estoque"), default=0)
        estoque_minimo = _as_positive_int(payload.get("estoque_minimo"), default=0)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    material = Material(
        referencia=referencia,
        descricao=descricao,
        aplicacao_tipo=aplicacao_tipo,
        foto_path=_clean(payload.get("foto_path")),
        quantidade_estoque=0,
        estoque_minimo=estoque_minimo,
        ativo=bool(payload.get("ativo", True)),
    )
    db.session.add(material)
    db.session.flush()

    if quantidade_estoque > 0:
        register_material_movement(
            material,
            quantity=quantidade_estoque,
            movement_type="ENTRADA",
            delta=quantidade_estoque,
            observation="Estoque inicial do cadastro",
        )

    db.session.commit()
    return jsonify(material.to_dict()), 201


@bp.put("/materiais/<int:material_id>")
@auth_required
def update_material(material_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    material = Material.query.get_or_404(material_id)
    payload = request.get_json(silent=True) or {}
    referencia = _clean(payload.get("referencia"))
    descricao = _clean(payload.get("descricao"))
    aplicacao_tipo = (_clean(payload.get("aplicacao_tipo")) or material.aplicacao_tipo).lower()

    if not referencia or not descricao:
        return jsonify({"error": "Referencia e descricao sao obrigatorias."}), 400
    if aplicacao_tipo not in {"cavalo", "carreta", "ambos"}:
        return jsonify({"error": "Aplicacao do material invalida."}), 400

    duplicate = Material.query.filter(Material.referencia == referencia, Material.id != material.id).first()
    if duplicate:
        return jsonify({"error": "Ja existe um material com esta referencia."}), 400

    try:
        estoque_minimo = _as_positive_int(payload.get("estoque_minimo"), default=material.estoque_minimo)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    material.referencia = referencia
    material.descricao = descricao
    material.aplicacao_tipo = aplicacao_tipo
    material.foto_path = _clean(payload.get("foto_path")) or material.foto_path
    material.estoque_minimo = estoque_minimo
    material.ativo = bool(payload.get("ativo", material.ativo))

    db.session.commit()
    return jsonify(material.to_dict())


@bp.delete("/materiais/<int:material_id>")
@auth_required
def delete_material(material_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    material = Material.query.get_or_404(material_id)
    material.ativo = False
    db.session.commit()
    return jsonify({"status": "ok", "material": material.to_dict()})


@bp.get("/materiais/<int:material_id>/movimentos")
@auth_required
def list_material_movements(material_id: int):
    Material.query.get_or_404(material_id)
    movements = (
        MaterialMovement.query.filter_by(material_id=material_id)
        .order_by(MaterialMovement.created_at.desc())
        .all()
    )
    return jsonify([movement.to_dict() for movement in movements])


@bp.post("/materiais/<int:material_id>/ajustar_estoque")
@auth_required
def adjust_material_stock(material_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    material = Material.query.get_or_404(material_id)
    payload = request.get_json(silent=True) or {}
    movement_type = str(payload.get("tipo_movimento") or "AJUSTE").strip().upper()

    try:
        quantidade = _as_positive_int(payload.get("quantidade"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if quantidade <= 0:
        return jsonify({"error": "Informe uma quantidade maior que zero."}), 400

    if movement_type not in {"ENTRADA", "SAIDA", "AJUSTE"}:
        return jsonify({"error": "Tipo de movimentacao invalido."}), 400

    delta = quantidade if movement_type == "ENTRADA" else -quantidade
    try:
        register_material_movement(
            material,
            quantity=quantidade,
            movement_type=movement_type,
            delta=delta,
            observation=_clean(payload.get("observacao")),
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    return jsonify(material.to_dict())

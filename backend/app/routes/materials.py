from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from flask import Blueprint, g, request
from sqlalchemy import func

from app.extensions import db
from app.models import MaintenanceMaterial, Material, MaterialMovement
from app.services.intelligent_rules_service import get_rule_value
from app.services.auth_service import auth_required, user_has_management_access
from app.services.material_service import register_material_movement
from app.utils.responses import api_response

bp = Blueprint("materials", __name__)


def _guard_management_access():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar materiais.", status_code=403)
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


def _movement_delta(movement: MaterialMovement) -> int:
    return int(movement.saldo_posterior or 0) - int(movement.saldo_anterior or 0)


def _build_movement_rows(movements: list[MaterialMovement], *, positive: bool) -> list[dict]:
    grouped: dict[int, dict] = {}
    for movement in movements:
        delta = _movement_delta(movement)
        quantity = delta if positive else abs(delta)
        if positive and quantity <= 0:
            continue
        if not positive and delta >= 0:
            continue
        material = movement.material
        if not material:
            continue
        row = grouped.setdefault(
            int(material.id),
            {
                "material_id": material.id,
                "referencia": material.referencia,
                "descricao": material.descricao,
                "aplicacao_tipo": material.aplicacao_tipo,
                "total": 0,
                "ultimo_movimento": None,
            },
        )
        row["total"] += int(quantity)
        if movement.created_at and (not row["ultimo_movimento"] or movement.created_at > row["ultimo_movimento"]):
            row["ultimo_movimento"] = movement.created_at

    rows = list(grouped.values())
    rows.sort(key=lambda row: (-int(row["total"] or 0), str(row["descricao"] or "").upper()))
    for row in rows:
        row["ultimo_movimento"] = row["ultimo_movimento"].isoformat() if row["ultimo_movimento"] else None
    return rows


def _build_reservation_rows(links: list[MaintenanceMaterial]) -> list[dict]:
    grouped: dict[int, dict] = {}
    for link in links:
        material = link.material
        schedule = link.schedule
        if not material or not schedule:
            continue
        row = grouped.setdefault(
            int(material.id),
            {
                "material_id": material.id,
                "referencia": material.referencia,
                "descricao": material.descricao,
                "aplicacao_tipo": material.aplicacao_tipo,
                "familias": set(),
                "reservado_total": 0,
                "necessario_total": 0,
                "programacoes": set(),
                "pacotes": set(),
                "ordens_servico": set(),
                "materiais_bloqueados": 0,
                "ultima_atualizacao": None,
            },
        )
        row["reservado_total"] += int(link.quantity_reserved or 0)
        row["necessario_total"] += int(link.quantity_required or 0)
        row["programacoes"].add(int(schedule.id))
        if schedule.package_reference_label():
            row["pacotes"].add(schedule.package_reference_label())
        for order in schedule.work_orders:
            if order.order_number:
                row["ordens_servico"].add(order.order_number)
        family = str(schedule.vehicle_family() or "ambos").strip().lower()
        if family:
            row["familias"].add(family)
        if str(link.status or "").upper() in {"AGUARDANDO_MATERIAL", "EM_COMPRAS"}:
            row["materiais_bloqueados"] += 1
        if link.updated_at and (not row["ultima_atualizacao"] or link.updated_at > row["ultima_atualizacao"]):
            row["ultima_atualizacao"] = link.updated_at

    rows = []
    for row in grouped.values():
        rows.append(
            {
                "material_id": row["material_id"],
                "referencia": row["referencia"],
                "descricao": row["descricao"],
                "aplicacao_tipo": row["aplicacao_tipo"],
                "familia_veiculo": " / ".join(sorted(row["familias"])) if row["familias"] else "ambos",
                "reservado_total": int(row["reservado_total"] or 0),
                "necessario_total": int(row["necessario_total"] or 0),
                "programacoes": len(row["programacoes"]),
                "pacotes": ", ".join(sorted(row["pacotes"])) if row["pacotes"] else "-",
                "ordens_servico": len(row["ordens_servico"]),
                "materiais_bloqueados": int(row["materiais_bloqueados"] or 0),
                "ultima_atualizacao": row["ultima_atualizacao"].isoformat() if row["ultima_atualizacao"] else None,
            }
        )
    rows.sort(key=lambda row: (-int(row["reservado_total"] or 0), str(row["descricao"] or "").upper()))
    return rows


def _timeline_dates(
    date_from: datetime | None,
    date_to: datetime | None,
    movement_dates: list[date],
    reservation_dates: list[date],
) -> list[date]:
    if date_from and date_to:
        start_date = date_from.date()
        end_date = date_to.date()
    else:
        end_date = date.today()
        start_date = end_date - timedelta(days=13)
        if movement_dates or reservation_dates:
            event_dates = sorted(movement_dates + reservation_dates)
            start_date = min(start_date, event_dates[0])
            end_date = max(end_date, event_dates[-1])
            if (end_date - start_date).days > 30:
                start_date = end_date - timedelta(days=29)
    if end_date < start_date:
        end_date = start_date
    days: list[date] = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)
    return days


def _build_timeline_rows(
    movements: list[MaterialMovement],
    links: list[MaintenanceMaterial],
    *,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[dict]:
    entries_by_day: dict[date, int] = defaultdict(int)
    exits_by_day: dict[date, int] = defaultdict(int)
    reserves_by_day: dict[date, int] = defaultdict(int)

    movement_dates: list[date] = []
    for movement in movements:
        if not movement.created_at:
            continue
        movement_day = movement.created_at.date()
        movement_dates.append(movement_day)
        delta = _movement_delta(movement)
        if delta > 0:
            entries_by_day[movement_day] += int(delta)
        elif delta < 0:
            exits_by_day[movement_day] += abs(int(delta))

    reservation_dates: list[date] = []
    for link in links:
        if not link.updated_at:
            continue
        updated_day = link.updated_at.date()
        reservation_dates.append(updated_day)
        reserves_by_day[updated_day] += int(link.quantity_reserved or 0)

    rows = []
    for day in _timeline_dates(date_from, date_to, movement_dates, reservation_dates):
        entries = int(entries_by_day.get(day, 0))
        exits = int(exits_by_day.get(day, 0))
        reserves = int(reserves_by_day.get(day, 0))
        max_value = max(entries, exits, reserves, 1)
        rows.append(
            {
                "data": day.isoformat(),
                "entradas": entries,
                "saidas": exits,
                "reservas": reserves,
                "entradas_barra": "█" * max(1, round((entries / max_value) * 10)) if entries else "",
                "saidas_barra": "█" * max(1, round((exits / max_value) * 10)) if exits else "",
                "reservas_barra": "█" * max(1, round((reserves / max_value) * 10)) if reserves else "",
            }
        )
    return rows


def _build_reserve_alerts(reserve_rows: list[dict], exit_rows: list[dict]) -> list[dict]:
    minimum_reserved = int(get_rule_value("reserve_high_quantity_minimum") or 3)
    reserve_multiplier = max(1, int(get_rule_value("reserve_high_multiplier") or 2))
    low_consumption_divisor = max(1, int(get_rule_value("reserve_low_consumption_divisor") or 3))
    exit_by_material = {int(row["material_id"]): int(row["total"] or 0) for row in exit_rows}
    alerts: list[dict] = []
    for row in reserve_rows:
        reserved_total = int(row.get("reservado_total") or 0)
        consumption_total = int(exit_by_material.get(int(row["material_id"]), 0))
        blocked = int(row.get("materiais_bloqueados") or 0)
        high_reserve = reserved_total >= max(minimum_reserved, max(1, consumption_total) * reserve_multiplier)
        low_consumption = consumption_total <= max(1, reserved_total // low_consumption_divisor)
        if not (high_reserve and low_consumption):
            continue
        alerts.append(
            {
                "material_id": row["material_id"],
                "referencia": row["referencia"],
                "descricao": row["descricao"],
                "reservado_total": reserved_total,
                "consumo_total": consumption_total,
                "programacoes": row.get("programacoes", 0),
                "materiais_bloqueados": blocked,
                "leitura": "Há muita peça comprometida e pouca saída real. Vale revisar agenda, pacote ou compra parada.",
            }
        )
    alerts.sort(key=lambda row: (-int(row["reservado_total"] or 0), str(row["descricao"] or "").upper()))
    return alerts


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
    return api_response(True, data=[material.to_dict() for material in materials])


@bp.get("/materiais/relatorio")
@auth_required
def material_report():
    try:
        date_from = _parse_date(request.args.get("data_inicial"))
        date_to = _parse_date(request.args.get("data_final"), end_of_day=True)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)

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
    movements = (
        movements_query.join(Material, Material.id == MaterialMovement.material_id)
        .order_by(MaterialMovement.created_at.desc(), Material.descricao.asc())
        .all()
    )

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
    entry_rows = _build_movement_rows(movements, positive=True)
    exit_rows = _build_movement_rows(movements, positive=False)

    reservation_links_query = MaintenanceMaterial.query.join(Material, Material.id == MaintenanceMaterial.material_id)
    if date_from:
        reservation_links_query = reservation_links_query.filter(MaintenanceMaterial.updated_at >= date_from)
    if date_to:
        reservation_links_query = reservation_links_query.filter(MaintenanceMaterial.updated_at <= date_to)
    reservation_links = reservation_links_query.order_by(MaintenanceMaterial.updated_at.desc()).all()
    reserve_rows = _build_reservation_rows(reservation_links)
    reserve_alerts = _build_reserve_alerts(reserve_rows, exit_rows)
    timeline_rows = _build_timeline_rows(movements, reservation_links, date_from=date_from, date_to=date_to)

    total_stock = sum(int(material.quantidade_estoque or 0) for material in materials)
    total_consumed = sum(item["consumo_total"] for item in consumption)
    total_entries = sum(int(item["total"] or 0) for item in entry_rows)
    total_reserved = sum(int(item["reservado_total"] or 0) for item in reserve_rows)

    data = {
        "periodo": {
            "data_inicial": date_from.date().isoformat() if date_from else None,
            "data_final": date_to.date().isoformat() if date_to else None,
        },
        "resumo": {
            "total_materiais": len(materials),
            "abaixo_minimo": len(low_stock_rows),
            "saldo_total": total_stock,
            "entradas_total_periodo": total_entries,
            "consumo_total_periodo": total_consumed,
            "saidas_total_periodo": total_consumed,
            "reservas_ativas": total_reserved,
            "materiais_com_reserva": sum(1 for row in reserve_rows if int(row.get("reservado_total") or 0) > 0),
            "alertas_reserva_consumo": len(reserve_alerts),
        },
        "baixo_estoque": low_stock_rows,
        "consumo_periodo": consumption,
        "ranking_uso": ranking,
        "entrada_periodo": entry_rows,
        "saida_periodo": exit_rows,
        "ranking_entrada": entry_rows[:5],
        "ranking_saida": exit_rows[:5],
        "reservas_atuais": reserve_rows,
        "alertas_reserva_consumo": reserve_alerts,
        "grafico_temporal": timeline_rows,
    }
    return api_response(True, data=data)


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
        return api_response(False, error="Referencia e descricao sao obrigatorias.", status_code=400)
    if aplicacao_tipo not in {"cavalo", "carreta", "ambos"}:
        return api_response(False, error="Aplicacao do material invalida.", status_code=400)
    if Material.query.filter(Material.referencia == referencia).first():
        return api_response(False, error="Ja existe um material com esta referencia.", status_code=400)

    try:
        quantidade_estoque = _as_positive_int(payload.get("quantidade_estoque"), default=0)
        estoque_minimo = _as_positive_int(payload.get("estoque_minimo"), default=0)
        ponto_reposicao = _as_positive_int(payload.get("ponto_reposicao"), default=estoque_minimo)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    classe_abc = str(payload.get("classe_abc") or "C").strip().upper()
    if classe_abc not in {"A", "B", "C"}:
        return api_response(False, error="Classe ABC invalida.", status_code=400)

    material = Material(
        referencia=referencia,
        descricao=descricao,
        aplicacao_tipo=aplicacao_tipo,
        foto_path=_clean(payload.get("foto_path")),
        quantidade_estoque=0,
        estoque_minimo=estoque_minimo,
        ponto_reposicao=ponto_reposicao,
        classe_abc=classe_abc,
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
    return api_response(True, data=material.to_dict(), status_code=201)


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
        return api_response(False, error="Referencia e descricao sao obrigatorias.", status_code=400)
    if aplicacao_tipo not in {"cavalo", "carreta", "ambos"}:
        return api_response(False, error="Aplicacao do material invalida.", status_code=400)

    duplicate = Material.query.filter(Material.referencia == referencia, Material.id != material.id).first()
    if duplicate:
        return api_response(False, error="Ja existe um material com esta referencia.", status_code=400)

    try:
        estoque_minimo = _as_positive_int(payload.get("estoque_minimo"), default=material.estoque_minimo)
        ponto_reposicao = _as_positive_int(payload.get("ponto_reposicao"), default=material.ponto_reposicao)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    classe_abc = str(payload.get("classe_abc") or material.classe_abc).strip().upper()
    if classe_abc not in {"A", "B", "C"}:
        return api_response(False, error="Classe ABC invalida.", status_code=400)

    material.referencia = referencia
    material.descricao = descricao
    material.aplicacao_tipo = aplicacao_tipo
    material.foto_path = _clean(payload.get("foto_path")) or material.foto_path
    material.estoque_minimo = estoque_minimo
    material.ponto_reposicao = ponto_reposicao
    material.classe_abc = classe_abc
    material.ativo = bool(payload.get("ativo", material.ativo))

    db.session.commit()
    return api_response(True, data=material.to_dict())


@bp.delete("/materiais/<int:material_id>")
@auth_required
def delete_material(material_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    material = Material.query.get_or_404(material_id)
    material.ativo = False
    db.session.commit()
    return api_response(True, data={"status": "ok", "material": material.to_dict()})


@bp.get("/materiais/<int:material_id>/movimentos")
@auth_required
def list_material_movements(material_id: int):
    Material.query.get_or_404(material_id)
    movements = (
        MaterialMovement.query.filter_by(material_id=material_id)
        .order_by(MaterialMovement.created_at.desc())
        .all()
    )
    return api_response(True, data=[movement.to_dict() for movement in movements])


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
        return api_response(False, error=str(exc), status_code=400)
    if quantidade <= 0:
        return api_response(False, error="Informe uma quantidade maior que zero.", status_code=400)

    if movement_type not in {"ENTRADA", "SAIDA", "AJUSTE"}:
        return api_response(False, error="Tipo de movimentacao invalido.", status_code=400)

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
        return api_response(False, error=str(exc), status_code=400)

    return api_response(True, data=material.to_dict())

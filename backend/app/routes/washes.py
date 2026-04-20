from __future__ import annotations

import tempfile
from io import BytesIO
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, send_file

from app.models import WashQueueItem
from app.services.auth_service import auth_required, user_has_management_access
from app.services.wash_service import (
    apply_preventive_schedule,
    build_tomorrow_message_payload,
    build_wash_overview,
    clear_schedule_decision,
    discover_wash_file,
    reclassify_wash_queue_categories,
    mark_unavailable,
    mark_schedule_not_completed,
    reopen_completed_schedule_item,
    register_wash,
    release_unavailable,
    set_blocked_day,
    save_wash_category_values,
    sync_wash_queue,
    update_plan_config,
)
from app.services.wash_pdf_export_service import export_monthly_wash_pdf

bp = Blueprint("washes", __name__)


def _guard_management_access():
    if not user_has_management_access(g.current_user):
        return jsonify({"error": "Somente admin ou gestor podem gerenciar lavagens."}), 403
    return None


def _wash_file():
    return discover_wash_file(current_app.config.get("WASH_CONTROL_FILE"))


def _strip_wash_values(payload):
    if isinstance(payload, list):
        return [_strip_wash_values(item) for item in payload]
    if isinstance(payload, dict):
        blocked_keys = {"valor", "valor_total", "valor_sugerido", "valor_unitario", "last_value"}
        return {
            key: _strip_wash_values(value)
            for key, value in payload.items()
            if key not in blocked_keys and key != "tabela_valores"
        }
    return payload


@bp.get("/lavagens/visao")
@auth_required
def wash_overview():
    year = request.args.get("ano", type=int)
    month = request.args.get("mes", type=int)
    overview = build_wash_overview(year=year, month=month)
    if not user_has_management_access(g.current_user):
        overview = _strip_wash_values(overview)
        overview["tabela_valores"] = []
    return jsonify(overview)


@bp.get("/lavagens/relatorio/pdf")
@auth_required
def wash_month_pdf_report():
    denied = _guard_management_access()
    if denied:
        return denied

    year = request.args.get("ano", type=int)
    month = request.args.get("mes", type=int)
    overview = build_wash_overview(year=year, month=month)
    period = overview.get("periodo") or {}
    safe_year = int(period.get("ano") or year or datetime.utcnow().year)
    safe_month = int(period.get("mes") or month or datetime.utcnow().month)

    tmp = tempfile.NamedTemporaryFile(prefix="lavagens_mensal_", suffix=".pdf", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    export_monthly_wash_pdf(overview, tmp_path, generated_by=g.current_user.nome or g.current_user.login)
    pdf_buffer = BytesIO(tmp_path.read_bytes())
    tmp_path.unlink(missing_ok=True)
    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"relatorio_lavagens_{safe_year}_{safe_month:02d}.pdf",
    )


@bp.put("/lavagens/valores")
@auth_required
def save_values():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    rows = payload.get("valores") or []
    if not isinstance(rows, list):
        return jsonify({"error": "Lista de valores inválida."}), 400
    return jsonify({"tabela_valores": save_wash_category_values(rows)})


@bp.post("/lavagens/sincronizar")
@auth_required
def sync_washes():
    denied = _guard_management_access()
    if denied:
        return denied
    return jsonify(sync_wash_queue(_wash_file()))


@bp.post("/lavagens/reclassificar")
@auth_required
def reclassify_washes():
    denied = _guard_management_access()
    if denied:
        return denied
    return jsonify(reclassify_wash_queue_categories())


@bp.post("/lavagens/registrar")
@auth_required
def create_wash_record():
    payload = request.get_json(silent=True) or {}
    queue_item_id = payload.get("queue_item_id")
    if not queue_item_id:
        return jsonify({"error": "Selecione um veiculo para registrar a lavagem."}), 400

    queue_item = WashQueueItem.query.get_or_404(queue_item_id)
    raw_date = str(payload.get("wash_date") or "").strip()
    try:
        wash_date = datetime.fromisoformat(raw_date) if raw_date else datetime.utcnow()
    except ValueError:
        return jsonify({"error": "Data da lavagem invalida."}), 400

    try:
        queue_item = register_wash(
            queue_item,
            wash_date=wash_date,
            location=payload.get("local"),
            value=payload.get("valor") if user_has_management_access(g.current_user) else None,
            carreta=payload.get("carreta"),
            category=payload.get("tipo_equipamento"),
            shift=payload.get("turno"),
            notes=payload.get("observacao"),
            photo_path=payload.get("foto_path"),
            user_id=g.current_user.id,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(queue_item.to_dict())


@bp.put("/lavagens/fila/<int:queue_item_id>/indisponivel")
@auth_required
def make_unavailable(queue_item_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    queue_item = WashQueueItem.query.get_or_404(queue_item_id)
    payload = request.get_json(silent=True) or {}
    queue_item = mark_unavailable(queue_item, payload.get("motivo"), g.current_user.id)
    return jsonify(queue_item.to_dict())


@bp.put("/lavagens/fila/<int:queue_item_id>/disponivel")
@auth_required
def make_available(queue_item_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    queue_item = WashQueueItem.query.get_or_404(queue_item_id)
    queue_item = release_unavailable(queue_item)
    return jsonify(queue_item.to_dict())


@bp.put("/lavagens/preventiva")
@auth_required
def schedule_preventive():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    queue_item_ids = payload.get("queue_item_ids") or []
    if not queue_item_ids:
        return jsonify({"error": "Selecione ao menos um veiculo para programar a preventiva."}), 400

    try:
        week_of_month = int(payload.get("week_of_month"))
        weekday = int(payload.get("weekday"))
    except (TypeError, ValueError):
        return jsonify({"error": "Semana ou dia da semana invalidos."}), 400

    queue_items = WashQueueItem.query.filter(WashQueueItem.id.in_(queue_item_ids)).all()
    if len(queue_items) != len(set(queue_item_ids)):
        return jsonify({"error": "Ha veiculos invalidos na selecao da preventiva."}), 400

    count = apply_preventive_schedule(
        queue_items,
        week_of_month=week_of_month,
        weekday=weekday,
        notes=payload.get("observacao"),
    )
    return jsonify({"updated": count})


@bp.put("/lavagens/plano")
@auth_required
def save_plan():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    try:
        year = int(payload.get("ano"))
        month = int(payload.get("mes"))
        morning_capacity = int(payload.get("capacidade_manha"))
        afternoon_capacity = int(payload.get("capacidade_tarde"))
        auxiliary_interval_days = int(payload.get("intervalo_auxiliares"))
    except (TypeError, ValueError):
        return jsonify({"error": "Parametros do planejamento invalidos."}), 400

    config = update_plan_config(
        year=year,
        month=month,
        morning_capacity=morning_capacity,
        afternoon_capacity=afternoon_capacity,
        auxiliary_interval_days=auxiliary_interval_days,
        notes=payload.get("observacao"),
    )
    return jsonify(config.to_dict())


@bp.put("/lavagens/plano/bloqueio")
@auth_required
def update_blocked_day():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    raw_date = str(payload.get("data") or "").strip()
    if not raw_date:
        return jsonify({"error": "Informe a data para o bloqueio da lavagem."}), 400

    try:
        selected_day = datetime.fromisoformat(raw_date).date()
        year = int(payload.get("ano") or selected_day.year)
        month = int(payload.get("mes") or selected_day.month)
    except (TypeError, ValueError):
        return jsonify({"error": "Data do bloqueio invalida."}), 400

    blocked = bool(payload.get("bloqueado", True))
    config = set_blocked_day(
        year=year,
        month=month,
        day_date=selected_day,
        shift=str(payload.get("turno") or "ALL"),
        blocked=blocked,
        reason=payload.get("motivo"),
    )
    return jsonify(config.to_dict())


@bp.get("/lavagens/mensagem-amanha")
@auth_required
def tomorrow_message():
    raw_date = request.args.get("data")
    if raw_date:
        try:
            reference_day = datetime.fromisoformat(raw_date).date()
        except ValueError:
            return jsonify({"error": "Data de referencia invalida."}), 400
    else:
        reference_day = None
    return jsonify(build_tomorrow_message_payload(reference_day))


@bp.put("/lavagens/cronograma/decisao")
@auth_required
def schedule_decision():
    payload = request.get_json(silent=True) or {}
    queue_item_id = payload.get("queue_item_id")
    if not queue_item_id:
        return jsonify({"error": "Selecione o item do cronograma."}), 400

    raw_date = str(payload.get("data") or "").strip()
    try:
        scheduled_date = datetime.fromisoformat(raw_date).date()
    except ValueError:
        return jsonify({"error": "Data do cronograma invalida."}), 400

    queue_item = WashQueueItem.query.get_or_404(queue_item_id)
    decision = mark_schedule_not_completed(
        queue_item=queue_item,
        scheduled_date=scheduled_date,
        shift=str(payload.get("turno") or "MANHA"),
        reason=payload.get("motivo"),
        user_id=g.current_user.id,
    )
    return jsonify(decision.to_dict())


@bp.put("/lavagens/cronograma/reeditar")
@auth_required
def schedule_reedit():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    queue_item_id = payload.get("queue_item_id")
    if not queue_item_id:
        return jsonify({"error": "Selecione o item do cronograma."}), 400

    raw_date = str(payload.get("data") or "").strip()
    try:
        scheduled_date = datetime.fromisoformat(raw_date).date()
    except ValueError:
        return jsonify({"error": "Data do cronograma invalida."}), 400

    queue_item = WashQueueItem.query.get_or_404(queue_item_id)
    shift = str(payload.get("turno") or "MANHA")
    current_status = str(payload.get("status_execucao") or "").upper()
    if current_status == "LAVADO":
        removed = reopen_completed_schedule_item(
            queue_item=queue_item,
            scheduled_date=scheduled_date,
            shift=shift,
        )
    else:
        removed = clear_schedule_decision(
            queue_item=queue_item,
            scheduled_date=scheduled_date,
            shift=shift,
        )
    return jsonify({"updated": 1 if removed else 0})

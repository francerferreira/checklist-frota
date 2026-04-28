from __future__ import annotations

from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models import Activity, ActivityItem, ActivityNonConformityLink, Material, User, Vehicle
from app.services.activity_link_service import (
    get_non_conformities_for_mass_activity,
    link_non_conformity_to_activity,
    normalize_item_key,
    normalize_modulo,
)
from app.services.auth_service import auth_required, user_has_management_access
from app.services.material_service import apply_activity_stock_change
from app.utils.filters import apply_item_search
from app.utils.responses import api_response

bp = Blueprint("activities", __name__)

# --- CONSTANTES DE ESTADO (Ponto 2: Controle de Estados) ---

class ActivityStatus:
    OPEN = "ABERTA"
    FINISHED = "FINALIZADA"

class ItemStatus:
    PENDING = "PENDENTE"
    INSTALLED = "INSTALADO"
    NOT_INSTALLED = "NAO_INSTALADO"
    
    @classmethod
    def all(cls):
        return {cls.PENDING, cls.INSTALLED, cls.NOT_INSTALLED}

# --- UTILITÁRIOS INTERNOS ---

def _guard_management_access():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar atividades.", status_code=403)
    return None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_material(material_id: int | None) -> Material | None:
    if not material_id:
        return None
    material = Material.query.get(material_id)
    if not material or not material.ativo:
        return None
    return material


def _effective_material(item: ActivityItem, activity: Activity) -> Material | None:
    return item.material or activity.material


def _effective_quantity(item: ActivityItem, activity: Activity) -> int:
    raw_value = item.quantidade_peca or activity.quantidade_por_equipamento or 1
    try:
        return max(1, int(raw_value))
    except (TypeError, ValueError):
        return 1


def _apply_item_material_payload(item: ActivityItem, activity: Activity, payload: dict):
    material_field_present = "material_id" in payload
    selected_material = item.material
    if material_field_present:
        raw_material_id = payload.get("material_id")
        if raw_material_id in ("", None, 0):
            selected_material = None
            item.material_id = None
        else:
            try:
                parsed_id = int(raw_material_id)
            except (TypeError, ValueError):
                raise ValueError("Material informado é inválido.")
            selected_material = _resolve_material(parsed_id)
            if not selected_material:
                raise ValueError("Material informado é inválido ou está inativo.")
            item.material_id = selected_material.id

    if "quantidade_peca" in payload or "quantidade_por_equipamento" in payload:
        raw_quantity = payload.get("quantidade_peca", payload.get("quantidade_por_equipamento"))
        try:
            item.quantidade_peca = max(1, int(raw_quantity or 1))
        except (TypeError, ValueError):
            raise ValueError("Quantidade de peça inválida.")

    if "codigo_peca" in payload:
        item.codigo_peca = _clean(payload.get("codigo_peca"))
    if "descricao_peca" in payload:
        item.descricao_peca = _clean(payload.get("descricao_peca"))

    if selected_material:
        if not item.codigo_peca:
            item.codigo_peca = selected_material.referencia
        if not item.descricao_peca:
            item.descricao_peca = selected_material.descricao
    elif material_field_present:
        item.codigo_peca = _clean(payload.get("codigo_peca"))
        item.descricao_peca = _clean(payload.get("descricao_peca"))

    if not item.quantidade_peca:
        item.quantidade_peca = max(1, int(activity.quantidade_por_equipamento or 1))


def _has_nc_origin_tag(activity: Activity) -> bool:
    observation = str(activity.observacao or "").upper()
    return "[ORIGEM:NC#" in observation


def _is_origin_photo_locked(activity: Activity, item: ActivityItem, *, linked_item_ids: set[int] | None = None) -> bool:
    source_type = str(activity.source_type or "").strip().upper()
    if source_type == "NC_ITEM":
        return True
    if _has_nc_origin_tag(activity):
        return True
    if linked_item_ids is not None:
        return item.id in linked_item_ids
    link_exists = ActivityNonConformityLink.query.filter_by(
        activity_id=activity.id,
        activity_item_id=item.id,
    ).first()
    return bool(link_exists)


def _serialize_activity(activity: Activity, *, include_items: bool = False) -> dict:
    payload = activity.to_dict(include_items=include_items)
    if not include_items:
        return payload

    links_by_item_id: dict[int, list[ActivityNonConformityLink]] = {}
    for link in activity.non_conformity_links or []:
        links_by_item_id.setdefault(link.activity_item_id, []).append(link)
    for item_links in links_by_item_id.values():
        item_links.sort(key=lambda link: link.linked_at or datetime.min, reverse=True)

    def origin_from_links(item_id: int) -> str | None:
        for link in links_by_item_id.get(item_id, []):
            checklist_item = link.checklist_item
            if checklist_item and checklist_item.foto_antes:
                return checklist_item.foto_antes
        return None

    linked_item_ids = {link.activity_item_id for link in (activity.non_conformity_links or [])}
    payload_by_id = {int(row.get("id")): row for row in payload.get("itens", []) if row.get("id") is not None}
    for item in activity.items:
        item_payload = payload_by_id.get(item.id)
        if not item_payload:
            continue
        origin_locked = _is_origin_photo_locked(activity, item, linked_item_ids=linked_item_ids)
        origin_photo = item_payload.get("foto_antes") or origin_from_links(item.id)
        if origin_photo and not item_payload.get("foto_antes"):
            # Compatibilidade com clientes legados que só leem foto_antes.
            item_payload["foto_antes"] = origin_photo
        item_payload["foto_origem"] = origin_photo
        item_payload["foto_resolucao"] = item_payload.get("foto_depois")
        item_payload["foto_origem_bloqueada"] = bool(origin_locked)
    return payload


def _activity_query():
    query = Activity.query.order_by(Activity.created_at.desc())
    tipo = request.args.get("tipo")
    status = request.args.get("status")
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

    query = apply_item_search(query, Activity, request.args.get("item"))
    return query


@bp.get("/atividades")
@auth_required
def list_activities():
    data = [activity.to_dict() for activity in _activity_query().all()]
    return api_response(True, data=data)


@bp.get("/atividades/<int:activity_id>")
@auth_required
def get_activity(activity_id: int):
    activity = Activity.query.get_or_404(activity_id)
    return api_response(True, data=_serialize_activity(activity, include_items=True))


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
        return api_response(False, error="Informe o modulo ou componente da atividade.", status_code=400)
    if not vehicle_ids:
        return api_response(False, error="Selecione ao menos um equipamento para a atividade.", status_code=400)

    vehicles = Vehicle.query.filter(Vehicle.id.in_(vehicle_ids)).order_by(Vehicle.frota.asc()).all()
    if len(vehicles) != len(set(vehicle_ids)):
        return api_response(False, error="Há equipamentos inválidos na seleção.", status_code=400)

    tipos = {vehicle.tipo for vehicle in vehicles}
    tipo_equipamento = payload.get("tipo_equipamento")
    if not tipo_equipamento:
        tipo_equipamento = tipos.pop() if len(tipos) == 1 else "misto"
    tipo_equipamento = str(tipo_equipamento).strip().lower() or "misto"

    titulo = _clean(payload.get("titulo")) or f"Troca em massa - {item_nome}"
    material_id = payload.get("material_id")
    material = None
    if material_id:
        material = Material.query.get(material_id)
        if not material or not material.ativo:
            return api_response(False, error="Material informado é inválido ou inativo.", status_code=400)

    try:
        quantidade_por_equipamento = max(1, int(payload.get("quantidade_por_equipamento") or 1))
    except (TypeError, ValueError):
        return api_response(False, error="Quantidade por equipamento inválida.", status_code=400)

    assigned_mechanic_id = payload.get("assigned_mechanic_user_id")
    assigned_mechanic = None
    if assigned_mechanic_id:
        assigned_mechanic = User.query.get(assigned_mechanic_id)
        if not assigned_mechanic or assigned_mechanic.tipo != "mecanico" or not assigned_mechanic.ativo:
            return api_response(False, error="Mecânico direcionado inválido ou inativo.", status_code=400)

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
                material_id=activity.material_id,
                quantidade_peca=activity.quantidade_por_equipamento,
                codigo_peca=activity.codigo_peca,
                descricao_peca=activity.descricao_peca,
                status_execucao=ItemStatus.PENDING,
            )
        )

    db.session.commit()
    return api_response(True, data=_serialize_activity(activity, include_items=True), status_code=201)


@bp.post("/atividades/nao_conformidades/lote")
@auth_required
def create_mass_activity_from_non_conformity_item():
    denied = _guard_management_access()
    if denied:
        return denied

    payload = request.get_json(silent=True) or {}
    item_nome = _clean(payload.get("item_nome"))
    if not item_nome:
        return api_response(False, error="Informe a não conformidade para abrir a atividade.", status_code=400)

    modulo = normalize_modulo(payload.get("modulo"))
    status_nc = (payload.get("status_nc") or "abertas").strip().lower()
    date_from = _clean(payload.get("date_from"))
    date_to = _clean(payload.get("date_to"))
    allow_duplicate = bool(payload.get("permitir_duplicada"))
    auto_link_nc = bool(payload.get("auto_link_nc", True))
    source_key = normalize_item_key(item_nome)

    existing_open = (
        Activity.query.filter_by(
            status=ActivityStatus.OPEN,
            source_type="NC_ITEM",
            source_key=source_key,
            source_modulo=modulo,
            auto_link_nc=auto_link_nc,
        )
        .order_by(Activity.created_at.desc())
        .first()
    )
    if existing_open and not allow_duplicate:
        err = (f"Já existe atividade em massa aberta para {source_key}: #{existing_open.id}. "
               "Finalize a atividade atual ou confirme abertura duplicada.")
        return api_response(False, error=err, status_code=409)

    selected_non_conformities = get_non_conformities_for_mass_activity(
        item_name=item_nome,
        modulo=modulo,
        status_nc=status_nc,
        date_from=date_from,
        date_to=date_to,
    )
    if not selected_non_conformities:
        return api_response(False, error="Nenhuma não conformidade encontrada.", status_code=404)

    vehicle_map: dict[int, str | None] = {}
    for checklist_item in selected_non_conformities:
        vehicle = checklist_item.checklist.vehicle if checklist_item.checklist else None
        if vehicle:
            vehicle_map[vehicle.id] = vehicle.tipo
    if not vehicle_map:
        return api_response(False, error="Não foi possível identificar equipamentos válidos.", status_code=400)

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

    vehicle_types = {str(tipo or "").strip().lower() for tipo in vehicle_map.values()}
    if modulo in {"cavalo", "carreta"}:
        tipo_equipamento = modulo
    else:
        tipo_equipamento = vehicle_types.pop() if len(vehicle_types) == 1 and vehicle_types else "misto"

    titulo = _clean(payload.get("titulo")) or f"Tratativa em massa - {source_key}"
    context_lines = [
            f"Origem: Relatório por não conformidade ({source_key})",
            f"Escopo: módulo={modulo}, status={status_nc}",
        ]
    if auto_link_nc:
        context_lines.append("Auto vínculo: novas NC do mesmo item serão anexadas automaticamente enquanto a atividade estiver aberta.")
    if date_from or date_to:
        context_lines.append(f"Período: {date_from or '-'} até {date_to or '-'}")
    user_observation = _clean(payload.get("observacao"))
    if user_observation:
        context_lines.insert(0, user_observation)

    activity = Activity(
        titulo=titulo,
        item_nome=source_key,
        tipo_equipamento=tipo_equipamento,
        source_type="NC_ITEM",
        source_key=source_key,
        source_modulo=modulo,
        auto_link_nc=auto_link_nc,
        material_id=material.id if material else None,
        quantidade_por_equipamento=quantidade_por_equipamento,
        codigo_peca=_clean(payload.get("codigo_peca")) or (material.referencia if material else None),
        descricao_peca=_clean(payload.get("descricao_peca")) or (material.descricao if material else None),
        fornecedor_peca=_clean(payload.get("fornecedor_peca")),
        lote_peca=_clean(payload.get("lote_peca")),
        observacao="\n".join(context_lines),
        created_by_user_id=g.current_user.id,
        assigned_mechanic_user_id=assigned_mechanic.id if assigned_mechanic else None,
    )
    db.session.add(activity)
    db.session.flush()

    for vehicle_id in sorted(vehicle_map):
        db.session.add(
            ActivityItem(
                activity_id=activity.id,
                vehicle_id=vehicle_id,
                material_id=activity.material_id,
                quantidade_peca=activity.quantidade_por_equipamento,
                codigo_peca=activity.codigo_peca,
                descricao_peca=activity.descricao_peca,
                status_execucao=ItemStatus.PENDING,
            )
        )
    db.session.flush()

    linked_total = 0
    for checklist_item in selected_non_conformities:
        if link_non_conformity_to_activity(activity, checklist_item, mode="MANUAL"):
            linked_total += 1

    db.session.commit()
    response = _serialize_activity(activity, include_items=True)
    response["nao_conformidades_iniciais"] = int(linked_total)
    response["equipamentos_iniciais"] = int(len(vehicle_map))
    return api_response(True, data=response, status_code=201)


@bp.put("/atividades/<int:activity_id>/itens/<int:item_id>")
@auth_required
def update_activity_item(activity_id: int, item_id: int):
    activity = Activity.query.get_or_404(activity_id)
    item = ActivityItem.query.filter_by(id=item_id, activity_id=activity.id).first_or_404()
    payload = request.get_json(silent=True) or {}
    material_fields = {"material_id", "quantidade_peca", "quantidade_por_equipamento", "codigo_peca", "descricao_peca"}
    material_payload_present = any(field in payload for field in material_fields)
    if material_payload_present and not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem editar material.", status_code=403)

    previous_status = item.status_execucao
    previous_material = _effective_material(item, activity)
    previous_quantity = _effective_quantity(item, activity)

    status_execucao = str(payload.get("status_execucao") or item.status_execucao).strip().upper()
    if status_execucao not in ItemStatus.all():
        return api_response(False, error="Status da atividade inválido.", status_code=400)

    try:
        _apply_item_material_payload(item, activity, payload)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)

    next_material = _effective_material(item, activity)
    next_quantity = _effective_quantity(item, activity)
    if (
        previous_status == ItemStatus.INSTALLED
        and status_execucao == ItemStatus.INSTALLED
        and (
            (previous_material.id if previous_material else None) != (next_material.id if next_material else None)
            or previous_quantity != next_quantity
        )
    ):
        return api_response(False, error="Altere o status para pendente antes de trocar o material instalado.", status_code=400)

    item.status_execucao = status_execucao
    item.observacao = _clean(payload.get("observacao")) or item.observacao
    linked_item_ids = {link.activity_item_id for link in (activity.non_conformity_links or [])}
    origin_photo_locked = _is_origin_photo_locked(activity, item, linked_item_ids=linked_item_ids)
    requested_origin_photo = _clean(payload.get("foto_antes")) if "foto_antes" in payload else None
    origin_photo_preserved = bool(
        origin_photo_locked
        and requested_origin_photo
        and requested_origin_photo != (item.foto_antes or "")
    )
    if not origin_photo_locked:
        item.foto_antes = _clean(payload.get("foto_antes")) or item.foto_antes
    item.foto_depois = _clean(payload.get("foto_depois")) or item.foto_depois
    if status_execucao == ItemStatus.PENDING:
        item.instalado_em = None
        item.executado_por_nome = None
        item.executado_por_login = None
    else:
        item.instalado_em = datetime.utcnow()
        item.executado_por_nome = g.current_user.nome
        item.executado_por_login = g.current_user.login

    try:
        material_for_movement = next_material if status_execucao == ItemStatus.INSTALLED else previous_material
        quantity_for_movement = next_quantity if status_execucao == ItemStatus.INSTALLED else previous_quantity
        apply_activity_stock_change(
            material_for_movement,
            previous_status=previous_status,
            new_status=status_execucao,
            quantity_per_equipment=quantity_for_movement,
            activity_id=activity.id,
            vehicle_label=item.vehicle.frota if item.vehicle else "equipamento",
        )
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)

    resumo = activity.summary()
    all_done = resumo["pendentes"] == 0
    activity.status = ActivityStatus.FINISHED if all_done else ActivityStatus.OPEN
    activity.finalized_at = datetime.utcnow() if all_done else None

    db.session.commit()
    response = _serialize_activity(activity, include_items=True)
    if origin_photo_preserved:
        response["aviso_foto_origem_preservada"] = True
        response["mensagem_foto_origem"] = "Evidência de origem preservada. Use foto de resolução para a tratativa."
    return api_response(True, data=response)


@bp.put("/atividades/<int:activity_id>/materiais")
@auth_required
def update_activity_item_materials(activity_id: int):
    denied = _guard_management_access()
    if denied:
        return denied

    activity = Activity.query.get_or_404(activity_id)
    payload = request.get_json(silent=True) or {}
    material_fields = {"material_id", "quantidade_peca", "quantidade_por_equipamento", "codigo_peca", "descricao_peca"}
    if not any(field in payload for field in material_fields):
        return api_response(False, error="Informe ao menos um campo de material para atualizar.", status_code=400)

    apply_to_all = bool(payload.get("apply_to_all"))
    item_ids = payload.get("activity_item_ids") or []
    if apply_to_all:
        target_items = ActivityItem.query.filter_by(activity_id=activity.id).all()
    else:
        if not item_ids:
            return api_response(False, error="Selecione ao menos um equipamento para atualizar material.", status_code=400)
        try:
            unique_ids = sorted({int(item_id) for item_id in item_ids if str(item_id).strip()})
        except (TypeError, ValueError):
            return api_response(False, error="Há equipamentos inválidos na seleção de materiais.", status_code=400)
        if not unique_ids:
            return api_response(False, error="Selecione ao menos um equipamento para atualizar material.", status_code=400)
        target_items = ActivityItem.query.filter(
            ActivityItem.activity_id == activity.id,
            ActivityItem.id.in_(unique_ids),
        ).all()
        if len(target_items) != len(unique_ids):
            return api_response(False, error="Há equipamentos inválidos na seleção de materiais.", status_code=400)

    if not target_items:
        return api_response(False, error="Selecione ao menos um equipamento para atualizar material.", status_code=400)

    if any((item.status_execucao or "").upper() == "INSTALADO" for item in target_items):
        return api_response(False, error="Não é permitido alterar material de item já instalado.", status_code=400)

    try:
        for item in target_items:
            _apply_item_material_payload(item, activity, payload)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)

    if apply_to_all:
        if "material_id" in payload:
            activity.material_id = target_items[0].material_id
        if "quantidade_peca" in payload or "quantidade_por_equipamento" in payload:
            activity.quantidade_por_equipamento = target_items[0].quantidade_peca
        if "codigo_peca" in payload:
            activity.codigo_peca = target_items[0].codigo_peca
        if "descricao_peca" in payload:
            activity.descricao_peca = target_items[0].descricao_peca

    db.session.commit()
    response = _serialize_activity(activity, include_items=True)
    response["itens_atualizados"] = len(target_items)
    return api_response(True, data=response)

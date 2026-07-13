from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.models import (
    EquipmentFamily, InspectionExecution, InspectionExecutionItem,
    InspectionTemplate, InspectionTemplateItem, MechanicNonConformity, Vehicle,
)
from app.utils.timezone import now_manaus_naive


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _template_items(payload_items: list) -> list[InspectionTemplateItem]:
    if not isinstance(payload_items, list) or not payload_items:
        raise ValueError("Informe ao menos um item no template tecnico.")
    result = []
    for position, payload in enumerate(payload_items, start=1):
        label = _clean(payload.get("label")) if isinstance(payload, dict) else None
        if not label:
            raise ValueError(f"Informe o nome do item na posicao {position}.")
        response_type = str(payload.get("response_type") or "STATUS").strip().upper()
        if response_type not in {"STATUS", "TEXTO", "NUMERO"}:
            raise ValueError(f"Tipo de resposta invalido no item {label}.")
        minimum = payload.get("minimum_value")
        maximum = payload.get("maximum_value")
        try:
            minimum = Decimal(str(minimum)) if minimum not in (None, "") else None
            maximum = Decimal(str(maximum)) if maximum not in (None, "") else None
        except InvalidOperation as exc:
            raise ValueError(f"Faixa numerica invalida no item {label}.") from exc
        if minimum is not None and maximum is not None and maximum < minimum:
            raise ValueError(f"Faixa numerica invertida no item {label}.")
        result.append(InspectionTemplateItem(
            category=_clean(payload.get("category")), label=label, position=position,
            required=bool(payload.get("required", True)), response_type=response_type,
            unit=_clean(payload.get("unit")), minimum_value=minimum, maximum_value=maximum,
            evidence_on_nc=bool(payload.get("evidence_on_nc", True)), active=True,
        ))
    return result


def create_template(payload: dict, user_id: int) -> InspectionTemplate:
    try:
        family_id = int(payload.get("family_id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Familia de equipamento invalida.") from exc
    family = db.session.get(EquipmentFamily, family_id)
    if not family or not family.active:
        raise ValueError("Familia de equipamento nao encontrada.")
    code = str(payload.get("code") or "").strip().upper()
    name = _clean(payload.get("name"))
    if not code or not name:
        raise ValueError("Informe codigo e nome do template.")
    if InspectionTemplate.query.filter_by(family_id=family_id, code=code).first():
        raise ValueError("Ja existe template com este codigo para a familia.")
    template = InspectionTemplate(
        family_id=family_id, code=code, name=name, version=1, status="RASCUNHO",
        instructions=_clean(payload.get("instructions")), created_by_user_id=user_id,
    )
    template.items = _template_items(payload.get("items") or [])
    db.session.add(template)
    db.session.commit()
    return template


def update_template(template_id: int, payload: dict) -> InspectionTemplate:
    template = db.session.get(InspectionTemplate, template_id)
    if not template:
        raise LookupError("Template nao encontrado.")
    if template.status != "RASCUNHO":
        raise ValueError("Somente templates em rascunho podem ser alterados.")
    if _clean(payload.get("name")):
        template.name = _clean(payload.get("name"))
    if "instructions" in payload:
        template.instructions = _clean(payload.get("instructions"))
    if "items" in payload:
        template.items = _template_items(payload.get("items") or [])
    db.session.commit()
    return template


def publish_template(template_id: int) -> InspectionTemplate:
    template = db.session.get(InspectionTemplate, template_id)
    if not template:
        raise LookupError("Template nao encontrado.")
    if template.status != "RASCUNHO":
        raise ValueError("O template nao esta em rascunho.")
    if not any(item.active for item in template.items):
        raise ValueError("O template precisa ter itens ativos.")
    previous = InspectionTemplate.query.filter_by(
        family_id=template.family_id, code=template.code, status="PUBLICADO"
    ).all()
    for item in previous:
        item.status = "ARQUIVADO"
    template.status = "PUBLICADO"
    template.published_at = now_manaus_naive()
    db.session.commit()
    return template


def create_new_version(template_id: int, user_id: int) -> InspectionTemplate:
    source = db.session.get(InspectionTemplate, template_id)
    if not source:
        raise LookupError("Template nao encontrado.")
    draft = InspectionTemplate.query.filter_by(
        family_id=source.family_id, code=source.code, status="RASCUNHO"
    ).first()
    if draft:
        raise ValueError("Ja existe uma nova versao em rascunho.")
    latest_version = db.session.query(db.func.max(InspectionTemplate.version)).filter_by(
        family_id=source.family_id, code=source.code
    ).scalar() or 0
    template = InspectionTemplate(
        family_id=source.family_id, code=source.code, name=source.name,
        version=int(latest_version) + 1, status="RASCUNHO", instructions=source.instructions,
        created_by_user_id=user_id,
    )
    template.items = [InspectionTemplateItem(
        category=item.category, label=item.label, position=item.position, required=item.required,
        response_type=item.response_type, unit=item.unit, minimum_value=item.minimum_value,
        maximum_value=item.maximum_value, evidence_on_nc=item.evidence_on_nc, active=item.active,
    ) for item in source.items]
    db.session.add(template)
    db.session.commit()
    return template


def list_templates(*, include_all: bool, vehicle_id: int | None = None) -> list[dict]:
    query = InspectionTemplate.query
    if vehicle_id:
        vehicle = db.session.get(Vehicle, vehicle_id)
        if not vehicle or not vehicle.ativo:
            raise LookupError("Equipamento ativo nao encontrado.")
        profile = vehicle.equipment_profile
        if not profile:
            return []
        query = query.filter_by(family_id=profile.family_id, status="PUBLICADO")
    elif not include_all:
        query = query.filter_by(status="PUBLICADO")
    rows = query.order_by(InspectionTemplate.name.asc(), InspectionTemplate.version.desc()).all()
    return [row.to_dict() for row in rows]


def create_execution(payload: dict, user_id: int) -> InspectionExecution:
    try:
        template_id = int(payload.get("template_id"))
        vehicle_id = int(payload.get("vehicle_id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Template ou equipamento invalido.") from exc
    template = db.session.get(InspectionTemplate, template_id)
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not template or template.status != "PUBLICADO":
        raise ValueError("Template publicado nao encontrado.")
    if not vehicle or not vehicle.ativo or not vehicle.equipment_profile:
        raise ValueError("Equipamento ativo e unificado nao encontrado.")
    if vehicle.equipment_profile.family_id != template.family_id:
        raise ValueError("O template nao pertence a familia deste equipamento.")
    payload_items = payload.get("items") or []
    supplied = {int(item.get("template_item_id")): item for item in payload_items if item.get("template_item_id")}
    execution = InspectionExecution(
        template_id=template.id, template_version=template.version, vehicle_id=vehicle.id,
        user_id=user_id, status="CONCLUIDA", result="CONFORME",
        general_notes=_clean(payload.get("general_notes")), started_at=now_manaus_naive(),
        completed_at=now_manaus_naive(),
    )
    for template_item in (item for item in template.items if item.active):
        answer = supplied.get(template_item.id)
        if not answer and template_item.required:
            raise ValueError(f"Responda o item obrigatorio: {template_item.label}.")
        if not answer:
            continue
        status = str(answer.get("status") or "").upper() or None
        value_text = _clean(answer.get("value_text"))
        value_number = None
        if template_item.response_type == "STATUS":
            if status not in {"OK", "NC", "NA"}:
                raise ValueError(f"Situacao invalida no item {template_item.label}.")
            if status == "NC":
                execution.result = "NAO_CONFORME"
                if not _clean(answer.get("observation")):
                    raise ValueError(f"Informe a observacao da NC: {template_item.label}.")
                if template_item.evidence_on_nc and not _clean(answer.get("evidence_path")):
                    raise ValueError(f"Anexe evidencia da NC: {template_item.label}.")
        elif template_item.response_type == "TEXTO":
            if template_item.required and not value_text:
                raise ValueError(f"Informe a resposta: {template_item.label}.")
        else:
            try:
                value_number = Decimal(str(answer.get("value_number")))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValueError(f"Informe valor numerico: {template_item.label}.") from exc
            if template_item.minimum_value is not None and value_number < template_item.minimum_value:
                execution.result = "NAO_CONFORME"
            if template_item.maximum_value is not None and value_number > template_item.maximum_value:
                execution.result = "NAO_CONFORME"
        execution.items.append(InspectionExecutionItem(
            template_item_id=template_item.id, item_label=template_item.label,
            response_type=template_item.response_type, status=status, value_text=value_text,
            value_number=value_number, observation=_clean(answer.get("observation")),
            evidence_path=_clean(answer.get("evidence_path")),
        ))
    db.session.add(execution)
    db.session.flush()
    for item in execution.items:
        if item.status != "NC":
            continue
        nc = MechanicNonConformity(
            created_by_user_id=user_id,
            veiculo_referencia=vehicle.frota or vehicle.placa,
            item_nome=item.item_label,
            observacao=f"[ORIGEM:INSPECAO_TECNICA#{execution.id}] {item.observation or ''}".strip(),
            foto_antes=item.evidence_path,
            resolvido=False,
        )
        db.session.add(nc)
        db.session.flush()
        item.generated_non_conformity_id = nc.id
    db.session.commit()
    return execution


def list_executions(*, vehicle_id: int | None = None, limit: int = 100) -> list[dict]:
    query = InspectionExecution.query.order_by(InspectionExecution.completed_at.desc())
    if vehicle_id:
        query = query.filter_by(vehicle_id=vehicle_id)
    return [row.to_dict(include_items=False) for row in query.limit(min(limit, 500)).all()]

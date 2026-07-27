from __future__ import annotations

from flask import Blueprint, g, request
from sqlalchemy import or_

from app.extensions import db
from app.models import AutomationExecution, Employee, Material, UserNavigationPreference, Vehicle
from app.services.auth_service import auth_required, user_has_management_access
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive


bp = Blueprint("navigation", __name__)

ROLE_PAGES = {
    "admin": {"dashboard", "operations_center", "nc", "productivity", "reports", "checklist_history", "spreader_history", "equipment", "checklist_items", "inspection_templates", "materials", "washes", "activities", "maintenance", "availability", "emergencies", "pcm", "resources", "purchases", "supply_library", "employees", "attendance", "employee_records", "hr_management", "vacations", "special_schedule", "users", "cloud_backup", "audit_logs", "admin_rules"},
    "gestor": {"dashboard", "operations_center", "nc", "productivity", "reports", "checklist_history", "spreader_history", "equipment", "checklist_items", "inspection_templates", "materials", "washes", "activities", "maintenance", "availability", "emergencies", "pcm", "resources", "purchases", "supply_library", "employees", "attendance", "employee_records", "hr_management", "vacations", "special_schedule", "admin_rules"},
    "mecanico": {"dashboard", "operations_center", "nc", "productivity", "activities", "maintenance", "availability", "emergencies"},
    "operacional": {"dashboard", "operations_center", "nc", "productivity", "activities", "maintenance", "availability", "emergencies"},
    "motorista": {"dashboard"},
}

PAGE_LABELS = {
    "dashboard": "Dashboard",
    "operations_center": "Central Operacional",
    "nc": "Central de Resolucao",
    "productivity": "Produtividade",
    "reports": "Relatorios",
    "checklist_history": "Historico Checklist",
    "spreader_history": "Historico de Spreaders",
    "equipment": "Equipamentos",
    "checklist_items": "Checklist",
    "inspection_templates": "Templates Tecnicos",
    "materials": "Materiais",
    "washes": "Lavagens",
    "activities": "Inspecoes",
    "maintenance": "Manutencao",
    "availability": "Disponibilidade",
    "emergencies": "Emergenciais e OS",
    "pcm": "PCM",
    "resources": "Recursos e ferramentas",
    "purchases": "Compras e fornecedores",
    "supply_library": "Suprimentos e Biblioteca",
    "employees": "Recursos Humanos",
    "attendance": "Frequencia e ocorrencias",
    "employee_records": "Documentos e treinamentos",
    "hr_management": "Painel de RH",
    "vacations": "Ferias",
    "special_schedule": "Escala de Domingo e Feriado",
    "users": "Logins",
    "cloud_backup": "Backup",
    "audit_logs": "Logs de Auditoria",
    "admin_rules": "Configuracao Administrativa",
}


def _allowed_page(page_key: str) -> bool:
    role = str(g.current_user.tipo or "").strip().lower()
    return page_key in ROLE_PAGES.get(role, {"dashboard"})


def _preference(page_key: str) -> UserNavigationPreference:
    if not _allowed_page(page_key):
        raise PermissionError("Tela não permitida para este perfil.")
    row = UserNavigationPreference.query.filter_by(user_id=g.current_user.id, page_key=page_key).first()
    if not row:
        row = UserNavigationPreference(user_id=g.current_user.id, page_key=page_key)
        db.session.add(row)
    return row


def _result(*, kind: str, entity_id: int | None, title: str, subtitle: str, page_key: str) -> dict:
    return {"kind": kind, "entity_id": entity_id, "title": title, "subtitle": subtitle, "page_key": page_key}


@bp.get("/navegacao/preferencias")
@auth_required
def get_navigation_preferences():
    rows = UserNavigationPreference.query.filter_by(user_id=g.current_user.id).all()
    allowed = [row for row in rows if _allowed_page(row.page_key)]
    favorites = sorted((row.to_dict() for row in allowed if row.is_favorite), key=lambda row: row["page_key"])
    recent = sorted((row.to_dict() for row in allowed if row.last_accessed_at), key=lambda row: row["last_accessed_at"], reverse=True)[:6]
    return api_response(True, data={"favorites": favorites, "recent": recent})


@bp.get("/navegacao/busca-global")
@auth_required
def global_search():
    term = str(request.args.get("q") or "").strip()
    if len(term) < 2:
        return api_response(False, error="Informe ao menos 2 caracteres para a busca.", status_code=400)
    if len(term) > 80:
        return api_response(False, error="A busca pode ter no maximo 80 caracteres.", status_code=400)
    limit = min(max(request.args.get("limite", default=20, type=int) or 20, 1), 50)
    pattern = f"%{term}%"
    role = str(g.current_user.tipo or "").strip().lower()
    allowed = ROLE_PAGES.get(role, {"dashboard"})
    results: list[dict] = []

    for page_key in sorted(allowed):
        page_label = PAGE_LABELS.get(page_key, page_key.replace("_", " ").title())
        if term.lower() in page_label.lower():
            results.append(_result(kind="TELA", entity_id=None, title=page_label, subtitle="Abrir tela do sistema", page_key=page_key))

    if "equipment" in allowed:
        rows = Vehicle.query.filter(or_(Vehicle.frota.ilike(pattern), Vehicle.placa.ilike(pattern), Vehicle.modelo.ilike(pattern), Vehicle.chassi.ilike(pattern))).order_by(Vehicle.frota.asc()).limit(limit).all()
        results.extend(_result(kind="EQUIPAMENTO", entity_id=row.id, title=f"{row.frota} - {row.modelo}", subtitle=f"Placa: {row.placa}", page_key="equipment") for row in rows)

    if "materials" in allowed:
        rows = Material.query.filter(or_(Material.referencia.ilike(pattern), Material.descricao.ilike(pattern))).order_by(Material.referencia.asc()).limit(limit).all()
        results.extend(_result(kind="MATERIAL", entity_id=row.id, title=f"{row.referencia} - {row.descricao}", subtitle=f"Estoque: {row.quantidade_estoque}", page_key="materials") for row in rows)

    if "employees" in allowed and user_has_management_access(g.current_user):
        rows = Employee.query.filter(or_(Employee.registration.ilike(pattern), Employee.full_name.ilike(pattern), Employee.function_name.ilike(pattern))).order_by(Employee.full_name.asc()).limit(limit).all()
        results.extend(_result(kind="COLABORADOR", entity_id=row.id, title=f"{row.registration} - {row.full_name}", subtitle=f"{row.function_name} | {row.team_name}", page_key="employees") for row in rows)

    if "dashboard" in allowed and user_has_management_access(g.current_user):
        rows = AutomationExecution.query.filter(AutomationExecution.status.in_({"ATIVO", "RECONHECIDO"}), AutomationExecution.message.ilike(pattern)).order_by(AutomationExecution.evaluated_at.desc()).limit(limit).all()
        for row in rows:
            target = {"MATERIAL": "materials", "PREVENTIVE_PLAN": "pcm", "EMERGENCY_EVENT": "emergencies"}.get(row.entity_type, "dashboard")
            if target in allowed:
                results.append(_result(kind="ALERTA", entity_id=row.entity_id, title=row.message, subtitle=f"{row.severity} | {row.entity_type}", page_key=target))

    return api_response(True, data=results[:limit])


@bp.put("/navegacao/paginas/<string:page_key>/favorito")
@auth_required
def toggle_navigation_favorite(page_key: str):
    try:
        row = _preference(page_key)
    except PermissionError as exc:
        return api_response(False, error=str(exc), status_code=403)
    row.is_favorite = not row.is_favorite
    db.session.commit()
    return api_response(True, data=row.to_dict())


@bp.post("/navegacao/paginas/<string:page_key>/acessar")
@auth_required
def register_navigation_access(page_key: str):
    try:
        row = _preference(page_key)
    except PermissionError as exc:
        return api_response(False, error=str(exc), status_code=403)
    row.access_count = (row.access_count or 0) + 1
    row.last_accessed_at = now_manaus_naive()
    db.session.commit()
    return api_response(True, data=row.to_dict())

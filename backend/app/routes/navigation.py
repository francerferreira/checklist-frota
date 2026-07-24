from __future__ import annotations

from flask import Blueprint, g

from app.extensions import db
from app.models import UserNavigationPreference
from app.services.auth_service import auth_required
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive


bp = Blueprint("navigation", __name__)

ROLE_PAGES = {
    "admin": {"dashboard", "operations_center", "nc", "productivity", "reports", "checklist_history", "equipment", "checklist_items", "inspection_templates", "materials", "washes", "activities", "maintenance", "availability", "emergencies", "pcm", "resources", "purchases", "supply_library", "employees", "attendance", "employee_records", "users", "cloud_backup", "audit_logs", "admin_rules"},
    "gestor": {"dashboard", "operations_center", "nc", "productivity", "reports", "checklist_history", "equipment", "checklist_items", "inspection_templates", "materials", "washes", "activities", "maintenance", "availability", "emergencies", "pcm", "resources", "purchases", "supply_library", "employees", "attendance", "employee_records", "admin_rules"},
    "mecanico": {"dashboard", "operations_center", "nc", "productivity", "activities", "maintenance", "availability", "emergencies"},
    "motorista": {"dashboard"},
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


@bp.get("/navegacao/preferencias")
@auth_required
def get_navigation_preferences():
    rows = UserNavigationPreference.query.filter_by(user_id=g.current_user.id).all()
    allowed = [row for row in rows if _allowed_page(row.page_key)]
    favorites = sorted((row.to_dict() for row in allowed if row.is_favorite), key=lambda row: row["page_key"])
    recent = sorted((row.to_dict() for row in allowed if row.last_accessed_at), key=lambda row: row["last_accessed_at"], reverse=True)[:6]
    return api_response(True, data={"favorites": favorites, "recent": recent})


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

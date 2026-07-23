from __future__ import annotations

from collections.abc import Mapping


PAGE_ACCESS_BY_ROLE = {
    "admin": {
        "dashboard",
        "operations_center",
        "nc",
        "productivity",
        "reports",
        "checklist_history",
        "equipment",
        "checklist_items",
        "inspection_templates",
        "materials",
        "washes",
        "activities",
        "maintenance",
        "availability",
        "emergencies",
        "pcm",
        "resources",
        "supply_library",
        "users",
        "cloud_backup",
        "audit_logs",
        "admin_rules",
    },
    "gestor": {
        "dashboard",
        "operations_center",
        "nc",
        "productivity",
        "reports",
        "checklist_history",
        "equipment",
        "checklist_items",
        "inspection_templates",
        "materials",
        "washes",
        "activities",
        "maintenance",
        "availability",
        "emergencies",
        "pcm",
        "resources",
        "supply_library",
        "admin_rules",
    },
    "mecanico": {
        "dashboard",
        "operations_center",
        "nc",
        "productivity",
        "activities",
        "maintenance",
        "availability",
        "emergencies",
    },
    "motorista": {
        "dashboard",
    },
}


ACTION_ACCESS_BY_ROLE = {
    "manage_users": {"admin"},
    "manage_activity_materials": {"admin", "gestor"},
    "view_wash_values": {"admin", "gestor"},
    "manage_wash_values": {"admin", "gestor"},
}


def normalize_user_role(user: Mapping[str, object] | None) -> str:
    return str((user or {}).get("tipo") or "").strip().lower()


def allowed_pages_for_role(role: str) -> set[str]:
    normalized_role = str(role or "").strip().lower()
    return set(PAGE_ACCESS_BY_ROLE.get(normalized_role, {"dashboard"}))


def user_can_access_page(user: Mapping[str, object] | None, page_key: str) -> bool:
    return page_key in allowed_pages_for_role(normalize_user_role(user))


def role_can(role: str, permission_key: str) -> bool:
    normalized_role = str(role or "").strip().lower()
    return normalized_role in ACTION_ACCESS_BY_ROLE.get(permission_key, set())


def user_can(user: Mapping[str, object] | None, permission_key: str) -> bool:
    return role_can(normalize_user_role(user), permission_key)

from __future__ import annotations

import re
import unicodedata

from app.extensions import db
from app.models import Employee, User


MANAGER_MARKERS = ("COORDENADOR", "SUPERVISOR", "ESPECIALISTA", "ANALISTA")
OPERATIONAL_MARKERS = ("MECANICO", "MECÂNICO", "TEC ", "TÉC", "TECNICO", "TÉCNICO", "ELETRICISTA", "ELETROMEC")


def normalize_login(value: str | None) -> str:
    """Normaliza login para aceitar maiúsculas/minúsculas e acentos."""
    raw = unicodedata.normalize("NFKD", str(value or ""))
    raw = "".join(char for char in raw if not unicodedata.combining(char))
    raw = raw.lower().strip()
    raw = re.sub(r"[^a-z0-9_.-]+", "", raw)
    return raw[:80]


def employee_user_type(function_name: str | None) -> str:
    value = unicodedata.normalize("NFKD", str(function_name or "")).upper()
    value = "".join(char for char in value if not unicodedata.combining(char))
    if any(marker in value for marker in MANAGER_MARKERS):
        return "gestor"
    if any(marker in value for marker in OPERATIONAL_MARKERS):
        return "operacional"
    return "operacional"


def _first_name_login(full_name: str, registration: str, used: set[str]) -> str:
    first_name = normalize_login((full_name or "").split()[0] if full_name else "colaborador") or "colaborador"
    candidate = first_name
    if candidate in {"admin", "francer"} or candidate in used:
        candidate = f"{first_name}_{normalize_login(registration) or 'colaborador'}"
    counter = 2
    while candidate in used or candidate in {"admin", "francer"}:
        candidate = f"{first_name}_{normalize_login(registration) or counter}"
        counter += 1
    return candidate


def provision_employee_users() -> dict:
    """Vincula cada colaborador ativo a um usuário sem duplicar vínculos."""
    admin = User.query.filter_by(login="admin").first()
    if not admin:
        admin = User(nome="Administrador", login="admin", tipo="admin", ativo=True)
        db.session.add(admin)
    admin.nome = "Administrador"
    admin.tipo = "admin"
    admin.ativo = True
    admin.set_password("admin")
    db.session.flush()

    used = {normalize_login(user.login) for user in User.query.all() if user.login}
    created = 0
    linked = 0
    employees = Employee.query.filter(Employee.status != "INATIVO").order_by(Employee.id.asc()).all()
    for employee in employees:
        # O login histórico do responsável pelo sistema deve continuar sendo
        # o vínculo do colaborador Francer, sem criar um segundo usuário.
        first_name = normalize_login((employee.full_name or "").split()[0] if employee.full_name else "")
        if first_name == "francer":
            legacy_francer = User.query.filter_by(login="francer").first()
            if legacy_francer and not legacy_francer.employee:
                legacy_francer.tipo = "admin"
                legacy_francer.ativo = True
                if not employee.first_access_completed_at:
                    legacy_francer.set_password(str(employee.registration).strip())
                employee.user_id = legacy_francer.id
                generated_francer = User.query.filter_by(login=f"francer_{normalize_login(employee.registration)}").first()
                if generated_francer and generated_francer.id != legacy_francer.id:
                    db.session.delete(generated_francer)
                used.add("francer")
                linked += 1
                continue
        if employee.user_id and employee.user:
            if first_name == "francer" and employee.user.login == "francer" and not employee.first_access_completed_at:
                employee.user.set_password(str(employee.registration).strip())
            used.add(normalize_login(employee.user.login))
            continue
        login = _first_name_login(employee.full_name, employee.registration, used)
        user = User(
            nome=employee.full_name,
            login=login,
            tipo=employee_user_type(employee.function_name),
            ativo=True,
        )
        user.set_password(str(employee.registration).strip())
        db.session.add(user)
        db.session.flush()
        employee.user_id = user.id
        used.add(login)
        created += 1
        linked += 1
    db.session.commit()
    return {"created": created, "linked": linked, "employees": len(employees)}

from __future__ import annotations

from datetime import date

from flask import Blueprint, g, request
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Employee, User
from app.models.employee import EMPLOYEE_STATUSES
from app.services.auth_service import auth_required, user_has_management_access
from app.services.audit_service import record_event
from app.utils.responses import api_response


bp = Blueprint("employees", __name__)


def _guard_hr_management():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar colaboradores.", status_code=403)
    return None


def _clean(value) -> str | None:
    value = str(value or "").strip()
    return value or None


def _parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Data de admissao invalida.") from exc


def _parse_user_id(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        user_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Login vinculado invalido.") from exc
    if not db.session.get(User, user_id):
        raise ValueError("Login vinculado nao encontrado.")
    return user_id


def _employee_payload(payload: dict) -> dict:
    registration = _clean(payload.get("registration"))
    full_name = _clean(payload.get("full_name"))
    function_name = _clean(payload.get("function_name"))
    team_name = _clean(payload.get("team_name"))
    shift_name = _clean(payload.get("shift_name"))
    if not all((registration, full_name, function_name, team_name, shift_name)):
        raise ValueError("Informe matricula, nome, funcao, atividade e turno.")
    status = str(payload.get("status") or "PRE_CADASTRO").strip().upper()
    if status not in EMPLOYEE_STATUSES:
        raise ValueError("Situacao do colaborador invalida.")
    photo_path = _clean(payload.get("photo_path"))
    if photo_path and not photo_path.startswith("/uploads/"):
        raise ValueError("A foto deve ser enviada pelo sistema.")
    return {
        "user_id": _parse_user_id(payload.get("user_id")),
        "registration": registration.upper(),
        "full_name": full_name,
        "function_name": function_name,
        "team_name": team_name,
        "shift_name": shift_name,
        "photo_path": photo_path,
        "status": status,
        "hired_on": _parse_date(payload.get("hired_on")),
        "notes": _clean(payload.get("notes")),
    }


def _integrity_error_message() -> str:
    return "Matricula ja cadastrada ou login ja vinculado a outro colaborador."


@bp.get("/rh/colaboradores")
@auth_required
def list_employees():
    denied = _guard_hr_management()
    if denied:
        return denied
    query = Employee.query
    if search := _clean(request.args.get("busca")):
        pattern = f"%{search}%"
        query = query.filter(or_(Employee.registration.ilike(pattern), Employee.full_name.ilike(pattern)))
    if status := _clean(request.args.get("situacao")):
        query = query.filter(Employee.status == status.upper())
    if team := _clean(request.args.get("equipe")):
        query = query.filter(Employee.team_name == team)
    if shift := _clean(request.args.get("turno")):
        query = query.filter(Employee.shift_name == shift)
    rows = query.order_by(Employee.status.asc(), Employee.full_name.asc()).all()
    return api_response(True, data=[row.to_dict() for row in rows])


@bp.get("/rh/colaboradores/usuarios-disponiveis")
@auth_required
def list_linkable_users():
    denied = _guard_hr_management()
    if denied:
        return denied
    users = User.query.filter_by(ativo=True).order_by(User.nome.asc()).all()
    return api_response(True, data=[user.to_dict() for user in users])


@bp.post("/rh/colaboradores")
@auth_required
def create_employee():
    denied = _guard_hr_management()
    if denied:
        return denied
    try:
        employee = Employee(**_employee_payload(request.get_json(silent=True) or {}))
        db.session.add(employee)
        db.session.flush()
        record_event(user_id=g.current_user.id, entity_type="EMPLOYEE", entity_id=employee.id, action="CREATED", new_value=employee.to_dict())
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    except IntegrityError:
        db.session.rollback()
        return api_response(False, error=_integrity_error_message(), status_code=409)
    return api_response(True, data=employee.to_dict(), status_code=201)


@bp.get("/rh/colaboradores/<int:employee_id>")
@auth_required
def get_employee(employee_id: int):
    denied = _guard_hr_management()
    if denied:
        return denied
    employee = db.session.get(Employee, employee_id)
    if not employee:
        return api_response(False, error="Colaborador nao encontrado.", status_code=404)
    return api_response(True, data=employee.to_dict())


@bp.put("/rh/colaboradores/<int:employee_id>")
@auth_required
def update_employee(employee_id: int):
    denied = _guard_hr_management()
    if denied:
        return denied
    employee = db.session.get(Employee, employee_id)
    if not employee:
        return api_response(False, error="Colaborador nao encontrado.", status_code=404)
    try:
        for field, value in _employee_payload(request.get_json(silent=True) or {}).items():
            setattr(employee, field, value)
        record_event(user_id=g.current_user.id, entity_type="EMPLOYEE", entity_id=employee.id, action="UPDATED", new_value=employee.to_dict())
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    except IntegrityError:
        db.session.rollback()
        return api_response(False, error=_integrity_error_message(), status_code=409)
    return api_response(True, data=employee.to_dict())

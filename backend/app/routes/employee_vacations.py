from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, g, request

from app.extensions import db
from app.models import Employee, EmployeeAttendanceRecord, EmployeeVacation
from app.models.employee import VACATION_STATUSES
from app.services.auth_service import auth_required, user_has_management_access
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive


bp = Blueprint("employee_vacations", __name__)


def _guard_hr_management():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar ferias e DSR.", status_code=403)
    return None


def _clean(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _date(value, label: str) -> date:
    try:
        return date.fromisoformat(str(value or ""))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Informe {label} no formato AAAA-MM-DD.") from exc


def _employee_id(value) -> int:
    try:
        employee_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Colaborador invalido.") from exc
    employee = db.session.get(Employee, employee_id)
    if not employee:
        raise ValueError("Colaborador nao encontrado.")
    if employee.status != "ATIVO":
        raise ValueError("Somente colaboradores ativos podem receber ferias ou DSR.")
    return employee_id


def _vacation_payload(payload: dict) -> dict:
    starts_on = _date(payload.get("starts_on"), "a data inicial")
    ends_on = _date(payload.get("ends_on"), "a data final")
    if ends_on < starts_on:
        raise ValueError("A data final das ferias nao pode ser anterior a data inicial.")
    if (ends_on - starts_on).days + 1 > 90:
        raise ValueError("Um periodo de ferias nao pode ultrapassar 90 dias.")
    status = str(payload.get("status") or "PROGRAMADA").strip().upper()
    if status not in VACATION_STATUSES:
        raise ValueError("Situacao das ferias invalida.")
    return {
        "employee_id": _employee_id(payload.get("employee_id")),
        "starts_on": starts_on,
        "ends_on": ends_on,
        "status": status,
        "notes": _clean(payload.get("notes")),
    }


def _assert_no_overlap(employee_id: int, starts_on: date, ends_on: date, *, ignore_id: int | None = None):
    query = EmployeeVacation.query.filter(
        EmployeeVacation.employee_id == employee_id,
        EmployeeVacation.status.in_(("PROGRAMADA", "APROVADA")),
        EmployeeVacation.starts_on <= ends_on,
        EmployeeVacation.ends_on >= starts_on,
    )
    if ignore_id:
        query = query.filter(EmployeeVacation.id != ignore_id)
    if query.first():
        raise ValueError("Este colaborador ja possui ferias programadas ou aprovadas no periodo informado.")


@bp.get("/rh/ferias")
@auth_required
def list_vacations():
    denied = _guard_hr_management()
    if denied:
        return denied
    query = EmployeeVacation.query
    if employee_id := request.args.get("colaborador_id", type=int):
        query = query.filter_by(employee_id=employee_id)
    if status := _clean(request.args.get("situacao")):
        query = query.filter_by(status=status.upper())
    if starts_on := _clean(request.args.get("data_inicial")):
        try:
            query = query.filter(EmployeeVacation.ends_on >= _date(starts_on, "a data inicial"))
        except ValueError as exc:
            return api_response(False, error=str(exc), status_code=400)
    if ends_on := _clean(request.args.get("data_final")):
        try:
            query = query.filter(EmployeeVacation.starts_on <= _date(ends_on, "a data final"))
        except ValueError as exc:
            return api_response(False, error=str(exc), status_code=400)
    rows = query.order_by(EmployeeVacation.starts_on.asc(), EmployeeVacation.id.asc()).all()
    return api_response(True, data=[row.to_dict() for row in rows])


@bp.post("/rh/ferias")
@auth_required
def create_vacation():
    denied = _guard_hr_management()
    if denied:
        return denied
    try:
        data = _vacation_payload(request.get_json(silent=True) or {})
        if data["status"] != "CANCELADA":
            _assert_no_overlap(data["employee_id"], data["starts_on"], data["ends_on"])
        vacation = EmployeeVacation(**data, created_by_user_id=g.current_user.id)
        db.session.add(vacation)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=vacation.to_dict(), status_code=201)


@bp.post("/rh/ferias/<int:vacation_id>/cancelar")
@auth_required
def cancel_vacation(vacation_id: int):
    denied = _guard_hr_management()
    if denied:
        return denied
    vacation = db.session.get(EmployeeVacation, vacation_id)
    if not vacation:
        return api_response(False, error="Ferias nao encontradas.", status_code=404)
    if vacation.status == "CANCELADA":
        return api_response(False, error="Este periodo de ferias ja esta cancelado.", status_code=400)
    reason = _clean((request.get_json(silent=True) or {}).get("reason"))
    if not reason:
        return api_response(False, error="Informe o motivo do cancelamento.", status_code=400)
    vacation.status = "CANCELADA"
    vacation.notes = f"{vacation.notes or ''}\nCancelamento: {reason}".strip()
    vacation.cancelled_by_user_id = g.current_user.id
    vacation.cancelled_at = now_manaus_naive()
    db.session.commit()
    return api_response(True, data=vacation.to_dict())


def _week_start(value) -> date:
    reference = _date(value, "a segunda-feira da semana")
    if reference.weekday() != 0:
        raise ValueError("Informe a segunda-feira da semana para registrar a DSR.")
    return reference


@bp.get("/rh/dsr-semanal")
@auth_required
def weekly_dsr():
    denied = _guard_hr_management()
    if denied:
        return denied
    try:
        starts_on = _week_start(request.args.get("semana"))
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    dsr_date = starts_on + timedelta(days=6)
    records = EmployeeAttendanceRecord.query.filter_by(
        occurrence_date=dsr_date,
        occurrence_type="DSR",
        record_status="ATIVO",
    ).all()
    vacations = EmployeeVacation.query.filter(
        EmployeeVacation.status.in_(("PROGRAMADA", "APROVADA")),
        EmployeeVacation.starts_on <= dsr_date,
        EmployeeVacation.ends_on >= dsr_date,
    ).all()
    return api_response(
        True,
        data={
            "week_start": starts_on.isoformat(),
            "week_end": dsr_date.isoformat(),
            "dsr_date": dsr_date.isoformat(),
            "records": [row.to_dict() for row in records],
            "vacation_employee_ids": [row.employee_id for row in vacations],
        },
    )


@bp.post("/rh/dsr-semanal")
@auth_required
def create_weekly_dsr():
    denied = _guard_hr_management()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        starts_on = _week_start(payload.get("week_start"))
        employee_ids = sorted({int(value) for value in (payload.get("employee_ids") or [])})
        if not employee_ids:
            raise ValueError("Selecione ao menos um colaborador para a DSR semanal.")
        if len(employee_ids) > 250:
            raise ValueError("A DSR semanal aceita no maximo 250 colaboradores por lancamento.")
        for employee_id in employee_ids:
            _employee_id(employee_id)
        dsr_date = starts_on + timedelta(days=6)
        vacation_ids = {
            row.employee_id for row in EmployeeVacation.query.filter(
                EmployeeVacation.employee_id.in_(employee_ids),
                EmployeeVacation.status.in_(("PROGRAMADA", "APROVADA")),
                EmployeeVacation.starts_on <= dsr_date,
                EmployeeVacation.ends_on >= dsr_date,
            ).all()
        }
        if vacation_ids:
            raise ValueError("Nao e permitido registrar DSR para colaborador que esteja de ferias no domingo da semana.")
        existing = EmployeeAttendanceRecord.query.filter(
            EmployeeAttendanceRecord.employee_id.in_(employee_ids),
            EmployeeAttendanceRecord.occurrence_date == dsr_date,
            EmployeeAttendanceRecord.record_status == "ATIVO",
        ).all()
        conflicts = [row for row in existing if row.occurrence_type != "DSR"]
        if conflicts:
            raise ValueError("Existe outra ocorrencia ativa para um dos colaboradores no domingo desta semana.")
        existing_dsr_ids = {row.employee_id for row in existing}
        created = []
        notes = _clean(payload.get("notes")) or f"DSR semanal | {starts_on.isoformat()} a {dsr_date.isoformat()}"
        for employee_id in employee_ids:
            if employee_id in existing_dsr_ids:
                continue
            record = EmployeeAttendanceRecord(
                employee_id=employee_id,
                occurrence_date=dsr_date,
                occurrence_type="DSR",
                record_status="ATIVO",
                notes=notes,
                created_by_user_id=g.current_user.id,
            )
            db.session.add(record)
            created.append(record)
        db.session.commit()
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    return api_response(
        True,
        data={
            "week_start": starts_on.isoformat(),
            "week_end": dsr_date.isoformat(),
            "dsr_date": dsr_date.isoformat(),
            "created": [row.to_dict() for row in created],
            "already_registered": len(existing_dsr_ids),
        },
        status_code=201,
    )

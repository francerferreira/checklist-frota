from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
import tempfile

from flask import Blueprint, g, request, send_file
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Employee, EmployeeAttendanceRecord, EmployeeSpecialSchedule, EmployeeVacation
from app.models.employee import SPECIAL_SCHEDULE_TYPES
from app.services.auth_service import auth_required, user_has_management_access
from app.services.employee_special_schedule_pdf_export_service import export_executive_special_schedule_pdf
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive


bp = Blueprint("employee_special_schedules", __name__)


def _guard_hr_management():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar escalas especiais.", status_code=403)
    return None


def _clean(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _date(value, label: str) -> date:
    try:
        return date.fromisoformat(str(value or ""))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Informe {label} no formato AAAA-MM-DD.") from exc


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


WEEKDAY_NAMES_PT_BR = (
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
)


def _date_with_weekday(value: date | None) -> str:
    if not value:
        return "Não se aplica"
    return f"{value.strftime('%d/%m/%Y')} — {WEEKDAY_NAMES_PT_BR[value.weekday()]}"


def _next_sunday(reference: date) -> date:
    remaining_days = (6 - reference.weekday()) % 7 or 7
    return reference + timedelta(days=remaining_days)


def _active_employee(employee_id) -> Employee:
    try:
        employee = db.session.get(Employee, int(employee_id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Colaborador inválido.") from exc
    if not employee or employee.status != "ATIVO":
        raise ValueError("A escala aceita apenas colaboradores ativos.")
    return employee


def _is_on_vacation(employee_id: int, reference: date) -> bool:
    return EmployeeVacation.query.filter(
        EmployeeVacation.employee_id == employee_id,
        EmployeeVacation.status.in_(("PROGRAMADA", "APROVADA")),
        EmployeeVacation.starts_on <= reference,
        EmployeeVacation.ends_on >= reference,
    ).first() is not None


@bp.get("/rh/escalas-especiais")
@auth_required
def list_special_schedules():
    denied = _guard_hr_management()
    if denied:
        return denied
    query = EmployeeSpecialSchedule.query
    if schedule_date := _clean(request.args.get("data")):
        try:
            query = query.filter_by(schedule_date=_date(schedule_date, "a data da escala"))
        except ValueError as exc:
            return api_response(False, error=str(exc), status_code=400)
    rows = query.order_by(EmployeeSpecialSchedule.schedule_date.desc(), EmployeeSpecialSchedule.id.desc()).all()
    return api_response(True, data=[row.to_dict() for row in rows])


@bp.get("/rh/escalas-especiais/pdf")
@auth_required
def special_schedules_pdf():
    denied = _guard_hr_management()
    if denied:
        return denied
    query = EmployeeSpecialSchedule.query
    schedule_date = _clean(request.args.get("data"))
    schedule_type = _clean(request.args.get("tipo"))
    try:
        selected_date = _date(schedule_date, "a data da escala") if schedule_date else None
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    if selected_date:
        query = query.filter_by(schedule_date=selected_date)
    if schedule_type:
        schedule_type = schedule_type.upper()
        if schedule_type not in SPECIAL_SCHEDULE_TYPES:
            return api_response(False, error="Selecione DOMINGO ou FERIADO para o tipo da escala.", status_code=400)
        query = query.filter_by(schedule_type=schedule_type)
    schedules = query.order_by(EmployeeSpecialSchedule.schedule_date.desc(), EmployeeSpecialSchedule.id.desc()).all()
    rows = []
    for schedule in schedules:
        employee = schedule.employee.to_dict() if schedule.employee else {}
        rows.append({
            "schedule_date": _date_with_weekday(schedule.schedule_date),
            "schedule_weekday": WEEKDAY_NAMES_PT_BR[schedule.schedule_date.weekday()],
            "schedule_type": schedule.schedule_type,
            "area": _clean(employee.get("team_name")) or "-",
            "employee": _clean(employee.get("full_name")) or "-",
            "registration": _clean(employee.get("registration")) or "-",
            "function_shift": " / ".join(value for value in (employee.get("function_name"), employee.get("shift_name")) if value) or "-",
            "status": str(schedule.status or "-").replace("_", " "),
            "dsr_date": _date_with_weekday(schedule.dsr_date),
        })
    tmp = tempfile.NamedTemporaryFile(prefix="escala_especial_", suffix=".pdf", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        export_executive_special_schedule_pdf(
            rows,
            tmp_path,
            report_date=_date_with_weekday(selected_date) if selected_date else "Todas as datas",
            schedule_type=schedule_type or "DOMINGO E FERIADO",
            generated_by=g.current_user.nome or g.current_user.login,
        )
        pdf_buffer = BytesIO(tmp_path.read_bytes())
    finally:
        tmp_path.unlink(missing_ok=True)
    pdf_buffer.seek(0)
    filename = f"escala_domingo_feriado_{selected_date.isoformat() if selected_date else 'historico'}.pdf"
    return send_file(pdf_buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)


@bp.post("/rh/escalas-especiais")
@auth_required
def create_special_schedule():
    denied = _guard_hr_management()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        schedule_date = _date(payload.get("schedule_date"), "a data da escala")
        schedule_type = str(payload.get("schedule_type") or "").strip().upper()
        if schedule_type not in SPECIAL_SCHEDULE_TYPES:
            raise ValueError("Selecione DOMINGO ou FERIADO para a escala.")
        if schedule_type == "DOMINGO" and schedule_date.weekday() != 6:
            raise ValueError("A data informada precisa ser um domingo.")
        if schedule_type == "DOMINGO" and schedule_date != _next_sunday(now_manaus_naive().date()):
            raise ValueError("A escala de domingo fica aberta do domingo atual até sábado, sempre para o próximo domingo.")
        holiday_name = _clean(payload.get("holiday_name"))
        if schedule_type == "FERIADO" and not holiday_name:
            raise ValueError("Informe o nome do feriado.")
        entries = payload.get("entries") or []
        if not isinstance(entries, list) or not entries:
            raise ValueError("Selecione ao menos um colaborador na escala.")
        if len(entries) > 250:
            raise ValueError("A escala aceita no máximo 250 colaboradores por lançamento.")

        created = []
        employee_ids = set()
        for entry in entries:
            employee = _active_employee((entry or {}).get("employee_id"))
            if employee.id in employee_ids:
                raise ValueError("Um colaborador foi informado mais de uma vez na mesma escala.")
            employee_ids.add(employee.id)
            if _is_on_vacation(employee.id, schedule_date):
                raise ValueError("Não é permitido escalar colaborador em férias.")
            if EmployeeSpecialSchedule.query.filter_by(employee_id=employee.id, schedule_date=schedule_date).first():
                raise ValueError("Este colaborador já está escalado nesta data.")
            dsr_date = None
            dsr_week_start = None
            if schedule_type == "DOMINGO":
                dsr_date = _date((entry or {}).get("dsr_date"), "a data prevista da DSR")
                if dsr_date == schedule_date:
                    raise ValueError("A DSR precisa ser em um dia diferente do domingo escalado.")
                if _is_on_vacation(employee.id, dsr_date):
                    raise ValueError("Não é permitido prever DSR em período de férias.")
                dsr_week_start = _week_start(dsr_date)
            schedule = EmployeeSpecialSchedule(
                employee_id=employee.id,
                schedule_date=schedule_date,
                schedule_type=schedule_type,
                holiday_name=holiday_name if schedule_type == "FERIADO" else None,
                dsr_date=dsr_date,
                dsr_week_start=dsr_week_start,
                notes=_clean(payload.get("notes")),
                created_by_user_id=g.current_user.id,
            )
            db.session.add(schedule)
            created.append(schedule)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    except IntegrityError:
        db.session.rollback()
        return api_response(False, error="A escala já possui lançamento para um dos colaboradores.", status_code=409)
    return api_response(True, data=[row.to_dict() for row in created], status_code=201)


@bp.post("/rh/escalas-especiais/<int:schedule_id>/confirmar-presenca")
@auth_required
def confirm_special_schedule_attendance(schedule_id: int):
    denied = _guard_hr_management()
    if denied:
        return denied
    schedule = db.session.get(EmployeeSpecialSchedule, schedule_id)
    if not schedule:
        return api_response(False, error="Escala não encontrada.", status_code=404)
    if schedule.status != "ESCALADO":
        return api_response(False, error="Esta escala já foi concluída.", status_code=400)
    try:
        if _is_on_vacation(schedule.employee_id, schedule.schedule_date):
            raise ValueError("Não é permitido confirmar presença de colaborador em férias.")
        if schedule.schedule_type == "DOMINGO":
            if not schedule.dsr_date:
                raise ValueError("A escala de domingo não possui data de DSR prevista.")
            if _is_on_vacation(schedule.employee_id, schedule.dsr_date):
                raise ValueError("Não é permitido lançar DSR em período de férias.")
            attendance = EmployeeAttendanceRecord.query.filter_by(
                employee_id=schedule.employee_id,
                occurrence_date=schedule.dsr_date,
                record_status="ATIVO",
            ).first()
            if attendance and attendance.occurrence_type != "DSR":
                raise ValueError("Já existe outra ocorrência ativa na data prevista para a DSR.")
            if not attendance:
                attendance = EmployeeAttendanceRecord(
                    employee_id=schedule.employee_id,
                    occurrence_date=schedule.dsr_date,
                    occurrence_type="DSR",
                    record_status="ATIVO",
                    notes=f"DSR gerada após presença confirmada no domingo {schedule.schedule_date.isoformat()}.",
                    created_by_user_id=g.current_user.id,
                )
                db.session.add(attendance)
                db.session.flush()
            schedule.dsr_attendance_record_id = attendance.id
        schedule.status = "COMPARECEU"
        schedule.attendance_confirmed_by_user_id = g.current_user.id
        schedule.attendance_confirmed_at = now_manaus_naive()
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    except IntegrityError:
        db.session.rollback()
        return api_response(False, error="Não foi possível registrar a presença e a DSR.", status_code=409)
    return api_response(True, data=schedule.to_dict())


@bp.post("/rh/escalas-especiais/<int:schedule_id>/nao-compareceu")
@auth_required
def mark_special_schedule_absence(schedule_id: int):
    denied = _guard_hr_management()
    if denied:
        return denied
    schedule = db.session.get(EmployeeSpecialSchedule, schedule_id)
    if not schedule:
        return api_response(False, error="Escala não encontrada.", status_code=404)
    if schedule.status != "ESCALADO":
        return api_response(False, error="Esta escala já foi concluída.", status_code=400)
    schedule.status = "NAO_COMPARECEU"
    schedule.attendance_confirmed_by_user_id = g.current_user.id
    schedule.attendance_confirmed_at = now_manaus_naive()
    db.session.commit()
    return api_response(True, data=schedule.to_dict())

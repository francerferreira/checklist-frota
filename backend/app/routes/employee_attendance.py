from __future__ import annotations

from datetime import date, datetime, time, timedelta
from io import BytesIO
from pathlib import Path
import tempfile

from flask import Blueprint, g, request, send_file
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Employee, EmployeeAttendanceRecord, EmployeeSpecialSchedule, EmployeeVacation
from app.models.employee import ATTENDANCE_TYPES
from app.services.auth_service import auth_required, user_has_management_access
from app.services.employee_attendance_pdf_export_service import export_executive_employee_attendance_pdf
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive


bp = Blueprint("employee_attendance", __name__)
PERIOD_TYPES = {"ATESTADO", "FERIAS", "AFASTADO"}
ABSENTEEISM_TYPES = ("PRESENTE", "FALTA", "ATESTADO", "DSR", "FERIAS", "FOLGA", "AFASTADO", "CURSO", "SERVICO_EXTERNO")


def _guard_hr_management():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar frequencia.", status_code=403)
    return None


def _clean(value) -> str | None:
    text_value = str(value or "").strip()
    return text_value or None


def _parse_date(value, label: str) -> date:
    try:
        return date.fromisoformat(str(value or ""))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Informe {label} no formato AAAA-MM-DD.") from exc


def _parse_time(value, label: str) -> time | None:
    if value in (None, ""):
        return None
    try:
        return time.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} invalido. Use HH:MM.") from exc


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "sim", "yes", "on"}


def _minutes_between(start: time, end: time) -> int:
    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute
    return max(0, end_minutes - start_minutes)


def _record_payload(payload: dict) -> dict:
    try:
        employee_id = int(payload.get("employee_id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Colaborador invalido.") from exc
    if not db.session.get(Employee, employee_id):
        raise ValueError("Colaborador nao encontrado.")
    occurrence_type = str(payload.get("occurrence_type") or "").strip().upper()
    if occurrence_type not in ATTENDANCE_TYPES:
        raise ValueError("Tipo de ocorrencia invalido.")
    scheduled_time = _parse_time(payload.get("scheduled_time"), "Horario previsto")
    arrival_time = _parse_time(payload.get("arrival_time"), "Horario de chegada")
    delay_minutes = 0
    if occurrence_type == "ATRASO":
        if not scheduled_time or not arrival_time:
            raise ValueError("Informe horario previsto e horario de chegada para atraso.")
        delay_minutes = _minutes_between(scheduled_time, arrival_time)
        if delay_minutes <= 0:
            raise ValueError("O horario de chegada deve ser posterior ao horario previsto.")
    document_path = _clean(payload.get("document_path"))
    if document_path and not document_path.startswith("/uploads/"):
        raise ValueError("O documento deve ser enviado pelo sistema.")
    return {
        "employee_id": employee_id,
        "occurrence_date": _parse_date(payload.get("occurrence_date"), "a data"),
        "occurrence_type": occurrence_type,
        "scheduled_time": scheduled_time,
        "arrival_time": arrival_time,
        "delay_minutes": delay_minutes,
        "is_justified": _parse_bool(payload.get("is_justified")),
        "reason": _clean(payload.get("reason")),
        "document_path": document_path,
        "notes": _clean(payload.get("notes")),
    }


def _dates_in_period(start_date: date, end_date: date):
    for offset in range((end_date - start_date).days + 1):
        yield start_date + timedelta(days=offset)


def _absenteeism_summary(rows: list[dict]) -> dict:
    totals = {kind: 0 for kind in ABSENTEEISM_TYPES}
    for row in rows:
        kind = row["occurrence_type"]
        if kind in totals:
            totals[kind] += 1
    return {"total": len(rows), "by_type": totals}


def _absenteeism_employee_query(args):
    query = Employee.query.filter_by(status="ATIVO")
    if shift := _clean(args.get("turno")):
        query = query.filter_by(shift_name=shift)
    if sector := _clean(args.get("setor")):
        query = query.filter_by(team_name=sector)
    if function_name := _clean(args.get("funcao")):
        query = query.filter_by(function_name=function_name)
    if name := _clean(args.get("nome")):
        query = query.filter(Employee.full_name.ilike(f"%{name}%"))
    if registration := _clean(args.get("matricula")):
        query = query.filter(Employee.registration.ilike(f"%{registration}%"))
    return query.order_by(Employee.team_name.asc(), Employee.full_name.asc())


def _build_absenteeism_rows(reference_date: date, query):
    employees = query.all()
    employee_ids = [employee.id for employee in employees]
    records = EmployeeAttendanceRecord.query.filter(
        EmployeeAttendanceRecord.employee_id.in_(employee_ids or [-1]),
        EmployeeAttendanceRecord.occurrence_date == reference_date,
        EmployeeAttendanceRecord.record_status == "ATIVO",
    ).all()
    records_by_employee = {record.employee_id: record for record in records}
    vacation_ids = {
        row.employee_id for row in EmployeeVacation.query.filter(
            EmployeeVacation.employee_id.in_(employee_ids or [-1]),
            EmployeeVacation.status.in_(("PROGRAMADA", "APROVADA")),
            EmployeeVacation.starts_on <= reference_date,
            EmployeeVacation.ends_on >= reference_date,
        ).all()
    }
    dsr_ids = {
        row.employee_id for row in EmployeeSpecialSchedule.query.filter(
            EmployeeSpecialSchedule.employee_id.in_(employee_ids or [-1]),
            EmployeeSpecialSchedule.dsr_date == reference_date,
            EmployeeSpecialSchedule.status.in_(("ESCALADO", "COMPARECEU")),
        ).all()
    }
    rows = []
    for employee in employees:
        record = records_by_employee.get(employee.id)
        automatic_vacation = employee.id in vacation_ids
        occurrence_type = "FERIAS" if automatic_vacation else (record.occurrence_type if record else ("DSR" if employee.id in dsr_ids else "PRESENTE"))
        rows.append({
            "employee": employee.to_dict(), "record_id": record.id if record else None,
            "occurrence_type": occurrence_type, "notes": record.notes if record else "",
            "automatic_vacation": automatic_vacation,
            "updated_at": record.updated_at.isoformat() if record and record.updated_at else None,
            "updated_by_user_id": record.updated_by_user_id if record else None,
        })
    return rows


def _attendance_area_label(employee: dict) -> str:
    text = str(employee.get("notes") or "").upper()
    marker = "AREA DE ATUACAO:"
    if marker in text:
        value = text.split(marker, 1)[1].split(".", 1)[0].strip()
        if value in {"ADM", "PCM", "RTG", "LBS"}:
            return value
    return str(employee.get("team_name") or "OUTROS").upper()


@bp.get("/rh/absenteismo-mobile")
@auth_required
def mobile_absenteeism():
    denied = _guard_hr_management()
    if denied:
        return denied
    try:
        reference_date = _parse_date(request.args.get("data") or date.today().isoformat(), "a data")
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    rows = _build_absenteeism_rows(reference_date, _absenteeism_employee_query(request.args))
    employees = [row["employee"] for row in rows]
    if status := _clean(request.args.get("status")):
        rows = [row for row in rows if row["occurrence_type"] == status.upper()]
    return api_response(True, data={"date": reference_date.isoformat(), "rows": rows, "summary": _absenteeism_summary(rows)})


@bp.get("/rh/absenteismo-mobile/pdf")
@auth_required
def mobile_absenteeism_pdf():
    denied = _guard_hr_management()
    if denied:
        return denied
    try:
        reference_date = _parse_date(request.args.get("data") or date.today().isoformat(), "a data")
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    rows = _build_absenteeism_rows(reference_date, _absenteeism_employee_query(request.args))
    if status := _clean(request.args.get("status")):
        rows = [row for row in rows if row["occurrence_type"] == status.upper()]
    export_rows = []
    for row in rows:
        employee = row["employee"] or {}
        export_rows.append({
            "area": _attendance_area_label(employee),
            "colaborador": employee.get("full_name") or "-",
            "matricula": employee.get("registration") or "-",
            "funcao": employee.get("function_name") or "-",
            "turno": employee.get("shift_name") or "-",
            "status": row["occurrence_type"].replace("_", " "),
            "observacao": row.get("notes") or "-",
        })
    filename = f"absenteismo_{reference_date.isoformat()}.pdf"
    tmp = tempfile.NamedTemporaryFile(prefix="absenteismo_", suffix=".pdf", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    export_executive_employee_attendance_pdf(
        export_rows,
        tmp_path,
        report_date=reference_date.strftime("%d/%m/%Y"),
        shift_label=_clean(request.args.get("turno")) or "Todos",
        area_label=_clean(request.args.get("setor")) or "Todas",
        generated_by=g.current_user.nome or g.current_user.login,
    )
    pdf_buffer = BytesIO(tmp_path.read_bytes())
    tmp_path.unlink(missing_ok=True)
    pdf_buffer.seek(0)
    return send_file(pdf_buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)

@bp.post("/rh/absenteismo-mobile")
@auth_required
def save_mobile_absenteeism():
    denied = _guard_hr_management()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        reference_date = _parse_date(payload.get("date"), "a data")
        # A apuração diária não pode ser lançada depois do fechamento da janela
        # operacional. Datas futuras continuam disponíveis para prévia, mas uma
        # data anterior ao dia corrente exige correção pelo histórico de RH.
        if reference_date < date.today():
            raise ValueError("A janela de 24 horas para esta apuração já foi encerrada. Use o histórico de RH para corrigir o lançamento.")
        entries = payload.get("entries") or []
        if not isinstance(entries, list) or not entries:
            raise ValueError("Informe ao menos um colaborador para salvar.")
        if len(entries) > 300:
            raise ValueError("O lançamento aceita no máximo 300 colaboradores por vez.")
        updated = []
        ids = set()
        vacation_ids = {row.employee_id for row in EmployeeVacation.query.filter(
            EmployeeVacation.status.in_(("PROGRAMADA", "APROVADA")), EmployeeVacation.starts_on <= reference_date, EmployeeVacation.ends_on >= reference_date,
        ).all()}
        for entry in entries:
            employee_id = int((entry or {}).get("employee_id"))
            if employee_id in ids:
                raise ValueError("Há colaborador repetido no lançamento.")
            ids.add(employee_id)
            employee = db.session.get(Employee, employee_id)
            if not employee or employee.status != "ATIVO":
                raise ValueError("A apuração aceita apenas colaboradores ativos.")
            if employee_id in vacation_ids:
                continue
            occurrence_type = str((entry or {}).get("occurrence_type") or "PRESENTE").upper()
            if occurrence_type not in ABSENTEEISM_TYPES or occurrence_type == "FERIAS":
                raise ValueError("Status de absenteísmo inválido.")
            record = EmployeeAttendanceRecord.query.filter_by(employee_id=employee_id, occurrence_date=reference_date).first()
            if not record:
                record = EmployeeAttendanceRecord(employee_id=employee_id, occurrence_date=reference_date, occurrence_type=occurrence_type, record_status="ATIVO", notes=_clean((entry or {}).get("notes")), created_by_user_id=g.current_user.id)
                db.session.add(record)
            else:
                record.occurrence_type = occurrence_type
                record.record_status = "ATIVO"
                record.notes = _clean((entry or {}).get("notes"))
                record.change_reason = "Atualização pela apuração móvel de absenteísmo."
                record.updated_by_user_id = g.current_user.id
            updated.append(record)
        db.session.commit()
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data={"saved": len(updated), "date": reference_date.isoformat()})


@bp.get("/rh/frequencia")
@auth_required
def list_attendance():
    denied = _guard_hr_management()
    if denied:
        return denied
    query = EmployeeAttendanceRecord.query
    if employee_id := request.args.get("colaborador_id", type=int):
        query = query.filter_by(employee_id=employee_id)
    if occurrence_date := _clean(request.args.get("data")):
        try:
            query = query.filter_by(occurrence_date=_parse_date(occurrence_date, "a data"))
        except ValueError as exc:
            return api_response(False, error=str(exc), status_code=400)
    if occurrence_type := _clean(request.args.get("tipo")):
        query = query.filter_by(occurrence_type=occurrence_type.upper())
    if record_status := _clean(request.args.get("status")):
        query = query.filter_by(record_status=record_status.upper())
    rows = query.order_by(EmployeeAttendanceRecord.occurrence_date.desc(), EmployeeAttendanceRecord.id.desc()).all()
    return api_response(True, data=[row.to_dict() for row in rows])


@bp.post("/rh/frequencia")
@auth_required
def create_attendance():
    denied = _guard_hr_management()
    if denied:
        return denied
    try:
        data = _record_payload(request.get_json(silent=True) or {})
        end_date_raw = (request.get_json(silent=True) or {}).get("end_date")
        end_date = _parse_date(end_date_raw, "a data final") if end_date_raw else data["occurrence_date"]
        if end_date < data["occurrence_date"]:
            raise ValueError("A data final nao pode ser anterior a data inicial.")
        if end_date > data["occurrence_date"] and data["occurrence_type"] not in PERIOD_TYPES:
            raise ValueError("Periodo e permitido apenas para atestado, ferias ou afastamento.")
        if (end_date - data["occurrence_date"]).days > 366:
            raise ValueError("O periodo nao pode ultrapassar 366 dias.")
        dates = list(_dates_in_period(data["occurrence_date"], end_date))
        conflicts = EmployeeAttendanceRecord.query.filter(
            EmployeeAttendanceRecord.employee_id == data["employee_id"],
            EmployeeAttendanceRecord.occurrence_date.in_(dates),
        ).first()
        if conflicts:
            raise ValueError("Ja existe um lancamento para este colaborador em uma das datas informadas.")
        records = []
        for current_date in dates:
            record = EmployeeAttendanceRecord(**{**data, "occurrence_date": current_date, "created_by_user_id": g.current_user.id})
            db.session.add(record)
            records.append(record)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    except IntegrityError:
        db.session.rollback()
        return api_response(False, error="Ja existe um lancamento para este colaborador nesta data.", status_code=409)
    return api_response(True, data=[record.to_dict() for record in records], status_code=201)


@bp.put("/rh/frequencia/<int:record_id>")
@auth_required
def update_attendance(record_id: int):
    denied = _guard_hr_management()
    if denied:
        return denied
    record = db.session.get(EmployeeAttendanceRecord, record_id)
    if not record:
        return api_response(False, error="Lancamento nao encontrado.", status_code=404)
    if record.record_status == "CANCELADO":
        return api_response(False, error="Lancamento cancelado nao pode ser alterado.", status_code=400)
    payload = request.get_json(silent=True) or {}
    change_reason = _clean(payload.get("change_reason"))
    if not change_reason:
        return api_response(False, error="Informe o motivo da correcao.", status_code=400)
    try:
        data = _record_payload(payload)
        if data["employee_id"] != record.employee_id or data["occurrence_date"] != record.occurrence_date:
            raise ValueError("A correcao nao pode trocar colaborador ou data; cancele e registre novamente.")
        for field, value in data.items():
            setattr(record, field, value)
        record.change_reason = change_reason
        record.updated_by_user_id = g.current_user.id
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=record.to_dict())


@bp.post("/rh/frequencia/<int:record_id>/cancelar")
@auth_required
def cancel_attendance(record_id: int):
    denied = _guard_hr_management()
    if denied:
        return denied
    record = db.session.get(EmployeeAttendanceRecord, record_id)
    if not record:
        return api_response(False, error="Lancamento nao encontrado.", status_code=404)
    if record.record_status == "CANCELADO":
        return api_response(False, error="Lancamento ja esta cancelado.", status_code=400)
    reason = _clean((request.get_json(silent=True) or {}).get("reason"))
    if not reason:
        return api_response(False, error="Informe o motivo do cancelamento.", status_code=400)
    record.record_status = "CANCELADO"
    record.cancellation_reason = reason
    record.cancelled_by_user_id = g.current_user.id
    record.cancelled_at = now_manaus_naive()
    db.session.commit()
    return api_response(True, data=record.to_dict())

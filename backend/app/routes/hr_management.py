from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, g, request
from sqlalchemy import func

from app.extensions import db
from app.models import Employee, EmployeeAttendanceRecord, EmployeeDocument, EmployeeTraining
from app.services.audit_service import record_event
from app.services.auth_service import auth_required, user_has_management_access
from app.utils.responses import api_response
from app.utils.timezone import now_manaus_naive


bp = Blueprint("hr_management", __name__)
ABSENCE_TYPES = {"FALTA", "ATESTADO", "AFASTADO"}
OPERATIONAL_ATTENDANCE_TYPES = {"PRESENTE", "ATRASO", "FALTA", "ATESTADO", "AFASTADO"}


def _guard():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem consultar a gestao de RH.", status_code=403)
    return None


def _period(start_value=None, end_value=None) -> tuple[date, date]:
    today = now_manaus_naive().date()
    default_start = today.replace(day=1)
    try:
        start = date.fromisoformat(str(start_value or request.args.get("data_inicial") or default_start.isoformat()))
        end = date.fromisoformat(str(end_value or request.args.get("data_final") or today.isoformat()))
    except ValueError as exc:
        raise ValueError("Use AAAA-MM-DD para o periodo.") from exc
    if end < start:
        raise ValueError("A data final nao pode ser anterior a data inicial.")
    if (end - start).days > 366:
        raise ValueError("O periodo pode ter no maximo 366 dias.")
    return start, end


def _alert_days(raw_value=None) -> int:
    try:
        value = int(raw_value if raw_value is not None else request.args.get("dias_alerta", default=30, type=int))
    except (TypeError, ValueError) as exc:
        raise ValueError("Dias de alerta deve estar entre 0 e 180.") from exc
    if value < 0 or value > 180:
        raise ValueError("Dias de alerta deve estar entre 0 e 180.")
    return value


def _employee_label(employee: Employee | None) -> dict:
    return {
        "id": employee.id if employee else None,
        "registration": employee.registration if employee else "-",
        "full_name": employee.full_name if employee else "-",
        "team_name": employee.team_name if employee else "-",
    }


def _build_alerts(reference_date: date, alert_days: int) -> list[dict]:
    limit = reference_date + timedelta(days=alert_days)
    documents = EmployeeDocument.query.filter(
        EmployeeDocument.expires_on.isnot(None),
        EmployeeDocument.expires_on <= limit,
    )
    if str(g.current_user.tipo or "").lower() != "admin":
        documents = documents.filter(EmployeeDocument.is_sensitive.is_(False))
    alerts = [
        {
            "kind": "DOCUMENTO",
            "record_id": row.id,
            "label": row.document_type,
            "expires_on": row.expires_on.isoformat(),
            "status": row.status(reference_date),
            "employee": _employee_label(row.employee),
        }
        for row in documents.all()
    ]
    trainings = EmployeeTraining.query.filter(
        EmployeeTraining.expires_on.isnot(None),
        EmployeeTraining.expires_on <= limit,
    ).all()
    alerts.extend(
        {
            "kind": "TREINAMENTO",
            "record_id": row.id,
            "label": row.course_name,
            "expires_on": row.expires_on.isoformat(),
            "status": row.status(reference_date),
            "employee": _employee_label(row.employee),
        }
        for row in trainings
    )
    priority = {"VENCIDO": 0, "VENCENDO": 1}
    return sorted(alerts, key=lambda row: (priority.get(row["status"], 2), row["expires_on"], row["label"]))


def _overview(start_value=None, end_value=None, alert_days_value=None) -> dict:
    start, end = _period(start_value, end_value)
    alert_days = _alert_days(alert_days_value)
    attendance_rows = EmployeeAttendanceRecord.query.filter(
        EmployeeAttendanceRecord.record_status == "ATIVO",
        EmployeeAttendanceRecord.occurrence_date >= start,
        EmployeeAttendanceRecord.occurrence_date <= end,
    ).all()
    attendance_by_type = {row[0]: int(row[1]) for row in db.session.query(EmployeeAttendanceRecord.occurrence_type, func.count(EmployeeAttendanceRecord.id)).filter(
        EmployeeAttendanceRecord.record_status == "ATIVO",
        EmployeeAttendanceRecord.occurrence_date >= start,
        EmployeeAttendanceRecord.occurrence_date <= end,
    ).group_by(EmployeeAttendanceRecord.occurrence_type).all()}
    operational_records = sum(count for kind, count in attendance_by_type.items() if kind in OPERATIONAL_ATTENDANCE_TYPES)
    absences = sum(count for kind, count in attendance_by_type.items() if kind in ABSENCE_TYPES)
    alerts = _build_alerts(end, alert_days)
    team_rows = db.session.query(Employee.team_name, func.count(Employee.id)).filter(Employee.status == "ATIVO").group_by(Employee.team_name).order_by(Employee.team_name.asc()).all()
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "alert_days": alert_days},
        "employees": {
            "total": Employee.query.count(),
            "active": Employee.query.filter_by(status="ATIVO").count(),
            "inactive": Employee.query.filter_by(status="INATIVO").count(),
            "by_team": [{"team_name": name or "Sem equipe", "total": int(total)} for name, total in team_rows],
        },
        "attendance": {
            "records": len(attendance_rows),
            "absences": absences,
            "by_type": [{"occurrence_type": kind, "total": total} for kind, total in sorted(attendance_by_type.items())],
            "absenteeism_percent": round((absences / operational_records * 100), 2) if operational_records else 0.0,
            "calculation": "Falta, atestado e afastamento sobre os registros operacionais do periodo; indicador gerencial, nao folha de pagamento.",
        },
        "alerts": alerts,
        "alert_summary": {
            "total": len(alerts),
            "expired": sum(1 for row in alerts if row["status"] == "VENCIDO"),
            "expiring": sum(1 for row in alerts if row["status"] == "VENCENDO"),
        },
    }


@bp.get("/rh/gestao")
@auth_required
def get_hr_management():
    if denied := _guard():
        return denied
    try:
        return api_response(True, data=_overview())
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)


@bp.post("/rh/gestao/exportacoes")
@auth_required
def register_hr_export():
    if denied := _guard():
        return denied
    payload = request.get_json(silent=True) or {}
    export_format = str(payload.get("format") or "CSV").upper()
    if export_format not in {"CSV", "XLSX"}:
        return api_response(False, error="Formato de exportacao invalido.", status_code=400)
    try:
        overview = _overview(payload.get("data_inicial"), payload.get("data_final"), payload.get("dias_alerta"))
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    record_event(
        user_id=g.current_user.id,
        entity_type="RH_MANAGEMENT",
        entity_id=0,
        action="EXPORT",
        new_value=f"Formato: {export_format}; alertas exportados: {overview['alert_summary']['total']}; periodo: {overview['period']['start']} a {overview['period']['end']}",
    )
    db.session.commit()
    return api_response(True, data={"export_format": export_format, "alerts": overview["alert_summary"]["total"]})

from datetime import date, timedelta

from flask import Blueprint, g, request

from app.models import Employee, EmployeeAttendanceRecord, EmployeeTraining
from app.services.auth_service import auth_required
from app.services.mobile_operation_service import (
    MobileOperationAccessError,
    MobileOperationConflict,
    mobile_access_code,
    resolve_mobile_asset,
    sync_mobile_operation,
)
from app.utils.responses import api_response


bp = Blueprint("mobile_operations", __name__)


def _mobile_employee_profile(employee: Employee) -> dict:
    return {
        "id": employee.id,
        "registration": employee.registration,
        "full_name": employee.full_name,
        "function_name": employee.function_name,
        "team_name": employee.team_name,
        "shift_name": employee.shift_name,
        "status": employee.status,
        "photo_path": employee.photo_path,
    }


@bp.get("/operacao-mobile/minha-jornada")
@auth_required
def mobile_employee_journey():
    """Consulta mobile do proprio colaborador, sem dados sensiveis de terceiros."""
    employee = Employee.query.filter_by(user_id=g.current_user.id).first()
    if not employee:
        return api_response(False, error="Este login nao esta vinculado a um colaborador.", status_code=404)

    today = date.today()
    attendance = (
        EmployeeAttendanceRecord.query
        .filter_by(employee_id=employee.id, record_status="ATIVO")
        .order_by(EmployeeAttendanceRecord.occurrence_date.desc(), EmployeeAttendanceRecord.id.desc())
        .limit(10)
        .all()
    )
    trainings = (
        EmployeeTraining.query
        .filter(
            EmployeeTraining.employee_id == employee.id,
            EmployeeTraining.expires_on.isnot(None),
            EmployeeTraining.expires_on <= today + timedelta(days=30),
        )
        .order_by(EmployeeTraining.expires_on.asc())
        .all()
    )
    return api_response(
        True,
        data={
            "employee": _mobile_employee_profile(employee),
            "attendance": [
                {
                    "occurrence_date": row.occurrence_date.isoformat(),
                    "occurrence_type": row.occurrence_type,
                    "delay_minutes": row.delay_minutes,
                    "is_justified": row.is_justified,
                    "record_status": row.record_status,
                }
                for row in attendance
            ],
            "training_alerts": [
                {
                    "course_name": row.course_name,
                    "training_type": row.training_type,
                    "expires_on": row.expires_on.isoformat(),
                    "status": row.status(today),
                }
                for row in trainings
            ],
            "reference_date": today.isoformat(),
        },
    )


@bp.get("/operacao-mobile/ativos/<access_code>")
@auth_required
def mobile_asset_by_code(access_code: str):
    try:
        vehicle = resolve_mobile_asset(access_code)
    except LookupError as exc:
        return api_response(False, error=str(exc), status_code=404)
    return api_response(True, data={"access_code": mobile_access_code(vehicle.id), "vehicle": vehicle.to_dict()})


@bp.post("/operacao-mobile/sincronizar")
@auth_required
def sync_mobile():
    try:
        data = sync_mobile_operation(request.get_json(silent=True) or {}, g.current_user)
    except MobileOperationAccessError as exc:
        return api_response(False, error=str(exc), status_code=403)
    except MobileOperationConflict as exc:
        return api_response(False, error=str(exc), status_code=409)
    except ValueError as exc:
        return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=data)

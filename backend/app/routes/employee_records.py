from __future__ import annotations

from datetime import date

from flask import Blueprint, g, request

from app.extensions import db
from app.models import Employee, EmployeeDocument, EmployeeHistoryEvent, EmployeeTraining
from app.services.auth_service import auth_required, user_has_management_access
from app.utils.responses import api_response


bp = Blueprint("employee_records", __name__)


def _guard():
    if not user_has_management_access(g.current_user):
        return api_response(False, error="Somente admin ou gestor podem gerenciar registros de RH.", status_code=403)
    return None


def _clean(value):
    value = str(value or "").strip()
    return value or None


def _bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "sim", "yes"}
    return bool(value)


def _date(value, label, *, required=False):
    if value in (None, ""):
        if required: raise ValueError(f"Informe {label}.")
        return None
    try: return date.fromisoformat(str(value))
    except ValueError as exc: raise ValueError(f"{label} invalida.") from exc


def _employee(value):
    try: employee = db.session.get(Employee, int(value))
    except (TypeError, ValueError): employee = None
    if not employee: raise ValueError("Colaborador nao encontrado.")
    return employee


def _file(value, label):
    path = _clean(value)
    if not path or not path.startswith("/uploads/"): raise ValueError(f"{label} deve ser enviado pelo sistema.")
    return path


@bp.get("/rh/documentos")
@auth_required
def list_documents():
    if denied := _guard(): return denied
    query = EmployeeDocument.query
    if employee_id := request.args.get("colaborador_id", type=int): query = query.filter_by(employee_id=employee_id)
    if g.current_user.tipo != "admin": query = query.filter_by(is_sensitive=False)
    return api_response(True, data=[row.to_dict() for row in query.order_by(EmployeeDocument.expires_on.asc()).all()])


@bp.post("/rh/documentos")
@auth_required
def create_document():
    if denied := _guard(): return denied
    payload = request.get_json(silent=True) or {}
    try:
        sensitive = _bool(payload.get("is_sensitive"))
        if sensitive and g.current_user.tipo != "admin": raise ValueError("Somente admin pode registrar documento sensivel.")
        row = EmployeeDocument(employee_id=_employee(payload.get("employee_id")).id, document_type=_clean(payload.get("document_type")) or "", issued_on=_date(payload.get("issued_on"), "Data de emissao"), expires_on=_date(payload.get("expires_on"), "Data de validade"), file_path=_file(payload.get("file_path"), "Documento"), is_sensitive=sensitive, notes=_clean(payload.get("notes")), created_by_user_id=g.current_user.id)
        if not row.document_type: raise ValueError("Informe o tipo do documento.")
        db.session.add(row); db.session.commit()
    except ValueError as exc:
        db.session.rollback(); return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=row.to_dict(), status_code=201)


@bp.get("/rh/treinamentos")
@auth_required
def list_trainings():
    if denied := _guard(): return denied
    query = EmployeeTraining.query
    if employee_id := request.args.get("colaborador_id", type=int): query = query.filter_by(employee_id=employee_id)
    return api_response(True, data=[row.to_dict() for row in query.order_by(EmployeeTraining.expires_on.asc()).all()])


@bp.post("/rh/treinamentos")
@auth_required
def create_training():
    if denied := _guard(): return denied
    payload = request.get_json(silent=True) or {}
    try:
        hours = payload.get("workload_hours")
        hours = int(hours) if hours not in (None, "") else None
        if hours is not None and hours <= 0: raise ValueError("Carga horaria deve ser positiva.")
        certificate = _clean(payload.get("certificate_path"))
        if certificate: certificate = _file(certificate, "Certificado")
        row = EmployeeTraining(employee_id=_employee(payload.get("employee_id")).id, course_name=_clean(payload.get("course_name")) or "", training_type=_clean(payload.get("training_type")) or "", provider_name=_clean(payload.get("provider_name")), starts_on=_date(payload.get("starts_on"), "Data inicial"), ends_on=_date(payload.get("ends_on"), "Data final"), workload_hours=hours, expires_on=_date(payload.get("expires_on"), "Data de validade"), certificate_path=certificate, notes=_clean(payload.get("notes")), created_by_user_id=g.current_user.id)
        if not row.course_name or not row.training_type: raise ValueError("Informe curso e tipo de treinamento.")
        db.session.add(row); db.session.commit()
    except ValueError as exc:
        db.session.rollback(); return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=row.to_dict(), status_code=201)


@bp.get("/rh/historico")
@auth_required
def list_history():
    if denied := _guard(): return denied
    employee_id = request.args.get("colaborador_id", type=int)
    if not employee_id: return api_response(False, error="Informe o colaborador.", status_code=400)
    return api_response(True, data=[row.to_dict() for row in EmployeeHistoryEvent.query.filter_by(employee_id=employee_id).order_by(EmployeeHistoryEvent.occurred_on.desc()).all()])


@bp.post("/rh/historico")
@auth_required
def create_history():
    if denied := _guard(): return denied
    payload = request.get_json(silent=True) or {}
    try:
        row = EmployeeHistoryEvent(employee_id=_employee(payload.get("employee_id")).id, event_type=_clean(payload.get("event_type")) or "", occurred_on=_date(payload.get("occurred_on"), "Data do evento", required=True), description=_clean(payload.get("description")) or "", created_by_user_id=g.current_user.id)
        if not row.event_type or not row.description: raise ValueError("Informe tipo e descricao do evento.")
        db.session.add(row); db.session.commit()
    except ValueError as exc:
        db.session.rollback(); return api_response(False, error=str(exc), status_code=400)
    return api_response(True, data=row.to_dict(), status_code=201)

from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe

from app.extensions import db
from app.models import DashboardTvAccessToken, User
from app.services.maintenance_dashboard_service import (
    DashboardFilters,
    build_dashboard_charts,
    build_dashboard_summary,
)
from app.utils.timezone import now_manaus_naive


TV_ACCESS_MINUTES_MIN = 15
TV_ACCESS_MINUTES_MAX = 24 * 60
TV_ACCESS_DEFAULT_MINUTES = 8 * 60
TV_ACCESS_LAST_USED_WRITE_INTERVAL = timedelta(minutes=5)


def _token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _clean_name(value) -> str:
    name = " ".join(str(value or "TV OPERACIONAL").strip().split())
    if not name:
        return "TV OPERACIONAL"
    if len(name) > 80:
        raise ValueError("Nome do acesso TV deve ter no maximo 80 caracteres.")
    return name


def _expires_in_minutes(value) -> int:
    if value in (None, ""):
        return TV_ACCESS_DEFAULT_MINUTES
    try:
        minutes = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Duracao do acesso TV invalida.") from exc
    if not TV_ACCESS_MINUTES_MIN <= minutes <= TV_ACCESS_MINUTES_MAX:
        raise ValueError(
            f"Duracao do acesso TV deve ficar entre {TV_ACCESS_MINUTES_MIN} e {TV_ACCESS_MINUTES_MAX} minutos."
        )
    return minutes


def create_tv_access_token(user: User, payload: dict) -> tuple[DashboardTvAccessToken, str]:
    now = now_manaus_naive()
    raw_token = f"tv_{token_urlsafe(32)}"
    access = DashboardTvAccessToken(
        name=_clean_name(payload.get("name")),
        token_hash=_token_hash(raw_token),
        created_by_user_id=user.id,
        expires_at=now + timedelta(minutes=_expires_in_minutes(payload.get("expires_in_minutes"))),
    )
    db.session.add(access)
    db.session.commit()
    return access, raw_token


def list_tv_access_tokens() -> list[dict]:
    return [
        item.to_dict()
        for item in DashboardTvAccessToken.query.order_by(DashboardTvAccessToken.created_at.desc()).all()
    ]


def revoke_tv_access_token(access_id: int) -> DashboardTvAccessToken:
    access = db.session.get(DashboardTvAccessToken, access_id)
    if not access:
        raise ValueError("Acesso TV nao encontrado.")
    if access.revoked_at is None:
        access.revoked_at = now_manaus_naive()
        db.session.commit()
    return access


def verify_tv_access_token(raw_token: str | None) -> DashboardTvAccessToken | None:
    token = str(raw_token or "").strip()
    if not token or len(token) > 256:
        return None
    access = DashboardTvAccessToken.query.filter_by(token_hash=_token_hash(token)).first()
    now = now_manaus_naive()
    if not access or access.revoked_at is not None or access.expires_at <= now:
        return None
    if access.last_used_at is None or now - access.last_used_at >= TV_ACCESS_LAST_USED_WRITE_INTERVAL:
        access.last_used_at = now
        db.session.commit()
    return access


def build_tv_dashboard_payload(filters: DashboardFilters) -> dict:
    summary = build_dashboard_summary(filters)
    charts = build_dashboard_charts(filters)
    kpis = summary.get("kpis") or {}
    work_orders = kpis.get("work_orders") or {}
    reliability = kpis.get("reliability") or {}
    return {
        "generated_at": summary.get("generated_at"),
        "filters": summary.get("filters"),
        "kpis": {
            "equipment_total": kpis.get("equipment_total", 0),
            "equipment_available": kpis.get("equipment_available", 0),
            "equipment_unavailable": kpis.get("equipment_unavailable", 0),
            "equipment_in_maintenance": kpis.get("equipment_in_maintenance", 0),
            "availability_percentage": kpis.get("availability_percentage"),
            "work_orders": {
                "open": work_orders.get("open", 0),
                "overdue": work_orders.get("overdue", 0),
                "blocked_by_material": work_orders.get("blocked_by_material", 0),
                "completed_in_period": work_orders.get("completed_in_period", 0),
            },
            "preventives_due_or_overdue": kpis.get("preventives_due_or_overdue", 0),
            "reliability": {
                "mttr_hours": reliability.get("mttr_hours"),
                "mtbf_hours": reliability.get("mtbf_hours"),
            },
        },
        "availability_by_family": [
            {
                "family_code": item.get("family_code"),
                "family_name": item.get("family_name"),
                "total": item.get("total", 0),
                "available": item.get("available", 0),
                "unavailable": item.get("unavailable", 0),
                "maintenance": item.get("maintenance", 0),
                "availability_percentage": item.get("availability_percentage"),
            }
            for item in charts.get("availability_by_family") or []
        ],
        "operational_status": charts.get("operational_status") or [],
        "work_orders_by_status": charts.get("work_orders_by_status") or [],
        "preventives_by_status": charts.get("preventives_by_status") or [],
        "operational_events_trend": [
            {"date": item.get("date"), "total": item.get("total", 0)}
            for item in charts.get("operational_events_trend") or []
        ],
    }

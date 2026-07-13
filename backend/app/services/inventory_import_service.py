from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from app.extensions import db
from app.models import Vehicle


def _normalize_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_year(value) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    return text


def discover_inventory_file(configured_path: str | None = None) -> Path | None:
    if not configured_path:
        return None

    project_root = Path(__file__).resolve().parents[3]
    path = Path(configured_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        return None
    if not path.is_relative_to(project_root):
        return None
    return path


def _map_carreta(row: tuple) -> dict:
    status = _normalize_text(row[9]) or "ON"
    return {
        "frota": _normalize_text(row[1]),
        "tipo": "carreta",
        "placa": _normalize_text(row[3]) or "S/PLACA",
        "ano": _normalize_year(row[4]),
        "chassi": _normalize_text(row[5]),
        "configuracao": _normalize_text(row[6]),
        "modelo": _normalize_text(row[7]) or "CARRETA",
        "atividade": _normalize_text(row[8]),
        "status": status,
        "descricao": _normalize_text(row[11]),
        "local": None,
        "ativo": status.upper() != "OFF",
    }


def _map_cavalo(row: tuple) -> dict:
    status = _normalize_text(row[6]) or "ON"
    return {
        "frota": _normalize_text(row[1]),
        "tipo": "cavalo",
        "placa": _normalize_text(row[3]) or "S/PLACA",
        "ano": _normalize_year(row[2]),
        "chassi": _normalize_text(row[5]),
        "configuracao": None,
        "modelo": _normalize_text(row[4]) or "CAVALO MECANICO",
        "atividade": _normalize_text(row[8]),
        "status": status,
        "descricao": _normalize_text(row[8]),
        "local": _normalize_text(row[7]),
        "ativo": status.upper() != "OFF",
    }


def import_inventory_data(path: Path) -> dict:
    workbook = load_workbook(path, read_only=True, data_only=True)
    imported = 0
    updated = 0

    sheets = {
        "CARRETAS": _map_carreta,
        "CAVALOS": _map_cavalo,
    }

    for sheet_name, mapper in sheets.items():
        worksheet = workbook[sheet_name]
        for row in worksheet.iter_rows(min_row=2, values_only=True):
            payload = mapper(row)
            if not payload["frota"]:
                continue

            vehicle = Vehicle.query.filter_by(frota=payload["frota"]).first()
            if vehicle is None:
                vehicle = Vehicle(**payload)
                db.session.add(vehicle)
                imported += 1
                continue

            preserved_photo = vehicle.foto_path
            for key, value in payload.items():
                setattr(vehicle, key, value)
            vehicle.foto_path = preserved_photo
            vehicle.ativo = (vehicle.status or "").upper() not in {"RETIRADO", "OFF"}
            updated += 1

    db.session.commit()
    from app.services.equipment_structure_service import seed_equipment_structure

    seed_equipment_structure()
    workbook.close()
    return {
        "arquivo": str(path),
        "importados": imported,
        "atualizados": updated,
    }

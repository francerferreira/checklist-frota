from __future__ import annotations

import unicodedata
import re

from flask import has_app_context
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import ChecklistCatalogItem


CAVALO_ITEMS = [
    "FAROL ALTO",
    "FAROL BAIXO",
    "FAROL ESQUERDO",
    "FAROL DIREITO",
    "LUZ DE MILHA ESQUERDA",
    "LUZ DE MILHA DIREITA",
    "LUZ DE POSIÇÃO ESQUERDA",
    "LUZ DE POSIÇÃO DIREITA",
    "LANTERNA DIANTEIRA",
    "LANTERNA TRASEIRA",
    "SETAS E PISCA-ALERTA LADO ESQUERDO",
    "SETAS E PISCA-ALERTA LADO DIREITO",
    "LUZ DE FREIO",
    "BUZINA",
    "PAINEL DE INSTRUMENTOS",
    "BOTÕES DO PAINEL",
    "SINAIS DE ANOMALIAS NO PAINEL",
    "INDICADOR DE COMBUSTÍVEL",
    "BATERIA",
    "NÍVEL DO ÓLEO DO MOTOR",
    "NÍVEL DO FLUIDO DE ARREFECIMENTO",
    "NÍVEL DO FLUIDO DE FREIO",
    "FILTRO SEPARADOR DE ÁGUA",
    "RADIADOR",
    "VAZAMENTOS APARENTES",
    "SISTEMA DE ESCAPAMENTO",
    "FREIO DE SERVIÇO",
    "FREIO DE ESTACIONAMENTO",
    "SUSPENSÃO DIANTEIRA",
    "SUSPENSÃO TRASEIRA",
    "AMORTECEDORES",
    "PNEUS DIANTEIROS",
    "PNEUS TRASEIROS",
    "PARAFUSOS DE RODA",
    "TAMPAS DOS PARAFUSOS DAS RODAS",
    "QUINTA RODA",
    "TRAVA DA QUINTA RODA",
    "ENGATE ELÉTRICO",
    "ENGATE PNEUMÁTICO",
    "PAINEL DE PROTEÇÃO DO PARALAMAS",
    "ESCADA DE ACESSO LADO ESQUERDO",
    "ESCADA DE ACESSO LADO DIREITO",
    "PARALAMAS ESQUERDO",
    "PARALAMAS DIREITO",
    "TAMPA DO ARLA",
    "TAMPA DO TANQUE DE COMBUSTÍVEL",
    "TAMPA DO LÍQUIDO DE ARREFECIMENTO",
    "TAMPAS DO PARA-CHOQUE",
    "PROTEÇÃO DO ARLA",
    "GRADE DO FAROL ESQUERDO",
    "GRADE DO FAROL DIREITO",
    "PLACA DIANTEIRA",
    "PLACA TRASEIRA",
    "RETROVISOR ESQUERDO",
    "RETROVISOR DIREITO",
    "PARA-BRISA",
    "LIMPADOR DO PARA-BRISA",
    "LOGO SCANIA FRONTAL",
    "SLIDES DA FRONTAL",
    "LOGO MODELO FRONTAL",
    "FRONTAL DO CAMINHÃO",
    "CINTO DE SEGURANÇA",
    "BANCO DO MOTORISTA",
    "AR-CONDICIONADO",
    "EXTINTOR",
]


CARRETA_ITEMS = [
    "ESTRUTURA DO CHASSI",
    "TRAVAMENTO DO PINO REI",
    "PINO REI",
    "SUSPENSÃO",
    "EIXOS",
    "CUBOS DE RODA",
    "PNEUS",
    "PARAFUSOS DE RODA",
    "FREIOS",
    "EQUIPAMENTO FREIO ESTACIONÁRIO",
    "MANGUEIRAS DE AR",
    "CONEXÕES PNEUMÁTICAS",
    "VÁLVULA PNEUMÁTICA DE FREIO",
    "LANTERNA TRASEIRA ESQUERDA",
    "LANTERNA TRASEIRA DIREITA",
    "LUZES DE FREIO",
    "PARALAMAS ESQUERDO",
    "PARALAMAS DIREITO",
    "PINO DO PÉ DE APOIO",
]


CHECKLIST_CATALOG = {
    "cavalo": CAVALO_ITEMS,
    "carreta": CARRETA_ITEMS,
}


DEPRECATED_CATALOG_ITEMS = {
    "cavalo": [
        "Painel de protecao do paralamas - compartimento 1",
        "Painel de protecao do paralamas - compartimento 2",
        "Painel de protecao do paralamas - compartimento 3",
        "Painel de protecao do paralamas - compartimento 4",
        "Painel de protecao do paralamas - compartimento 5",
        "Painel de protecao do paralamas - compartimento 6",
        "Painel de proteção do paralamas - compartimento 1",
        "Painel de proteção do paralamas - compartimento 2",
        "Painel de proteção do paralamas - compartimento 3",
        "Painel de proteção do paralamas - compartimento 4",
        "Painel de proteção do paralamas - compartimento 5",
        "Painel de proteção do paralamas - compartimento 6",
    ]
}


def _normalize_vehicle_type(vehicle_type: str) -> str:
    normalized_type = (vehicle_type or "").strip().lower()
    if normalized_type not in CHECKLIST_CATALOG:
        raise ValueError("Tipo de veículo inválido para checklist.")
    return normalized_type


def _default_items_for_type(vehicle_type: str) -> list[str]:
    return list(CHECKLIST_CATALOG[_normalize_vehicle_type(vehicle_type)])


def _add_default_items() -> None:
    for vehicle_type, items in CHECKLIST_CATALOG.items():
        for position, item_name in enumerate(items, 1):
            db.session.add(
                ChecklistCatalogItem(
                    vehicle_type=vehicle_type,
                    item_nome=item_name,
                    position=position,
                    ativo=True,
                )
            )


def seed_checklist_catalog_items() -> None:
    if ChecklistCatalogItem.query.count() == 0:
        _add_default_items()
        db.session.commit()
        return

    for vehicle_type, default_items in CHECKLIST_CATALOG.items():
        default_keys = {normalize_item_name(item_name): item_name for item_name in default_items}
        deprecated_keys = {
            normalize_item_name(item_name)
            for item_name in DEPRECATED_CATALOG_ITEMS.get(vehicle_type, [])
        }
        rows = ChecklistCatalogItem.query.filter_by(vehicle_type=vehicle_type).all()
        rows_by_key: dict[str, list[ChecklistCatalogItem]] = {}
        for row in rows:
            rows_by_key.setdefault(normalize_item_name(row.item_nome), []).append(row)

        for position, item_name in enumerate(default_items, 1):
            key = normalize_item_name(item_name)
            matching_rows = rows_by_key.get(key, [])
            row = next((item for item in matching_rows if item.item_nome == item_name), None)
            if row is None and matching_rows:
                row = matching_rows[0]
            if row:
                row.item_nome = item_name
                row.position = position
                row.ativo = True
                for duplicate in matching_rows:
                    if duplicate.id != row.id:
                        duplicate.ativo = False
                continue

            db.session.add(
                ChecklistCatalogItem(
                    vehicle_type=vehicle_type,
                    item_nome=item_name,
                    position=position,
                    ativo=True,
                )
            )

        for row in rows:
            key = normalize_item_name(row.item_nome)
            if key in deprecated_keys and key not in default_keys:
                row.ativo = False
            elif key not in default_keys and row.ativo:
                row.item_nome = row.item_nome.strip().upper()

    db.session.commit()


def get_catalog_rows(vehicle_type: str | None = None, *, include_inactive: bool = False) -> list[ChecklistCatalogItem]:
    query = ChecklistCatalogItem.query
    if vehicle_type:
        query = query.filter_by(vehicle_type=_normalize_vehicle_type(vehicle_type))
    if not include_inactive:
        query = query.filter_by(ativo=True)
    return query.order_by(
        ChecklistCatalogItem.vehicle_type.asc(),
        ChecklistCatalogItem.position.asc(),
        ChecklistCatalogItem.item_nome.asc(),
    ).all()


def build_checklist_catalog(*, include_inactive: bool = False) -> dict[str, list[dict]]:
    if not has_app_context():
        return {
            vehicle_type: [
                {
                    "id": None,
                    "tipo": vehicle_type,
                    "vehicle_type": vehicle_type,
                    "item_nome": item_name,
                    "position": position,
                    "foto_path": None,
                    "ativo": True,
                }
                for position, item_name in enumerate(items, 1)
            ]
            for vehicle_type, items in CHECKLIST_CATALOG.items()
        }

    try:
        rows = get_catalog_rows(include_inactive=include_inactive)
    except SQLAlchemyError:
        rows = []

    if not rows:
        return {
            vehicle_type: [
                {
                    "id": None,
                    "tipo": vehicle_type,
                    "vehicle_type": vehicle_type,
                    "item_nome": item_name,
                    "position": position,
                    "foto_path": None,
                    "ativo": True,
                }
                for position, item_name in enumerate(items, 1)
            ]
            for vehicle_type, items in CHECKLIST_CATALOG.items()
        }

    catalog = {"cavalo": [], "carreta": []}
    for row in rows:
        catalog.setdefault(row.vehicle_type, []).append(row.to_dict())
    return catalog


def get_items_for_vehicle_type(vehicle_type: str) -> list[str]:
    normalized_type = _normalize_vehicle_type(vehicle_type)
    if not has_app_context():
        return _default_items_for_type(normalized_type)

    try:
        rows = get_catalog_rows(normalized_type)
    except SQLAlchemyError:
        return _default_items_for_type(normalized_type)

    if not rows:
        return _default_items_for_type(normalized_type)
    return [row.item_nome for row in rows]


def normalize_item_name(name: str) -> str:
    without_accents = "".join(
        character
        for character in unicodedata.normalize("NFD", name or "")
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"[^a-zA-Z0-9]+", "", without_accents).lower()

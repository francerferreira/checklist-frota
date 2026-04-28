from __future__ import annotations

import re
import unicodedata

from flask import has_app_context
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import ChecklistCatalogItem
from app.services.vehicle_type_service import normalize_checklist_vehicle_type


CAVALO_ITEMS = [
    "FAROL ALTO",
    "FAROL BAIXO",
    "FAROL ESQUERDO",
    "FAROL DIREITO",
    "LUZ DE MILHA ESQUERDA",
    "LUZ DE MILHA DIREITA",
    "LUZ DE POSICAO ESQUERDA",
    "LUZ DE POSICAO DIREITA",
    "LANTERNA DIANTEIRA",
    "LANTERNA TRASEIRA",
    "SETAS E PISCA-ALERTA LADO ESQUERDO",
    "SETAS E PISCA-ALERTA LADO DIREITO",
    "LUZ DE FREIO",
    "BUZINA",
    "PAINEL DE INSTRUMENTOS",
    "BOTOES DO PAINEL",
    "SINAIS DE ANOMALIAS NO PAINEL",
    "INDICADOR DE COMBUSTIVEL",
    "BATERIA",
    "NIVEL DO OLEO DO MOTOR",
    "NIVEL DO FLUIDO DE ARREFECIMENTO",
    "NIVEL DO FLUIDO DE FREIO",
    "FILTRO SEPARADOR DE AGUA",
    "RADIADOR",
    "VAZAMENTOS APARENTES",
    "SISTEMA DE ESCAPAMENTO",
    "FREIO DE SERVICO",
    "FREIO DE ESTACIONAMENTO",
    "SUSPENSAO DIANTEIRA",
    "SUSPENSAO TRASEIRA",
    "AMORTECEDORES",
    "PNEUS DIANTEIROS",
    "PNEUS TRASEIROS",
    "PARAFUSOS DE RODA",
    "TAMPAS DOS PARAFUSOS DAS RODAS",
    "QUINTA RODA",
    "TRAVA DA QUINTA RODA",
    "ENGATE ELETRICO",
    "ENGATE PNEUMATICO",
    "PAINEL DE PROTECAO DO PARALAMAS",
    "ESCADA DE ACESSO LADO ESQUERDO",
    "ESCADA DE ACESSO LADO DIREITO",
    "PARALAMAS ESQUERDO",
    "PARALAMAS DIREITO",
    "TAMPA DO ARLA",
    "TAMPA DO TANQUE DE COMBUSTIVEL",
    "TAMPA DO LIQUIDO DE ARREFECIMENTO",
    "TAMPAS DO PARA-CHOQUE",
    "PROTECAO DO ARLA",
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
    "FRONTAL DO CAMINHAO",
    "CINTO DE SEGURANCA",
    "BANCO DO MOTORISTA",
    "AR-CONDICIONADO",
    "EXTINTOR",
]

CARRETA_ITEMS = [
    "ESTRUTURA DO CHASSI",
    "TRAVAMENTO DO PINO REI",
    "PINO REI",
    "SUSPENSAO",
    "EIXOS",
    "CUBOS DE RODA",
    "PNEUS",
    "PARAFUSOS DE RODA",
    "FREIOS",
    "EQUIPAMENTO FREIO ESTACIONARIO",
    "MANGUEIRAS DE AR",
    "CONEXOES PNEUMATICAS",
    "VALVULA PNEUMATICA DE FREIO",
    "LANTERNA TRASEIRA ESQUERDA",
    "LANTERNA TRASEIRA DIREITA",
    "LUZES DE FREIO",
    "PARALAMAS ESQUERDO",
    "PARALAMAS DIREITO",
    "PINO DO PE DE APOIO",
]

CARRO_SIMPLES_ITEMS = [
    "FAROIS",
    "LANTERNAS",
    "SETAS E PISCA-ALERTA",
    "LUZ DE FREIO",
    "BUZINA",
    "LIMPADOR DE PARA-BRISA",
    "PARA-BRISA",
    "RETROVISORES",
    "PNEUS",
    "ESTEPE",
    "NIVEL DE COMBUSTIVEL",
    "NIVEL DE OLEO DO MOTOR",
    "NIVEL DA AGUA OU ARREFECIMENTO",
    "VAZAMENTOS APARENTES",
    "FREIO",
    "FREIO DE ESTACIONAMENTO",
    "CINTO DE SEGURANCA",
    "BANCO DO MOTORISTA",
    "PORTAS E TRAVAS",
    "AR-CONDICIONADO",
    "EXTINTOR",
    "DOCUMENTACAO DO VEICULO",
]

CAVALO_AUXILIAR_ITEMS = [
    "FAROL ALTO E BAIXO",
    "LANTERNAS",
    "SETAS E PISCA-ALERTA",
    "LUZ DE FREIO",
    "BUZINA",
    "PAINEL DE INSTRUMENTOS",
    "INDICADORES DE ANOMALIA NO PAINEL",
    "NIVEL DE COMBUSTIVEL",
    "NIVEL DE OLEO DO MOTOR",
    "NIVEL DO ARREFECIMENTO",
    "VAZAMENTOS APARENTES",
    "FREIO DE SERVICO",
    "FREIO DE ESTACIONAMENTO",
    "PNEUS DIANTEIROS",
    "PNEUS TRASEIROS",
    "PARAFUSOS DE RODA",
    "SUSPENSAO",
    "RETROVISORES",
    "PARA-BRISA",
    "LIMPADOR DE PARA-BRISA",
    "ENGATE ELETRICO",
    "ENGATE PNEUMATICO",
    "QUINTA RODA",
    "TRAVA DA QUINTA RODA",
    "ESCADA DE ACESSO",
    "PARACHOQUE E FRONTAL",
    "PLACA DIANTEIRA E TRASEIRA",
    "CINTO DE SEGURANCA",
    "BANCO DO MOTORISTA",
    "EXTINTOR",
]

AMBULANCIA_ITEMS = [
    "FAROIS",
    "LANTERNAS",
    "SETAS E PISCA-ALERTA",
    "LUZ DE FREIO",
    "SIRENE",
    "GIROFLEX OU SINALIZADOR DE EMERGENCIA",
    "BUZINA",
    "PAINEL DE INSTRUMENTOS",
    "NIVEL DE COMBUSTIVEL",
    "NIVEL DE OLEO DO MOTOR",
    "NIVEL DA AGUA OU ARREFECIMENTO",
    "VAZAMENTOS APARENTES",
    "FREIO",
    "FREIO DE ESTACIONAMENTO",
    "PNEUS",
    "ESTEPE",
    "RETROVISORES",
    "PARA-BRISA",
    "LIMPADOR DE PARA-BRISA",
    "CINTO DE SEGURANCA",
    "BANCO DO MOTORISTA",
    "AR-CONDICIONADO DA CABINE",
    "AR-CONDICIONADO DO COMPARTIMENTO",
    "MACA",
    "OXIGENIO",
    "KIT DE PRIMEIROS SOCORROS",
    "EXTINTOR",
    "PORTAS TRASEIRAS E LATERAIS",
]

CAMINHAO_PIPA_ITEMS = [
    "FAROIS",
    "LANTERNAS",
    "SETAS E PISCA-ALERTA",
    "LUZ DE FREIO",
    "BUZINA",
    "PAINEL DE INSTRUMENTOS",
    "NIVEL DE COMBUSTIVEL",
    "NIVEL DE OLEO DO MOTOR",
    "NIVEL DA AGUA OU ARREFECIMENTO",
    "VAZAMENTOS APARENTES",
    "FREIO DE SERVICO",
    "FREIO DE ESTACIONAMENTO",
    "PNEUS",
    "PARAFUSOS DE RODA",
    "RETROVISORES",
    "PARA-BRISA",
    "LIMPADOR DE PARA-BRISA",
    "TANQUE DE AGUA",
    "MANGUEIRAS",
    "BOMBA DE AGUA",
    "REGISTRO E CONEXOES",
    "VAZAMENTO NO SISTEMA DE AGUA",
    "ESCADA DE ACESSO",
    "EXTINTOR",
]

CAMINHAO_BRIGADA_ITEMS = [
    "FAROIS",
    "LANTERNAS",
    "SETAS E PISCA-ALERTA",
    "LUZ DE FREIO",
    "SIRENE",
    "GIROFLEX OU SINALIZADOR DE EMERGENCIA",
    "BUZINA",
    "PAINEL DE INSTRUMENTOS",
    "NIVEL DE COMBUSTIVEL",
    "NIVEL DE OLEO DO MOTOR",
    "NIVEL DA AGUA OU ARREFECIMENTO",
    "VAZAMENTOS APARENTES",
    "FREIO",
    "FREIO DE ESTACIONAMENTO",
    "PNEUS",
    "RETROVISORES",
    "PARA-BRISA",
    "LIMPADOR DE PARA-BRISA",
    "TANQUE DE AGUA",
    "BOMBA DE INCENDIO",
    "MANGUEIRAS DE COMBATE",
    "ESGUICHO OU CANHAO",
    "CONEXOES",
    "EQUIPAMENTOS DE EMERGENCIA",
    "EXTINTOR",
]

ONIBUS_ITEMS = [
    "FAROIS",
    "LANTERNAS",
    "SETAS E PISCA-ALERTA",
    "LUZ DE FREIO",
    "BUZINA",
    "PAINEL DE INSTRUMENTOS",
    "NIVEL DE COMBUSTIVEL",
    "NIVEL DE OLEO DO MOTOR",
    "NIVEL DA AGUA OU ARREFECIMENTO",
    "VAZAMENTOS APARENTES",
    "FREIO",
    "FREIO DE ESTACIONAMENTO",
    "PNEUS",
    "RETROVISORES",
    "PARA-BRISA",
    "LIMPADOR DE PARA-BRISA",
    "PORTAS DE ACESSO",
    "BANCOS",
    "CINTOS",
    "ILUMINACAO INTERNA",
    "AR-CONDICIONADO",
    "EXTINTOR",
]

VAN_ITEMS = [
    "FAROIS",
    "LANTERNAS",
    "SETAS E PISCA-ALERTA",
    "LUZ DE FREIO",
    "BUZINA",
    "PAINEL DE INSTRUMENTOS",
    "NIVEL DE COMBUSTIVEL",
    "NIVEL DE OLEO DO MOTOR",
    "NIVEL DA AGUA OU ARREFECIMENTO",
    "VAZAMENTOS APARENTES",
    "FREIO",
    "FREIO DE ESTACIONAMENTO",
    "PNEUS",
    "ESTEPE",
    "RETROVISORES",
    "PARA-BRISA",
    "LIMPADOR DE PARA-BRISA",
    "PORTAS",
    "BANCOS",
    "AR-CONDICIONADO",
    "EXTINTOR",
]

CHECKLIST_CATALOG = {
    "cavalo": CAVALO_ITEMS,
    "carreta": CARRETA_ITEMS,
    "carro_simples": CARRO_SIMPLES_ITEMS,
    "cavalo_auxiliar": CAVALO_AUXILIAR_ITEMS,
    "ambulancia": AMBULANCIA_ITEMS,
    "caminhao_pipa": CAMINHAO_PIPA_ITEMS,
    "caminhao_brigada": CAMINHAO_BRIGADA_ITEMS,
    "onibus": ONIBUS_ITEMS,
    "van": VAN_ITEMS,
}

DEPRECATED_CATALOG_ITEMS = {
    "cavalo": [
        "Painel de protecao do paralamas - compartimento 1",
        "Painel de protecao do paralamas - compartimento 2",
        "Painel de protecao do paralamas - compartimento 3",
        "Painel de protecao do paralamas - compartimento 4",
        "Painel de protecao do paralamas - compartimento 5",
        "Painel de protecao do paralamas - compartimento 6",
        "Painel de protecao do paralamas - compartimento 1",
        "Painel de protecao do paralamas - compartimento 2",
        "Painel de protecao do paralamas - compartimento 3",
        "Painel de protecao do paralamas - compartimento 4",
        "Painel de protecao do paralamas - compartimento 5",
        "Painel de protecao do paralamas - compartimento 6",
    ]
}


def _normalize_vehicle_type(vehicle_type: str) -> str:
    return normalize_checklist_vehicle_type(vehicle_type)


def _default_items_for_type(vehicle_type: str) -> list[str]:
    return list(CHECKLIST_CATALOG[_normalize_vehicle_type(vehicle_type)])


def _normalize_row_item_name(item_name: str | None) -> str:
    return (item_name or "").strip().upper()


def _deduplicate_active_rows_by_position(rows: list[ChecklistCatalogItem]) -> bool:
    changed = False
    rows_by_position: dict[int, list[ChecklistCatalogItem]] = {}
    for row in rows:
        rows_by_position.setdefault(int(row.position or 0), []).append(row)

    for position_rows in rows_by_position.values():
        active_rows = [row for row in position_rows if row.ativo]
        if len(active_rows) <= 1:
            continue

        active_rows.sort(
            key=lambda row: (
                row.updated_at or row.created_at,
                row.id or 0,
            ),
            reverse=True,
        )
        for duplicate in active_rows[1:]:
            if duplicate.ativo:
                duplicate.ativo = False
                changed = True

    return changed


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
    inspector = inspect(db.engine)
    check_constraints = inspector.get_check_constraints("checklist_catalog_items")
    check_sql = " ".join((item.get("sqltext") or "") for item in check_constraints).lower()

    def db_accepts_type(vehicle_type: str) -> bool:
        if not check_sql:
            return True
        return (f"'{vehicle_type}'" in check_sql) or (f'"{vehicle_type}"' in check_sql)

    if ChecklistCatalogItem.query.count() == 0:
        for vehicle_type, items in CHECKLIST_CATALOG.items():
            if not db_accepts_type(vehicle_type):
                continue
            for position, item_name in enumerate(items, 1):
                db.session.add(
                    ChecklistCatalogItem(
                        vehicle_type=vehicle_type,
                        item_nome=item_name,
                        position=position,
                        ativo=True,
                    )
                )
        db.session.commit()
        return

    changed = False
    for vehicle_type, default_items in CHECKLIST_CATALOG.items():
        if not db_accepts_type(vehicle_type):
            continue

        default_keys = {normalize_item_name(item_name) for item_name in default_items}
        deprecated_keys = {
            normalize_item_name(item_name)
            for item_name in DEPRECATED_CATALOG_ITEMS.get(vehicle_type, [])
        }
        rows = (
            ChecklistCatalogItem.query.filter_by(vehicle_type=vehicle_type)
            .order_by(ChecklistCatalogItem.position.asc(), ChecklistCatalogItem.id.asc())
            .all()
        )

        if not rows:
            for position, item_name in enumerate(default_items, 1):
                db.session.add(
                    ChecklistCatalogItem(
                        vehicle_type=vehicle_type,
                        item_nome=item_name,
                        position=position,
                        ativo=True,
                    )
                )
            changed = True
            continue

        for row in rows:
            normalized_name = _normalize_row_item_name(row.item_nome)
            if row.item_nome != normalized_name:
                row.item_nome = normalized_name
                changed = True

            key = normalize_item_name(row.item_nome)
            if key in deprecated_keys and key not in default_keys and row.ativo:
                row.ativo = False
                changed = True

        if _deduplicate_active_rows_by_position(rows):
            changed = True

    if changed:
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
    default_catalog = {
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

    if not has_app_context():
        return default_catalog

    try:
        rows = get_catalog_rows(include_inactive=include_inactive)
    except SQLAlchemyError:
        rows = []

    if not rows:
        return default_catalog

    catalog = {vehicle_type: list(items) for vehicle_type, items in default_catalog.items()}
    rows_by_type: dict[str, list[dict]] = {}
    for row in rows:
        rows_by_type.setdefault(row.vehicle_type, []).append(row.to_dict())
    for vehicle_type, items in rows_by_type.items():
        catalog[vehicle_type] = items
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

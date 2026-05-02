from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.checklist_catalog import (  # noqa: E402
    build_checklist_catalog,
    classify_catalog_item_group,
    enrich_catalog_item_payload,
    get_group_rules_for_vehicle_type,
)


def test_classify_catalog_item_group_maps_existing_side_item_to_parent():
    result = classify_catalog_item_group("cavalo", "PARALAMAS DIREITO")

    assert result["item_principal"] == "PARALAMAS"
    assert result["tipo_agrupamento"] == "lado"
    assert result["parte"] == "LADO DIREITO"
    assert result["item_origem"] == "PARALAMAS DIREITO"


def test_classify_catalog_item_group_keeps_simple_item_unchanged():
    result = classify_catalog_item_group("cavalo", "BUZINA")

    assert result["item_principal"] == "BUZINA"
    assert result["tipo_agrupamento"] == "simples"
    assert result["parte"] is None
    assert result["item_origem"] == "BUZINA"


def test_get_group_rules_for_vehicle_type_returns_expected_carreta_rules():
    rules = get_group_rules_for_vehicle_type("carreta")
    rule_names = {rule["item_principal"] for rule in rules}

    assert "LANTERNA TRASEIRA" in rule_names
    assert "PARALAMAS" in rule_names


def test_enrich_catalog_item_payload_adds_grouping_metadata():
    result = enrich_catalog_item_payload(
        {
            "tipo": "cavalo",
            "vehicle_type": "cavalo",
            "item_nome": "RETROVISOR ESQUERDO",
        }
    )

    assert result["agrupamento"]["item_principal"] == "RETROVISOR"
    assert result["agrupamento"]["parte"] == "LADO ESQUERDO"


def test_build_checklist_catalog_includes_grouping_metadata_without_app_context():
    catalog = build_checklist_catalog()
    cavalo_items = catalog["cavalo"]
    item = next(row for row in cavalo_items if row["item_nome"] == "PARALAMAS DIREITO")

    assert item["agrupamento"]["item_principal"] == "PARALAMAS"
    assert item["agrupamento"]["parte"] == "LADO DIREITO"

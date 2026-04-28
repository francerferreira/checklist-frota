from __future__ import annotations

from collections.abc import Iterable


CHECKLIST_VEHICLE_TYPES = (
    "cavalo",
    "carreta",
    "carro_simples",
    "cavalo_auxiliar",
    "ambulancia",
    "caminhao_pipa",
    "caminhao_brigada",
    "onibus",
    "van",
)

VEHICLE_TYPE_LABELS = {
    "cavalo": "Cavalo",
    "carreta": "Carreta",
    "carro_simples": "Carro simples",
    "cavalo_auxiliar": "Cavalo auxiliar",
    "ambulancia": "Ambulancia",
    "caminhao_pipa": "Caminhao pipa",
    "caminhao_brigada": "Caminhao brigada",
    "onibus": "Onibus",
    "van": "Van",
    "auxiliar": "Auxiliar legado",
}

LEGACY_AUXILIARY_TYPES = {"auxiliar"}


def supported_checklist_vehicle_types() -> tuple[str, ...]:
    return CHECKLIST_VEHICLE_TYPES


def is_supported_checklist_vehicle_type(vehicle_type: str | None) -> bool:
    try:
        normalize_checklist_vehicle_type(vehicle_type)
        return True
    except ValueError:
        return False


def normalize_checklist_vehicle_type(vehicle_type: str | None) -> str:
    normalized_type = str(vehicle_type or "").strip().lower()
    if normalized_type not in CHECKLIST_VEHICLE_TYPES:
        raise ValueError("Tipo de veiculo invalido para checklist.")
    return normalized_type


def vehicle_type_options(*, include_legacy_auxiliar: bool = False) -> list[tuple[str, str]]:
    options = [(VEHICLE_TYPE_LABELS[item], item) for item in CHECKLIST_VEHICLE_TYPES]
    if include_legacy_auxiliar:
        options.append((VEHICLE_TYPE_LABELS["auxiliar"], "auxiliar"))
    return options


def infer_auxiliary_vehicle_type(
    frota: str | None,
    modelo: str | None = None,
    atividade: str | None = None,
    *,
    fallback: str = "carro_simples",
) -> str:
    text = " ".join(str(part or "").strip().upper() for part in (frota, modelo, atividade))
    frota_text = str(frota or "").strip().upper()

    if any(token in text for token in ("USB-1", "USB-2", "AMBULANCIA")):
        return "ambulancia"
    if "CAMINHAO PIPA" in text:
        return "caminhao_pipa"
    if any(token in frota_text for token in ("CAP-515", "CA-05", "CA-06")):
        return "cavalo_auxiliar"
    if "ONIBUS" in text or "CA-01" in frota_text:
        return "onibus"
    if "VAN" in text or "CA-02" in frota_text:
        return "van"
    if any(token in text for token in ("MONTANA", "GOL")):
        return "carro_simples"
    if "BRIGADA" in text and "PIPA" not in text:
        return "caminhao_brigada"
    return fallback


def resolve_vehicle_type_for_checklist(vehicle_or_type, *context_parts: str | None) -> str:
    if isinstance(vehicle_or_type, str) or vehicle_or_type is None:
        vehicle_type = str(vehicle_or_type or "").strip().lower()
        if vehicle_type in CHECKLIST_VEHICLE_TYPES:
            return vehicle_type
        if vehicle_type in LEGACY_AUXILIARY_TYPES:
            return infer_auxiliary_vehicle_type(*context_parts)
        raise ValueError("Tipo de veiculo invalido para checklist.")

    vehicle = vehicle_or_type
    vehicle_type = str(getattr(vehicle, "tipo", "") or "").strip().lower()
    if vehicle_type in CHECKLIST_VEHICLE_TYPES:
        return vehicle_type
    if vehicle_type in LEGACY_AUXILIARY_TYPES:
        return infer_auxiliary_vehicle_type(
            getattr(vehicle, "frota", None),
            getattr(vehicle, "modelo", None),
            getattr(vehicle, "atividade", None),
        )
    raise ValueError("Tipo de veiculo invalido para checklist.")


def checklist_vehicle_type_set(extra_types: Iterable[str] | None = None) -> set[str]:
    values = set(CHECKLIST_VEHICLE_TYPES)
    if extra_types:
        values.update(str(item).strip().lower() for item in extra_types if item)
    return values

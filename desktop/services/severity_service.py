from __future__ import annotations


SEVERITY_RED = "#A85A5A"
SEVERITY_RED_BG = "#F4E7E7"
SEVERITY_YELLOW = "#5F563F"
SEVERITY_YELLOW_BG = "#ECE7D8"
SEVERITY_GREEN = "#3F5643"
SEVERITY_GREEN_BG = "#E5ECE5"


def severity_from_counts(total: float, open_count: float = 0.0) -> dict:
    total = float(total or 0)
    open_count = float(open_count or 0)
    if open_count >= 3 or total >= 10:
        return _build("Alta", SEVERITY_RED, SEVERITY_RED_BG)
    if open_count >= 1 or total >= 4:
        return _build("Moderada", SEVERITY_YELLOW, SEVERITY_YELLOW_BG)
    return _build("Controlada", SEVERITY_GREEN, SEVERITY_GREEN_BG)


def severity_from_occurrence(item: dict) -> dict:
    if item.get("resolvido"):
        return _build("Controlada", SEVERITY_GREEN, SEVERITY_GREEN_BG)
    return _build("Alta", SEVERITY_RED, SEVERITY_RED_BG)


def overall_executive_status(items: list[dict], total: float = 0.0, open_total: float = 0.0) -> dict:
    if open_total >= 3 or total >= 12:
        return _build("Alta prioridade", SEVERITY_RED, SEVERITY_RED_BG)
    if any(severity_from_counts(item.get("total_nc", 0), item.get("abertas", 0))["label"] == "Alta" for item in items):
        return _build("Alta prioridade", SEVERITY_RED, SEVERITY_RED_BG)
    if open_total >= 1 or total >= 4:
        return _build("Prioridade moderada", SEVERITY_YELLOW, SEVERITY_YELLOW_BG)
    return _build("Cenario controlado", SEVERITY_GREEN, SEVERITY_GREEN_BG)


def _build(label: str, color: str, background: str) -> dict:
    return {
        "label": label,
        "color": color,
        "background": background,
        "style": (
            f"background:{background}; color:{color}; border:1px solid {color}; "
            "border-radius:2px; padding:4px 8px; font-size:12px; font-weight:700;"
        ),
    }

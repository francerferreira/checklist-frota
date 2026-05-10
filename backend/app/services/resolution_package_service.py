from __future__ import annotations

from collections import Counter
from datetime import timedelta

from app.models import ChecklistItem, ResolutionPackage
from app.utils.timezone import now_manaus_naive

DEFAULT_RECURRENCE_WINDOW_DAYS = 15
DEFAULT_RECURRENCE_WEIGHT = 5
DEFAULT_CRITICAL_RECURRENCE_THRESHOLD = 5


def normalized_item_name(item: ChecklistItem | None) -> str:
    if not item:
        return "-"
    return (item.item_principal or item.item_nome or "").strip().upper() or "-"


def derive_package_item_name(items: list[ChecklistItem]) -> str | None:
    if not items:
        return None
    counts = Counter(normalized_item_name(item) for item in items if normalized_item_name(item) != "-")
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def calculate_item_recurrence(item_name: str | None, window_days: int = DEFAULT_RECURRENCE_WINDOW_DAYS) -> int:
    normalized_name = (item_name or "").strip().upper()
    if not normalized_name:
        return 0
    cutoff = now_manaus_naive() - timedelta(days=max(1, int(window_days or DEFAULT_RECURRENCE_WINDOW_DAYS)))
    rows = (
        ChecklistItem.query.filter(ChecklistItem.status == "NC", ChecklistItem.created_at >= cutoff)
        .all()
    )
    return sum(1 for item in rows if normalized_item_name(item) == normalized_name)


def calculate_priority_score(
    linked_items: list[ChecklistItem],
    recurrence_hits: int,
    recurrence_weight: int = DEFAULT_RECURRENCE_WEIGHT,
) -> int:
    if not linked_items:
        return 0
    now = now_manaus_naive()
    unresolved_items = [item for item in linked_items if not item.resolvido]
    target_items = unresolved_items or linked_items
    oldest_days = 0
    if target_items:
        oldest_date = min(item.created_at for item in target_items if item.created_at)
        oldest_days = max(0, (now - oldest_date).days)
    return int((len(target_items) * 10) + min(oldest_days, 30) + (max(0, int(recurrence_hits)) * max(0, int(recurrence_weight))))


def is_critical_recurrence(recurrence_hits: int, threshold: int = DEFAULT_CRITICAL_RECURRENCE_THRESHOLD) -> bool:
    return int(recurrence_hits or 0) >= int(threshold or DEFAULT_CRITICAL_RECURRENCE_THRESHOLD)


def refresh_package_metrics(package: ResolutionPackage) -> ResolutionPackage:
    links = package.links or []
    items = [link.checklist_item for link in links if link.checklist_item]
    item_name = package.item_name or derive_package_item_name(items)
    package.item_name = item_name
    recurrence_hits = calculate_item_recurrence(item_name, package.recurrence_window_days or DEFAULT_RECURRENCE_WINDOW_DAYS)
    package.recurrence_hits = recurrence_hits
    package.priority_score = calculate_priority_score(items, recurrence_hits, package.recurrence_weight or DEFAULT_RECURRENCE_WEIGHT)
    package.critical_recurrence = is_critical_recurrence(recurrence_hits)
    return package

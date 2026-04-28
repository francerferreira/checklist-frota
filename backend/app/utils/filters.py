from __future__ import annotations

from sqlalchemy import or_


def apply_item_search(query, model, search_value: str | None):
    text = str(search_value or "").strip()
    if not text:
        return query

    pattern = f"%{text}%"
    # Mantem compatibilidade com queries de itens em checklist/atividades/NC.
    clauses = []
    if hasattr(model, "item_nome"):
        clauses.append(model.item_nome.ilike(pattern))
    if hasattr(model, "tipo_equipamento"):
        clauses.append(model.tipo_equipamento.ilike(pattern))
    if hasattr(model, "observacao"):
        clauses.append(model.observacao.ilike(pattern))

    if not clauses:
        return query
    return query.filter(or_(*clauses))

from sqlalchemy import or_

def apply_item_search(query, model, search_term: str | None):
    """
    Centraliza a lógica de busca por item (Ponto 1 do escopo de domínio).
    Garante consistência na filtragem de NCs, Atividades e Relatórios.
    """
    if not search_term or not search_term.strip():
        return query
    pattern = f"%{search_term.strip()}%"
    return query.filter(model.item_nome.ilike(pattern))
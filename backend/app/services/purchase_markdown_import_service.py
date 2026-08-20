"""Importa a base mestre JSONL de Serviços, Materiais e Compras.

O Markdown é tratado como fonte de carga, não como contrato de API. A carga
usa as tabelas canônicas já existentes e registra cada linha na trilha de
importação para permitir reexecução segura.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.extensions import db
from app.models import (
    InvoicePurchaseOrderLink,
    Material,
    PurchaseImportBatch,
    PurchaseImportSourceRow,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseProcessEvent,
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseServiceCatalog,
    Supplier,
)
from app.services.purchase_import_service import _legacy_request_status, _module_from_text, _normalize_key, _supplier_code
from app.utils.timezone import now_manaus_naive


def _text(value) -> str | None:
    if value is None:
        return None
    value = str(value).replace("\xa0", " ").strip()
    return value or None


def _date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    value = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            pass
    return None


def _decimal(value) -> Decimal:
    if value in (None, "", "-"):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    try:
        return Decimal(str(value).strip().replace(".", "").replace(",", "."))
    except InvalidOperation:
        return Decimal("0")


def _json_sections(path: Path) -> tuple[list[dict], list[dict], list[dict]]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    sections: dict[str, list[dict]] = {}
    current = None
    in_fence = False
    for line in lines:
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            in_fence = False
            continue
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if current and in_fence and line.strip():
            sections[current].append(json.loads(line))
    return (
        sections.get("4. CADASTRO DE SERVIÇOS", []),
        sections.get("5. CADASTRO DE MATERIAIS", []),
        sections.get("7. HISTÓRICO DE COMPRAS — SC / PC / NF", []),
    )


def _supplier(name: str | None, cache: dict[str, Supplier]) -> Supplier | None:
    name = _text(name)
    if not name:
        return None
    key = _normalize_key(name)
    if key in cache:
        return cache[key]
    item = Supplier.query.filter_by(name=name[:180]).first()
    if item is None:
        item = Supplier(code=_supplier_code(name), name=name[:180], legal_name=name[:220], active=True)
        db.session.add(item)
        db.session.flush()
    cache[key] = item
    return item


def _status(rows: list[dict]) -> str:
    has_pc = any(row.get("numero_pc") for row in rows)
    has_nf = any(row.get("numero_nota") for row in rows)
    requested = sum((_decimal(row.get("quantidade_sc")) for row in rows), Decimal("0"))
    received = sum((_decimal(row.get("quantidade_recebida")) for row in rows), Decimal("0"))
    if not has_pc:
        return "AGUARDANDO_PC"
    if not has_nf:
        return "AGUARDANDO_NF"
    if received <= 0:
        return "EM_TRANSITO"
    if received < requested:
        return "PARCIALMENTE_RECEBIDA"
    return "RECEBIDA"


def _import_purchase_markdown_fast(source_path: Path, *, user_id: int, checksum: str, services: list[dict], materials: list[dict], history: list[dict]) -> dict:
    """Carga em lotes para SQLite/PostgreSQL sem autoflush por linha."""
    batch = PurchaseImportBatch(source_filename=source_path.name, source_checksum=checksum, imported_by_user_id=user_id, rows_read=len(history), status="PROCESSANDO")
    db.session.add(batch)
    db.session.flush()

    material_catalog = {_text(row.get("codigo_produto")): row for row in materials if _text(row.get("codigo_produto"))}
    service_catalog = {(_text(row.get("codigo_servico")) or "")[:80]: row for row in services if _text(row.get("codigo_servico"))}
    history_codes = {_text(row.get("codigo_produto_servico")) for row in history if _text(row.get("codigo_produto_servico"))}
    material_codes = {code for code in history_codes if not code.startswith("017.")} | set(material_catalog)
    service_codes = {code[:80] for code in history_codes if code.startswith("017.")} | set(service_catalog)

    existing_materials = {item.codigo_produto or item.referencia: item for item in Material.query.filter(Material.referencia.in_([code[:80] for code in material_codes])).all()}
    material_rows = []
    for code in sorted(material_codes):
        if code in existing_materials:
            continue
        row = material_catalog.get(code, {})
        material_rows.append({"referencia": code[:80], "descricao": (_text(row.get("descricao")) or "MATERIAL HISTÓRICO")[:255], "aplicacao_tipo": "ambos", "codigo_produto": code[:120], "marca": _text(row.get("marca")), "referencia_manual": _text(row.get("referencia_manual")), "numero_fabricante": _text(row.get("numero_fabricante")), "referencia_preferencial": _text(row.get("referencia_preferencial")), "status_referencia": _text(row.get("status_referencia")), "familia_codigo": _text(row.get("familia_codigo")), "primeira_sc": _text(row.get("primeira_sc")), "ultima_sc": _text(row.get("ultima_sc")), "quantidade_registros_historicos": int(row.get("quantidade_registros_historicos") or 0), "ultimo_pc": _text(row.get("ultimo_pc")), "data_ultimo_pc": _date(row.get("data_ultimo_pc")), "ultimo_fornecedor": _text(row.get("ultimo_fornecedor")), "ultima_nf": _text(row.get("ultima_nf")), "data_ultima_nf": _date(row.get("data_ultima_nf")), "valor_item_ultimo_registro": _decimal(row.get("valor_item_ultimo_registro"))})
    if material_rows:
        db.session.bulk_insert_mappings(Material, material_rows)
    material_map = {item.codigo_produto or item.referencia: item.id for item in Material.query.filter(Material.referencia.in_([code[:80] for code in material_codes])).all()}

    existing_services = {item.code: item.id for item in PurchaseServiceCatalog.query.filter(PurchaseServiceCatalog.code.in_(list(service_codes))).all()}
    service_rows = []
    for code in sorted(service_codes):
        if code in existing_services:
            continue
        row = service_catalog.get(code, {})
        service_rows.append({"code": code, "service_name": (_text(row.get("descricao_servico")) or code)[:255], "description": (_text(row.get("descricao_servico")) or code), "active": True, "imported": True, "referencia_fiscal_manual": _text(row.get("referencia_fiscal_manual")), "numero_fabricante_cadastrado": _text(row.get("numero_fabricante_cadastrado")), "primeira_sc": _text(row.get("primeira_sc")), "ultima_sc": _text(row.get("ultima_sc")), "quantidade_registros_historicos": int(row.get("quantidade_registros_historicos") or 0), "ultimo_fornecedor": _text(row.get("ultimo_fornecedor")), "ultimo_pc": _text(row.get("ultimo_pc")), "ultima_observacao_sc": _text(row.get("ultima_observacao_sc"))})
    if service_rows:
        db.session.bulk_insert_mappings(PurchaseServiceCatalog, service_rows)
    service_map = {item.code: item.id for item in PurchaseServiceCatalog.query.filter(PurchaseServiceCatalog.code.in_(list(service_codes))).all()}

    supplier_names = {_text(row.get("fornecedor")) for row in history if _text(row.get("fornecedor"))}
    supplier_map = {item.name: item for item in Supplier.query.filter(Supplier.name.in_(list(supplier_names))).all()}
    supplier_rows = [{"code": _supplier_code(name), "name": name[:180], "legal_name": name[:220], "active": True} for name in sorted(supplier_names) if name not in supplier_map]
    if supplier_rows:
        db.session.bulk_insert_mappings(Supplier, supplier_rows)
    supplier_map = {item.name: item for item in Supplier.query.filter(Supplier.name.in_(list(supplier_names))).all()}

    grouped: dict[tuple[str | None, str | None, str], list[dict]] = defaultdict(list)
    for row in history:
        key = (_text(row.get("cod_coligada")), _text(row.get("cod_filial")), _text(row.get("numero_sc")))
        if key[2] and _text(row.get("codigo_produto_servico")):
            grouped[key].append(row)
    request_rows = []
    for (company, branch, sc), rows in grouped.items():
        requested = max(1, int(sum((_decimal(row.get("quantidade_sc")) for row in rows), Decimal("0"))))
        received = max(0, int(sum((_decimal(row.get("quantidade_recebida")) for row in rows), Decimal("0"))))
        request_rows.append({"code": f"SC-{company or '0'}-{branch or '0'}-{sc}"[:40], "requested_quantity": requested, "received_quantity": min(received, requested), "status": _legacy_request_status(_status(rows)), "priority": "MEDIA", "created_by_user_id": user_id, "company_code": company, "branch_code": branch, "sc_number": sc, "sc_date": _date(rows[0].get("data_emissao_sc")), "requester_raw": _text(rows[0].get("solicitante")), "request_type": "MISTO" if {(_text(row.get("tipo_item")) or "MATERIAL") for row in rows} == {"MATERIAL", "SERVICO"} else ("SERVICO" if all(_text(row.get("tipo_item")) == "SERVICO" for row in rows) else "MATERIAL"), "module": _module_from_text(rows[0].get("observacao_sc"), rows[0].get("descricao_produto_servico")), "justification": _text(rows[0].get("observacao_sc")), "imported": True, "import_batch_id": batch.id})
    db.session.bulk_insert_mappings(PurchaseRequest, request_rows)
    request_map = {(item.company_code, item.branch_code, item.sc_number): item for item in PurchaseRequest.query.filter_by(import_batch_id=batch.id).all()}

    item_rows = []
    item_source = []
    for key, rows in grouped.items():
        request = request_map[key]
        for line, row in enumerate(rows, 1):
            code = _text(row.get("codigo_produto_servico")) or ""
            item_type = "SERVICO" if _text(row.get("tipo_item")) == "SERVICO" else "MATERIAL"
            qty = _decimal(row.get("quantidade_sc")) or Decimal("1")
            received = min(_decimal(row.get("quantidade_recebida")), qty)
            item_rows.append({"purchase_request_id": request.id, "line_number": line, "item_type": item_type, "material_id": material_map.get(code) if item_type == "MATERIAL" else None, "service_catalog_id": service_map.get(code[:80]) if item_type == "SERVICO" else None, "product_code_raw": code, "description_raw": _text(row.get("descricao_produto_servico")) or "ITEM HISTÓRICO", "brand_raw": _text(row.get("marca")), "manual_reference_raw": _text(row.get("referencia_manual")), "manufacturer_part_number_raw": _text(row.get("numero_fabricante")), "quantity_requested": qty, "quantity_received": received, "status": "RECEBIDO" if received >= qty else ("AGUARDANDO_PC" if not _text(row.get("numero_pc")) else ("AGUARDANDO_NF" if not _text(row.get("numero_nota")) else "RECEBIMENTO_PARCIAL")), "imported": True})
            item_source.append((key, line, row))
    db.session.bulk_insert_mappings(PurchaseRequestItem, item_rows)
    item_map = {(item.purchase_request_id, item.line_number): item for item in PurchaseRequestItem.query.filter(PurchaseRequestItem.purchase_request_id.in_([request.id for request in request_map.values()])).all()}

    order_keys = {(pc, key[0], key[1]) for key, _, row in item_source if (pc := _text(row.get("numero_pc")))}
    order_rows = []
    for pc, company, branch in sorted(order_keys):
        first = next(row for key, _, row in item_source if _text(row.get("numero_pc")) == pc and key[0] == company and key[1] == branch)
        order_rows.append({"pc_number": pc, "pc_date": _date(first.get("data_emissao_pc")), "supplier_id": supplier_map.get(_text(first.get("fornecedor"))).id if supplier_map.get(_text(first.get("fornecedor"))) else None, "supplier_raw": _text(first.get("fornecedor")), "total_value": Decimal("0"), "status": "RECEBIDO" if _text(first.get("numero_nota")) else "EMITIDO", "company_code": company, "branch_code": branch, "imported": True, "import_batch_id": batch.id})
    if order_rows:
        db.session.bulk_insert_mappings(PurchaseOrder, order_rows)
    order_map = {(item.pc_number, item.company_code, item.branch_code): item for item in PurchaseOrder.query.filter_by(import_batch_id=batch.id).all()}

    order_item_rows = []
    invoice_keys = set()
    for key, line, row in item_source:
        item = item_map[(request_map[key].id, line)]
        pc = _text(row.get("numero_pc"))
        if pc:
            order = order_map[(pc, key[0], key[1])]
            order.total_value = (order.total_value or Decimal("0")) + _decimal(row.get("valor_item"))
            order_item_rows.append({"purchase_order_id": order.id, "purchase_request_item_id": item.id, "quantity_ordered": _decimal(row.get("quantidade_pc")) or _decimal(row.get("quantidade_sc")) or Decimal("1"), "total_price": _decimal(row.get("valor_item")), "status": "RECEBIDO" if _text(row.get("numero_nota")) else "EMITIDO"})
        nf = _text(row.get("numero_nota"))
        if nf:
            invoice_keys.add((nf, _text(row.get("serie")), supplier_map.get(_text(row.get("fornecedor"))).id if supplier_map.get(_text(row.get("fornecedor"))) else None))
    if order_item_rows:
        db.session.bulk_insert_mappings(PurchaseOrderItem, order_item_rows)
    order_item_map = {(item.purchase_order_id, item.purchase_request_item_id): item for item in PurchaseOrderItem.query.filter(PurchaseOrderItem.purchase_order_id.in_([item.id for item in order_map.values()])).all()}

    invoice_rows = []
    for nf, series, supplier_id in sorted(invoice_keys):
        row = next(row for _, _, row in item_source if _text(row.get("numero_nota")) == nf and _text(row.get("serie")) == series and (supplier_map.get(_text(row.get("fornecedor"))).id if supplier_map.get(_text(row.get("fornecedor"))) else None) == supplier_id)
        invoice_rows.append({"invoice_number": nf, "series": series, "supplier_id": supplier_id, "supplier_raw": _text(row.get("fornecedor")), "invoice_date": _date(row.get("data_emissao_nf")), "invoice_value": _decimal(row.get("valor_item")), "status": "RECEBIDA", "imported": True, "import_batch_id": batch.id})
    if invoice_rows:
        db.session.bulk_insert_mappings(PurchaseInvoice, invoice_rows)
    invoice_map = {(item.invoice_number, item.series, item.supplier_id): item for item in PurchaseInvoice.query.filter_by(import_batch_id=batch.id).all()}

    link_values: dict[tuple[int, int], Decimal] = {}
    invoice_item_rows, source_rows = [], []
    for index, (key, line, row) in enumerate(item_source, 1):
        item = item_map[(request_map[key].id, line)]
        pc = _text(row.get("numero_pc"))
        order = order_map.get((pc, key[0], key[1])) if pc else None
        order_item = order_item_map.get((order.id, item.id)) if order else None
        nf = _text(row.get("numero_nota"))
        supplier = supplier_map.get(_text(row.get("fornecedor")))
        invoice = invoice_map.get((nf, _text(row.get("serie")), supplier.id if supplier else None)) if nf else None
        if invoice and order:
            link_key = (invoice.id, order.id)
            link_values[link_key] = link_values.get(link_key, Decimal("0")) + _decimal(row.get("valor_item"))
        if invoice and order_item:
            invoice_item_rows.append({"invoice_id": invoice.id, "purchase_order_item_id": order_item.id, "quantity_invoiced": _decimal(row.get("quantidade_pc")) or item.quantity_requested, "quantity_received": min(_decimal(row.get("quantidade_recebida")), item.quantity_requested), "accepted": True})
        payload = json.loads(json.dumps(row, ensure_ascii=False, default=str))
        source_rows.append({"batch_id": batch.id, "source_row_number": index, "source_hash": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(), "source_payload": payload, "normalized_entity_ids": {"purchase_request_id": request.id, "purchase_request_item_id": item.id, "purchase_order_id": order.id if order else None, "purchase_invoice_id": invoice.id if invoice else None}})
    link_rows = [{"invoice_id": invoice_id, "purchase_order_id": order_id, "linked_value": value} for (invoice_id, order_id), value in link_values.items()]
    if link_rows:
        db.session.bulk_insert_mappings(InvoicePurchaseOrderLink, link_rows)
    if invoice_item_rows:
        db.session.bulk_insert_mappings(PurchaseInvoiceItem, invoice_item_rows)
    db.session.bulk_insert_mappings(PurchaseImportSourceRow, source_rows)
    db.session.bulk_insert_mappings(PurchaseProcessEvent, [{"entity_type": "PURCHASE_REQUEST", "entity_id": request.id, "event_type": "IMPORTADO", "new_status": request.status, "actor_id": user_id, "comment": "Importação da base mestre de Serviços, Materiais e Compras."} for request in request_map.values()])
    db.session.flush()
    batch.rows_created = len(material_rows) + len(service_rows) + len(supplier_rows) + len(request_rows) + len(item_rows) + len(order_rows) + len(order_item_rows) + len(invoice_rows) + len(link_rows)
    batch.status = "CONCLUIDO"
    batch.finished_at = now_manaus_naive()
    db.session.commit()
    return {"status": "CONCLUIDO", "batch": batch.to_dict(), "created": {"materials": len(material_rows), "services": len(service_rows), "suppliers": len(supplier_rows), "requests": len(request_rows), "items": len(item_rows), "orders": len(order_rows), "order_items": len(order_item_rows), "invoices": len(invoice_rows), "invoice_links": len(link_rows)}, "reconciliation": {"source_rows": len(history), "purchase_requests": len(grouped), "catalog_materials": len(materials), "catalog_services": len(services)}}


def import_purchase_markdown(path: str | Path, *, user_id: int) -> dict:
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Arquivo base não encontrado: {source_path}")
    checksum = hashlib.sha256(source_path.read_bytes()).hexdigest()
    existing = PurchaseImportBatch.query.filter_by(source_checksum=checksum).first()
    if existing:
        return {"status": "JA_IMPORTADO", "batch": existing.to_dict()}

    services, materials, history = _json_sections(source_path)
    return _import_purchase_markdown_fast(source_path, user_id=user_id, checksum=checksum, services=services, materials=materials, history=history)

    # Mantido abaixo apenas como referência da implementação ORM original.
    batch = PurchaseImportBatch(
        source_filename=source_path.name,
        source_checksum=checksum,
        imported_by_user_id=user_id,
        rows_read=len(history),
        status="PROCESSANDO",
    )
    db.session.add(batch)
    db.session.flush()
    # A carga faz muitas consultas de reconciliação. Evitamos autoflush a cada
    # consulta e mantemos flush explícito somente quando um ID é necessário.
    db.session.autoflush = False

    material_cache: dict[str, Material] = {}
    service_cache: dict[str, PurchaseServiceCatalog] = {}
    supplier_cache: dict[str, Supplier] = {}
    created = {"materials": 0, "services": 0, "suppliers": 0, "requests": 0, "items": 0, "orders": 0, "order_items": 0, "invoices": 0, "invoice_links": 0}

    for row in materials:
        code = _text(row.get("codigo_produto"))
        if not code:
            continue
        material = Material.query.filter_by(codigo_produto=code).first() or Material.query.filter_by(referencia=code[:80]).first()
        if material is None:
            material = Material(referencia=code[:80], descricao=(_text(row.get("descricao")) or "MATERIAL HISTÓRICO")[:255], aplicacao_tipo="ambos")
            db.session.add(material)
            db.session.flush()
            created["materials"] += 1
        for field in ("codigo_produto", "marca", "referencia_manual", "numero_fabricante", "referencia_preferencial", "status_referencia", "familia_codigo", "primeira_sc", "ultima_sc", "ultimo_pc", "ultimo_fornecedor", "ultima_nf"):
            setattr(material, field, _text(row.get(field)))
        material.descricao = (_text(row.get("descricao")) or material.descricao)[:255]
        material.quantidade_registros_historicos = int(row.get("quantidade_registros_historicos") or 0)
        material.data_ultimo_pc = _date(row.get("data_ultimo_pc"))
        material.data_ultima_nf = _date(row.get("data_ultima_nf"))
        material.valor_item_ultimo_registro = _decimal(row.get("valor_item_ultimo_registro"))
        material_cache[code] = material

    for row in services:
        code = (_text(row.get("codigo_servico")) or "")[:80]
        if not code:
            continue
        service = PurchaseServiceCatalog.query.filter_by(code=code).first()
        if service is None:
            service = PurchaseServiceCatalog(code=code, service_name=(_text(row.get("descricao_servico")) or code)[:255], active=True, imported=True)
            db.session.add(service)
            db.session.flush()
            created["services"] += 1
        service.service_name = (_text(row.get("descricao_servico")) or service.service_name)[:255]
        service.description = service.service_name
        service.imported = True
        for field in ("referencia_fiscal_manual", "numero_fabricante_cadastrado", "primeira_sc", "ultima_sc", "ultimo_fornecedor", "ultimo_pc", "ultima_observacao_sc"):
            setattr(service, field, _text(row.get(field)))
        service.quantidade_registros_historicos = int(row.get("quantidade_registros_historicos") or 0)
        service_cache[code] = service

    grouped: dict[tuple[str | None, str | None, str], list[dict]] = defaultdict(list)
    for row in history:
        sc = _text(row.get("numero_sc"))
        code = _text(row.get("codigo_produto_servico"))
        if sc and code:
            grouped[(_text(row.get("cod_coligada")), _text(row.get("cod_filial")), sc)].append(row)

    order_cache: dict[tuple[str, str | None, str | None], PurchaseOrder] = {}
    invoice_cache: dict[tuple[str, str | None, int | None], PurchaseInvoice] = {}
    for (company, branch, sc), rows in grouped.items():
        requested = max(1, int(sum((_decimal(row.get("quantidade_sc")) for row in rows), Decimal("0"))))
        received = max(0, int(sum((_decimal(row.get("quantidade_recebida")) for row in rows), Decimal("0"))))
        request = PurchaseRequest.query.filter_by(company_code=company, branch_code=branch, sc_number=sc).first()
        if request is None:
            request = PurchaseRequest(code=f"SC-{company or '0'}-{branch or '0'}-{sc}"[:40], requested_quantity=requested, received_quantity=min(received, requested), status=_legacy_request_status(_status(rows)), priority="MEDIA", created_by_user_id=user_id, company_code=company, branch_code=branch, sc_number=sc, sc_date=_date(rows[0].get("data_emissao_sc")), requester_raw=_text(rows[0].get("solicitante")), module=_module_from_text(rows[0].get("observacao_sc"), rows[0].get("descricao_produto_servico")), justification=_text(rows[0].get("observacao_sc")), imported=True, import_batch_id=batch.id)
            db.session.add(request)
            db.session.flush()
            created["requests"] += 1
        else:
            request.status = _legacy_request_status(_status(rows))
            request.imported = True
            request.import_batch_id = batch.id

        for line, row in enumerate(rows, 1):
            code = _text(row.get("codigo_produto_servico")) or ""
            item_type = "SERVICO" if _text(row.get("tipo_item")) == "SERVICO" else "MATERIAL"
            material = service = None
            if item_type == "MATERIAL":
                material = material_cache.get(code) or Material.query.filter_by(codigo_produto=code).first() or Material.query.filter_by(referencia=code[:80]).first()
                if material is None:
                    material = Material(referencia=code[:80], codigo_produto=code, descricao=(_text(row.get("descricao_produto_servico")) or "MATERIAL HISTÓRICO")[:255], aplicacao_tipo="ambos")
                    db.session.add(material)
                    db.session.flush()
                    created["materials"] += 1
                material_cache[code] = material
            else:
                service = service_cache.get(code) or PurchaseServiceCatalog.query.filter_by(code=code[:80]).first()
                if service is None:
                    service = PurchaseServiceCatalog(code=code[:80], service_name=(_text(row.get("descricao_produto_servico")) or code)[:255], description=_text(row.get("descricao_produto_servico")), active=True, imported=True)
                    db.session.add(service)
                    db.session.flush()
                    created["services"] += 1
                service_cache[code] = service

            item = PurchaseRequestItem.query.filter_by(purchase_request_id=request.id, line_number=line).first()
            qty = _decimal(row.get("quantidade_sc")) or Decimal("1")
            received_qty = min(_decimal(row.get("quantidade_recebida")), qty)
            if item is None:
                item = PurchaseRequestItem(purchase_request_id=request.id, line_number=line, description_raw=(_text(row.get("descricao_produto_servico")) or "ITEM HISTÓRICO"), quantity_requested=qty, imported=True)
                db.session.add(item)
                created["items"] += 1
            item.item_type = item_type
            item.material_id = material.id if material else None
            item.service_catalog_id = service.id if service else None
            item.product_code_raw = code
            item.description_raw = (_text(row.get("descricao_produto_servico")) or "ITEM HISTÓRICO")
            item.brand_raw = _text(row.get("marca"))
            item.manual_reference_raw = _text(row.get("referencia_manual"))
            item.manufacturer_part_number_raw = _text(row.get("numero_fabricante"))
            item.quantity_requested = qty
            item.quantity_received = received_qty
            item.status = "RECEBIDO" if received_qty >= qty else ("AGUARDANDO_PC" if not _text(row.get("numero_pc")) else ("AGUARDANDO_NF" if not _text(row.get("numero_nota")) else "RECEBIMENTO_PARCIAL"))
            db.session.flush()

            supplier = _supplier(row.get("fornecedor"), supplier_cache)
            order = order_item = None
            pc = _text(row.get("numero_pc"))
            if pc:
                key = (pc, company, branch)
                order = order_cache.get(key) or PurchaseOrder.query.filter_by(pc_number=pc, company_code=company, branch_code=branch).first()
                if order is None:
                    order = PurchaseOrder(pc_number=pc, pc_date=_date(row.get("data_emissao_pc")), supplier_id=supplier.id if supplier else None, supplier_raw=_text(row.get("fornecedor")), total_value=Decimal("0"), status="RECEBIDO" if _text(row.get("numero_nota")) else "EMITIDO", imported=True, import_batch_id=batch.id)
                    db.session.add(order)
                    db.session.flush()
                    created["orders"] += 1
                order.supplier_id = supplier.id if supplier else order.supplier_id
                order.supplier_raw = _text(row.get("fornecedor")) or order.supplier_raw
                order.total_value = (order.total_value or Decimal("0")) + _decimal(row.get("valor_item"))
                order_cache[key] = order
                order_item = PurchaseOrderItem.query.filter_by(purchase_order_id=order.id, purchase_request_item_id=item.id).first()
                if order_item is None:
                    order_item = PurchaseOrderItem(purchase_order_id=order.id, purchase_request_item_id=item.id, quantity_ordered=_decimal(row.get("quantidade_pc")) or qty, total_price=_decimal(row.get("valor_item")), status="RECEBIDO" if _text(row.get("numero_nota")) else "EMITIDO")
                    db.session.add(order_item)
                    db.session.flush()
                    created["order_items"] += 1

            nf = _text(row.get("numero_nota"))
            invoice = None
            if nf:
                key = (nf, _text(row.get("serie")), supplier.id if supplier else None)
                invoice = invoice_cache.get(key) or PurchaseInvoice.query.filter_by(invoice_number=nf, series=key[1], supplier_id=key[2]).first()
                if invoice is None:
                    invoice = PurchaseInvoice(invoice_number=nf, series=key[1], supplier_id=key[2], supplier_raw=_text(row.get("fornecedor")), invoice_date=_date(row.get("data_emissao_nf")), invoice_value=_decimal(row.get("valor_item")), status="RECEBIDA", imported=True, import_batch_id=batch.id)
                    db.session.add(invoice)
                    db.session.flush()
                    created["invoices"] += 1
                else:
                    invoice.invoice_value = (invoice.invoice_value or Decimal("0")) + _decimal(row.get("valor_item"))
                invoice_cache[key] = invoice
                if order is not None:
                    if not InvoicePurchaseOrderLink.query.filter_by(invoice_id=invoice.id, purchase_order_id=order.id).first():
                        db.session.add(InvoicePurchaseOrderLink(invoice_id=invoice.id, purchase_order_id=order.id, linked_value=_decimal(row.get("valor_item"))))
                        created["invoice_links"] += 1
                    if order_item is not None and not PurchaseInvoiceItem.query.filter_by(invoice_id=invoice.id, purchase_order_item_id=order_item.id).first():
                        db.session.add(PurchaseInvoiceItem(invoice_id=invoice.id, purchase_order_item_id=order_item.id, quantity_invoiced=_decimal(row.get("quantidade_pc")) or qty, quantity_received=received_qty, accepted=True))

            payload = json.loads(json.dumps(row, ensure_ascii=False, default=str))
            source_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            db.session.add(PurchaseImportSourceRow(batch_id=batch.id, source_row_number=int(row.get("id_historico") or line), source_hash=source_hash, source_payload=payload, normalized_entity_ids={"purchase_request_id": request.id, "purchase_request_item_id": item.id, "purchase_order_id": order.id if order else None, "purchase_invoice_id": invoice.id if invoice else None}))

        request.request_type = "MISTO" if any(item.item_type == "MATERIAL" for item in request.items) and any(item.item_type == "SERVICO" for item in request.items) else ("MATERIAL" if any(item.item_type == "MATERIAL" for item in request.items) else "SERVICO")
        request.requested_quantity = requested
        request.received_quantity = min(received, requested)
        request.material_id = next((item.material_id for item in request.items if item.material_id), None)
        db.session.add(PurchaseProcessEvent(entity_type="PURCHASE_REQUEST", entity_id=request.id, event_type="IMPORTADO", new_status=request.status, actor_id=user_id, comment="Importação da base mestre de Serviços, Materiais e Compras."))

    batch.rows_created = sum(created.values())
    batch.status = "CONCLUIDO"
    batch.finished_at = now_manaus_naive()
    db.session.commit()
    db.session.autoflush = True
    return {"status": "CONCLUIDO", "batch": batch.to_dict(), "created": created, "reconciliation": {"source_rows": len(history), "purchase_requests": len(grouped), "catalog_materials": len(materials), "catalog_services": len(services)}}

from __future__ import annotations

from datetime import datetime
import re

from app.extensions import db

_ORIGIN_PATTERN = re.compile(r"\[ORIGEM:(?P<type>[A-Z_]+)#(?P<id>\d+)\]")


def _extract_origin(observation: str | None) -> dict | None:
    if not observation:
        return None
    match = _ORIGIN_PATTERN.search(observation)
    if not match:
        return None

    raw_type = (match.group("type") or "").strip().upper()
    raw_id = match.group("id")
    try:
        source_id = int(raw_id)
    except (TypeError, ValueError):
        return None

    if raw_type in {"NC", "NAO_CONFORMIDADE"}:
        source_type = "nao_conformidade"
        description = f"Não conformidade #{source_id}"
    else:
        source_type = raw_type.lower()
        description = f"Origem {raw_type} #{source_id}"
    return {"tipo": source_type, "id": source_id, "descricao": description}


class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(160), nullable=False, index=True)
    item_nome = db.Column(db.String(160), nullable=False, index=True)
    tipo_equipamento = db.Column(db.String(20), nullable=False, index=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=True, index=True)
    quantidade_por_equipamento = db.Column(db.Integer, nullable=False, default=1)
    codigo_peca = db.Column(db.String(80), nullable=True)
    descricao_peca = db.Column(db.String(255), nullable=True)
    fornecedor_peca = db.Column(db.String(160), nullable=True)
    lote_peca = db.Column(db.String(120), nullable=True)
    observacao = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="ABERTA", index=True)
    source_type = db.Column(db.String(40), nullable=True, index=True)
    source_key = db.Column(db.String(180), nullable=True, index=True)
    source_modulo = db.Column(db.String(20), nullable=True, index=True)
    auto_link_nc = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    assigned_mechanic_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    finalized_at = db.Column(db.DateTime, nullable=True)

    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    assigned_mechanic = db.relationship("User", foreign_keys=[assigned_mechanic_user_id], lazy="joined")
    material = db.relationship("Material", lazy="joined")
    items = db.relationship(
        "ActivityItem",
        back_populates="activity",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    non_conformity_links = db.relationship(
        "ActivityNonConformityLink",
        back_populates="activity",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('ABERTA', 'FINALIZADA')",
            name="ck_activity_status",
        ),
        db.CheckConstraint(
            "quantidade_por_equipamento > 0",
            name="ck_activity_quantidade_por_equipamento_positive",
        ),
    )

    def summary(self) -> dict:
        total = len(self.items)
        installed = sum(1 for item in self.items if item.status_execucao == "INSTALADO")
        not_installed = sum(1 for item in self.items if item.status_execucao == "NAO_INSTALADO")
        pending = sum(1 for item in self.items if item.status_execucao == "PENDENTE")
        return {
            "total": total,
            "instalados": installed,
            "nao_instalados": not_installed,
            "pendentes": pending,
        }

    def to_dict(self, include_items: bool = False) -> dict:
        origin = _extract_origin(self.observacao)
        if not origin and (self.source_type or "").upper() == "NC_ITEM":
            origin = {
                "tipo": "relatorio_nc_item",
                "id": None,
                "descricao": f"Relatório NC: {self.source_key or self.item_nome}",
            }
        data = {
            "id": self.id,
            "titulo": self.titulo,
            "item_nome": self.item_nome,
            "tipo_equipamento": self.tipo_equipamento,
            "source_type": self.source_type,
            "source_key": self.source_key,
            "source_modulo": self.source_modulo,
            "auto_link_nc": bool(self.auto_link_nc),
            "material_id": self.material_id,
            "material": self.material.to_dict() if self.material else None,
            "quantidade_por_equipamento": self.quantidade_por_equipamento,
            "codigo_peca": self.codigo_peca,
            "descricao_peca": self.descricao_peca,
            "fornecedor_peca": self.fornecedor_peca,
            "lote_peca": self.lote_peca,
            "observacao": self.observacao,
            "origem": origin,
            "status": self.status,
            "assigned_mechanic_user_id": self.assigned_mechanic_user_id,
            "assigned_mechanic": self.assigned_mechanic.to_dict() if self.assigned_mechanic else None,
            "created_at": self.created_at.isoformat(),
            "finalized_at": self.finalized_at.isoformat() if self.finalized_at else None,
            "created_by": self.created_by.to_dict() if self.created_by else None,
            "resumo": self.summary(),
            "vinculos_nc": self.nc_link_summary(),
        }
        if include_items:
            data["itens"] = [item.to_dict() for item in self.items]
        return data

    def nc_link_summary(self) -> dict:
        links = self.non_conformity_links or []
        linked_total = len(links)
        linked_open = 0
        linked_resolved = 0
        for link in links:
            checklist_item = link.checklist_item
            if checklist_item and checklist_item.resolvido:
                linked_resolved += 1
            else:
                linked_open += 1
        return {
            "total": linked_total,
            "abertas": linked_open,
            "resolvidas": linked_resolved,
        }


class ActivityItem(db.Model):
    __tablename__ = "activity_items"

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=False, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    status_execucao = db.Column(db.String(20), nullable=False, default="PENDENTE", index=True)
    observacao = db.Column(db.Text, nullable=True)
    foto_antes = db.Column(db.String(255), nullable=True)
    foto_depois = db.Column(db.String(255), nullable=True)
    executado_por_nome = db.Column(db.String(120), nullable=True)
    executado_por_login = db.Column(db.String(80), nullable=True)
    instalado_em = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    activity = db.relationship("Activity", back_populates="items")
    vehicle = db.relationship("Vehicle", lazy="joined")
    non_conformity_links = db.relationship(
        "ActivityNonConformityLink",
        back_populates="activity_item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        db.CheckConstraint(
            "status_execucao IN ('PENDENTE', 'INSTALADO', 'NAO_INSTALADO')",
            name="ck_activity_item_status_execucao",
        ),
        db.UniqueConstraint("activity_id", "vehicle_id", name="uq_activity_vehicle"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "activity_id": self.activity_id,
            "status_execucao": self.status_execucao,
            "observacao": self.observacao,
            "foto_antes": self.foto_antes,
            "foto_depois": self.foto_depois,
            "executado_por_nome": self.executado_por_nome,
            "executado_por_login": self.executado_por_login,
            "instalado_em": self.instalado_em.isoformat() if self.instalado_em else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "veiculo": self.vehicle.to_dict() if self.vehicle else None,
        }


class ActivityNonConformityLink(db.Model):
    __tablename__ = "activity_non_conformity_links"

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=False, index=True)
    activity_item_id = db.Column(db.Integer, db.ForeignKey("activity_items.id"), nullable=False, index=True)
    checklist_item_id = db.Column(db.Integer, db.ForeignKey("checklist_items.id"), nullable=False, unique=True, index=True)
    linked_by_mode = db.Column(db.String(20), nullable=False, default="MANUAL", index=True)
    linked_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    activity = db.relationship("Activity", back_populates="non_conformity_links")
    activity_item = db.relationship("ActivityItem", back_populates="non_conformity_links")
    checklist_item = db.relationship("ChecklistItem", lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "linked_by_mode IN ('MANUAL', 'AUTO')",
            name="ck_activity_nc_link_mode",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "activity_id": self.activity_id,
            "activity_item_id": self.activity_item_id,
            "checklist_item_id": self.checklist_item_id,
            "linked_by_mode": self.linked_by_mode,
            "linked_at": self.linked_at.isoformat() if self.linked_at else None,
            "checklist_item": self.checklist_item.to_dict() if self.checklist_item else None,
        }

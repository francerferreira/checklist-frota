from __future__ import annotations

from datetime import datetime

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class Material(db.Model):
    __tablename__ = "materials"

    id = db.Column(db.Integer, primary_key=True)
    referencia = db.Column(db.String(80), nullable=False, unique=True, index=True)
    descricao = db.Column(db.String(255), nullable=False, index=True)
    aplicacao_tipo = db.Column(db.String(20), nullable=False, default="ambos", index=True)
    foto_path = db.Column(db.String(255), nullable=True)
    quantidade_estoque = db.Column(db.Integer, nullable=False, default=0)
    estoque_minimo = db.Column(db.Integer, nullable=False, default=0)
    ponto_reposicao = db.Column(db.Integer, nullable=False, default=0)
    classe_abc = db.Column(db.String(1), nullable=False, default="C", index=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    codigo_produto = db.Column(db.String(120), nullable=True, index=True)
    marca = db.Column(db.String(180), nullable=True)
    referencia_manual = db.Column(db.String(180), nullable=True)
    numero_fabricante = db.Column(db.String(180), nullable=True)
    referencia_preferencial = db.Column(db.String(180), nullable=True, index=True)
    status_referencia = db.Column(db.String(30), nullable=True, index=True)
    familia_codigo = db.Column(db.String(80), nullable=True, index=True)
    primeira_sc = db.Column(db.String(60), nullable=True)
    ultima_sc = db.Column(db.String(60), nullable=True)
    quantidade_registros_historicos = db.Column(db.Integer, nullable=True)
    ultimo_pc = db.Column(db.String(60), nullable=True)
    data_ultimo_pc = db.Column(db.Date, nullable=True)
    ultimo_fornecedor = db.Column(db.String(220), nullable=True)
    ultima_nf = db.Column(db.String(80), nullable=True)
    data_ultima_nf = db.Column(db.Date, nullable=True)
    valor_item_ultimo_registro = db.Column(db.Numeric(18, 2), nullable=True)

    movements = db.relationship(
        "MaterialMovement",
        back_populates="material",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    family_applications = db.relationship("MaterialFamilyApplication", back_populates="material", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        db.CheckConstraint(
            "aplicacao_tipo IN ('cavalo', 'carreta', 'ambos')",
            name="ck_material_aplicacao_tipo",
        ),
        db.CheckConstraint(
            "quantidade_estoque >= 0",
            name="ck_material_quantidade_estoque_non_negative",
        ),
        db.CheckConstraint(
            "estoque_minimo >= 0",
            name="ck_material_estoque_minimo_non_negative",
        ),
        db.CheckConstraint(
            "ponto_reposicao >= 0",
            name="ck_material_ponto_reposicao_non_negative",
        ),
        db.CheckConstraint(
            "classe_abc IN ('A', 'B', 'C')",
            name="ck_material_classe_abc",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "referencia": self.referencia,
            "descricao": self.descricao,
            "aplicacao_tipo": self.aplicacao_tipo,
            "foto_path": self.foto_path,
            "quantidade_estoque": self.quantidade_estoque,
            "estoque_minimo": self.estoque_minimo,
            "ponto_reposicao": self.ponto_reposicao,
            "classe_abc": self.classe_abc,
            "ativo": self.ativo,
            "codigo_produto": self.codigo_produto,
            "marca": self.marca,
            "referencia_manual": self.referencia_manual,
            "numero_fabricante": self.numero_fabricante,
            "referencia_preferencial": self.referencia_preferencial,
            "status_referencia": self.status_referencia,
            "familia_codigo": self.familia_codigo,
            "primeira_sc": self.primeira_sc,
            "ultima_sc": self.ultima_sc,
            "quantidade_registros_historicos": self.quantidade_registros_historicos,
            "ultimo_pc": self.ultimo_pc,
            "data_ultimo_pc": self.data_ultimo_pc.isoformat() if self.data_ultimo_pc else None,
            "ultimo_fornecedor": self.ultimo_fornecedor,
            "ultima_nf": self.ultima_nf,
            "data_ultima_nf": self.data_ultima_nf.isoformat() if self.data_ultima_nf else None,
            "valor_item_ultimo_registro": float(self.valor_item_ultimo_registro) if self.valor_item_ultimo_registro is not None else None,
            "baixo_estoque": self.quantidade_estoque <= self.estoque_minimo,
            "repor": self.quantidade_estoque <= self.ponto_reposicao,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "family_applications": [row.to_dict() for row in self.family_applications if row.active],
        }


class MaterialMovement(db.Model):
    __tablename__ = "material_movements"

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=True, index=True)
    checklist_item_id = db.Column(db.Integer, db.ForeignKey("checklist_items.id"), nullable=True, index=True)
    warehouse_stock_id = db.Column(db.Integer, db.ForeignKey("warehouse_stocks.id"), nullable=True, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True, index=True)
    application = db.Column(db.String(160), nullable=True)
    tipo_movimento = db.Column(db.String(30), nullable=False, index=True)
    quantidade = db.Column(db.Integer, nullable=False)
    saldo_anterior = db.Column(db.Integer, nullable=False)
    saldo_posterior = db.Column(db.Integer, nullable=False)
    observacao = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)

    material = db.relationship("Material", back_populates="movements")
    user = db.relationship("User", lazy="joined")
    activity = db.relationship("Activity", lazy="joined")
    checklist_item = db.relationship("ChecklistItem", lazy="joined")
    warehouse_stock = db.relationship("WarehouseStock", lazy="joined")
    vehicle = db.relationship("Vehicle", lazy="joined")

    __table_args__ = (
        db.CheckConstraint(
            "tipo_movimento IN ('ENTRADA', 'SAIDA', 'AJUSTE', 'ATIVIDADE', 'NAO_CONFORMIDADE')",
            name="ck_material_movement_tipo",
        ),
        db.CheckConstraint(
            "quantidade > 0",
            name="ck_material_movement_quantidade_positive",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "material_id": self.material_id,
            "user_id": self.user_id,
            "activity_id": self.activity_id,
            "checklist_item_id": self.checklist_item_id,
            "warehouse_stock_id": self.warehouse_stock_id,
            "vehicle_id": self.vehicle_id,
            "application": self.application,
            "tipo_movimento": self.tipo_movimento,
            "quantidade": self.quantidade,
            "saldo_anterior": self.saldo_anterior,
            "saldo_posterior": self.saldo_posterior,
            "observacao": self.observacao,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "usuario": self.user.to_dict() if self.user else None,
        }

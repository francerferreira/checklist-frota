from __future__ import annotations

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class InspectionTemplate(db.Model):
    __tablename__ = "inspection_templates"

    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey("equipment_families.id"), nullable=False, index=True)
    code = db.Column(db.String(40), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False, default=1, index=True)
    status = db.Column(db.String(20), nullable=False, default="RASCUNHO", index=True)
    instructions = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    published_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    family = db.relationship("EquipmentFamily", lazy="joined")
    created_by = db.relationship("User", lazy="joined")
    items = db.relationship(
        "InspectionTemplateItem", back_populates="template", cascade="all, delete-orphan",
        lazy="joined", order_by="InspectionTemplateItem.position",
    )

    __table_args__ = (
        db.UniqueConstraint("family_id", "code", "version", name="uq_inspection_template_family_code_version"),
        db.CheckConstraint("version > 0", name="ck_inspection_template_version_positive"),
        db.CheckConstraint("status IN ('RASCUNHO', 'PUBLICADO', 'ARQUIVADO')", name="ck_inspection_template_status"),
    )

    def to_dict(self, include_items: bool = True) -> dict:
        data = {
            "id": self.id, "family_id": self.family_id,
            "family": self.family.to_dict() if self.family else None,
            "code": self.code, "name": self.name, "version": self.version,
            "status": self.status, "instructions": self.instructions,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_by_user_id": self.created_by_user_id,
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
        return data


class InspectionTemplateItem(db.Model):
    __tablename__ = "inspection_template_items"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("inspection_templates.id"), nullable=False, index=True)
    category = db.Column(db.String(80), nullable=True, index=True)
    label = db.Column(db.String(180), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1, index=True)
    required = db.Column(db.Boolean, nullable=False, default=True)
    response_type = db.Column(db.String(20), nullable=False, default="STATUS", index=True)
    unit = db.Column(db.String(30), nullable=True)
    minimum_value = db.Column(db.Numeric(12, 2), nullable=True)
    maximum_value = db.Column(db.Numeric(12, 2), nullable=True)
    evidence_on_nc = db.Column(db.Boolean, nullable=False, default=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    template = db.relationship("InspectionTemplate", back_populates="items")

    __table_args__ = (
        db.UniqueConstraint("template_id", "position", name="uq_inspection_template_item_position"),
        db.CheckConstraint("position > 0", name="ck_inspection_template_item_position_positive"),
        db.CheckConstraint("response_type IN ('STATUS', 'TEXTO', 'NUMERO')", name="ck_inspection_template_item_response_type"),
        db.CheckConstraint("minimum_value IS NULL OR maximum_value IS NULL OR maximum_value >= minimum_value", name="ck_inspection_template_item_range"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id, "template_id": self.template_id, "category": self.category,
            "label": self.label, "position": self.position, "required": self.required,
            "response_type": self.response_type, "unit": self.unit,
            "minimum_value": float(self.minimum_value) if self.minimum_value is not None else None,
            "maximum_value": float(self.maximum_value) if self.maximum_value is not None else None,
            "evidence_on_nc": self.evidence_on_nc, "active": self.active,
        }


class InspectionExecution(db.Model):
    __tablename__ = "inspection_executions"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("inspection_templates.id"), nullable=False, index=True)
    template_version = db.Column(db.Integer, nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="CONCLUIDA", index=True)
    result = db.Column(db.String(20), nullable=False, index=True)
    general_notes = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    completed_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)

    template = db.relationship("InspectionTemplate", lazy="joined")
    vehicle = db.relationship("Vehicle", lazy="joined")
    user = db.relationship("User", lazy="joined")
    items = db.relationship("InspectionExecutionItem", back_populates="execution", cascade="all, delete-orphan", lazy="joined")

    __table_args__ = (
        db.CheckConstraint("status IN ('CONCLUIDA')", name="ck_inspection_execution_status"),
        db.CheckConstraint("result IN ('CONFORME', 'NAO_CONFORME')", name="ck_inspection_execution_result"),
        db.CheckConstraint("completed_at >= started_at", name="ck_inspection_execution_period"),
    )

    def to_dict(self, include_items: bool = True) -> dict:
        data = {
            "id": self.id, "template_id": self.template_id, "template_version": self.template_version,
            "template": self.template.to_dict(include_items=False) if self.template else None,
            "vehicle": self.vehicle.to_dict() if self.vehicle else None,
            "user": self.user.to_dict() if self.user else None,
            "status": self.status, "result": self.result, "general_notes": self.general_notes,
            "started_at": self.started_at.isoformat(), "completed_at": self.completed_at.isoformat(),
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
        return data


class InspectionExecutionItem(db.Model):
    __tablename__ = "inspection_execution_items"

    id = db.Column(db.Integer, primary_key=True)
    execution_id = db.Column(db.Integer, db.ForeignKey("inspection_executions.id"), nullable=False, index=True)
    template_item_id = db.Column(db.Integer, db.ForeignKey("inspection_template_items.id"), nullable=False, index=True)
    item_label = db.Column(db.String(180), nullable=False)
    response_type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=True, index=True)
    value_text = db.Column(db.Text, nullable=True)
    value_number = db.Column(db.Numeric(12, 2), nullable=True)
    observation = db.Column(db.Text, nullable=True)
    evidence_path = db.Column(db.String(255), nullable=True)
    generated_non_conformity_id = db.Column(
        db.Integer, db.ForeignKey("mechanic_non_conformities.id"), nullable=True, index=True
    )

    execution = db.relationship("InspectionExecution", back_populates="items")
    template_item = db.relationship("InspectionTemplateItem", lazy="joined")
    generated_non_conformity = db.relationship("MechanicNonConformity", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("execution_id", "template_item_id", name="uq_inspection_execution_template_item"),
        db.CheckConstraint("status IS NULL OR status IN ('OK', 'NC', 'NA')", name="ck_inspection_execution_item_status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id, "template_item_id": self.template_item_id, "item_label": self.item_label,
            "response_type": self.response_type, "status": self.status, "value_text": self.value_text,
            "value_number": float(self.value_number) if self.value_number is not None else None,
            "observation": self.observation, "evidence_path": self.evidence_path,
            "generated_non_conformity_id": self.generated_non_conformity_id,
        }

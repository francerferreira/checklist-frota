from __future__ import annotations

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class ResolutionPackage(db.Model):
    __tablename__ = "resolution_packages"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    grouping_mode = db.Column(db.String(30), nullable=False, index=True)
    item_name = db.Column(db.String(160), nullable=True, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True, index=True)
    status = db.Column(db.String(30), nullable=False, default="ABERTO", index=True)
    priority_score = db.Column(db.Integer, nullable=False, default=0, index=True)
    recurrence_hits = db.Column(db.Integer, nullable=False, default=0)
    recurrence_window_days = db.Column(db.Integer, nullable=False, default=15)
    recurrence_weight = db.Column(db.Integer, nullable=False, default=5)
    critical_recurrence = db.Column(db.Boolean, nullable=False, default=False, index=True)
    observation = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    vehicle = db.relationship("Vehicle", lazy="joined")
    links = db.relationship(
        "ResolutionPackageLink",
        back_populates="package",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    __table_args__ = (
        db.CheckConstraint(
            "grouping_mode IN ('POR_ITEM', 'POR_EQUIPAMENTO')",
            name="ck_resolution_package_grouping_mode",
        ),
        db.CheckConstraint(
            "status IN ('ABERTO', 'EM_MANUTENCAO', 'CONCLUIDO', 'CANCELADO')",
            name="ck_resolution_package_status",
        ),
        db.CheckConstraint(
            "priority_score >= 0",
            name="ck_resolution_package_priority_score_non_negative",
        ),
        db.CheckConstraint(
            "recurrence_hits >= 0",
            name="ck_resolution_package_recurrence_hits_non_negative",
        ),
        db.CheckConstraint(
            "recurrence_window_days > 0",
            name="ck_resolution_package_recurrence_window_positive",
        ),
        db.CheckConstraint(
            "recurrence_weight >= 0",
            name="ck_resolution_package_recurrence_weight_non_negative",
        ),
    )

    def counts(self) -> dict:
        total = len(self.links)
        open_items = 0
        resolved_items = 0
        for link in self.links:
            checklist_item = link.checklist_item
            if checklist_item and checklist_item.resolvido:
                resolved_items += 1
            else:
                open_items += 1
        return {
            "total": total,
            "abertas": open_items,
            "resolvidas": resolved_items,
        }

    def reference_label(self) -> str:
        if self.grouping_mode == "POR_ITEM":
            return self.item_name or "-"
        if self.vehicle:
            return self.vehicle.frota or self.vehicle.placa or "-"
        return "-"

    def to_dict(self, include_links: bool = False) -> dict:
        data = {
            "id": self.id,
            "title": self.title,
            "grouping_mode": self.grouping_mode,
            "item_name": self.item_name,
            "vehicle_id": self.vehicle_id,
            "vehicle": self.vehicle.to_dict() if self.vehicle else None,
            "reference_label": self.reference_label(),
            "status": self.status,
            "priority_score": int(self.priority_score or 0),
            "recurrence_hits": int(self.recurrence_hits or 0),
            "recurrence_window_days": int(self.recurrence_window_days or 0),
            "recurrence_weight": int(self.recurrence_weight or 0),
            "critical_recurrence": bool(self.critical_recurrence),
            "observation": self.observation,
            "created_by_user_id": self.created_by_user_id,
            "created_by": self.created_by.to_dict() if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resumo": self.counts(),
        }
        if include_links:
            data["links"] = [link.to_dict() for link in self.links]
        return data


class ResolutionPackageLink(db.Model):
    __tablename__ = "resolution_package_links"

    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.Integer, db.ForeignKey("resolution_packages.id"), nullable=False, index=True)
    checklist_item_id = db.Column(db.Integer, db.ForeignKey("checklist_items.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)

    package = db.relationship("ResolutionPackage", back_populates="links")
    checklist_item = db.relationship("ChecklistItem", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("package_id", "checklist_item_id", name="uq_resolution_package_checklist_item"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "package_id": self.package_id,
            "checklist_item_id": self.checklist_item_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "checklist_item": self.checklist_item.to_dict() if self.checklist_item else None,
        }

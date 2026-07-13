from __future__ import annotations

from app.extensions import db
from app.utils.timezone import now_manaus_naive


class EmergencyEvent(db.Model):
    __tablename__ = "emergency_events"

    id = db.Column(db.Integer, primary_key=True)
    event_number = db.Column(db.String(40), nullable=False, unique=True, index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False, index=True)
    severity = db.Column(db.String(20), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="ABERTA", index=True)
    equipment_stopped = db.Column(db.Boolean, nullable=False, default=False, index=True)
    title = db.Column(db.String(180), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(160), nullable=True)
    evidence_path = db.Column(db.String(255), nullable=True)
    reported_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    triaged_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    assigned_mechanic_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("maintenance_work_orders.id"), nullable=True, unique=True, index=True)
    opened_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, index=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    converted_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    vehicle = db.relationship("Vehicle", lazy="joined")
    reported_by = db.relationship("User", foreign_keys=[reported_by_user_id], lazy="joined")
    triaged_by = db.relationship("User", foreign_keys=[triaged_by_user_id], lazy="joined")
    assigned_mechanic = db.relationship("User", foreign_keys=[assigned_mechanic_user_id], lazy="joined")
    work_order = db.relationship("MaintenanceWorkOrder", lazy="joined")

    __table_args__ = (
        db.CheckConstraint("severity IN ('BAIXA', 'MEDIA', 'ALTA', 'CRITICA')", name="ck_emergency_severity"),
        db.CheckConstraint(
            "status IN ('ABERTA', 'TRIAGEM', 'CONVERTIDA', 'ENCERRADA', 'CANCELADA')",
            name="ck_emergency_status",
        ),
    )

    def to_dict(self, include_execution: bool = True) -> dict:
        execution = self.work_order.execution if self.work_order else None
        return {
            "id": self.id,
            "event_number": self.event_number,
            "vehicle_id": self.vehicle_id,
            "severity": self.severity,
            "status": self.status,
            "equipment_stopped": self.equipment_stopped,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "evidence_path": self.evidence_path,
            "reported_by_user_id": self.reported_by_user_id,
            "triaged_by_user_id": self.triaged_by_user_id,
            "assigned_mechanic_user_id": self.assigned_mechanic_user_id,
            "work_order_id": self.work_order_id,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "converted_at": self.converted_at.isoformat() if self.converted_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "vehicle": self.vehicle.to_dict() if self.vehicle else None,
            "reported_by": self.reported_by.to_dict() if self.reported_by else None,
            "assigned_mechanic": self.assigned_mechanic.to_dict() if self.assigned_mechanic else None,
            "work_order": self.work_order.to_dict() if self.work_order else None,
            "execution": execution.to_dict() if include_execution and execution else None,
        }


class WorkOrderExecution(db.Model):
    __tablename__ = "work_order_executions"

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey("maintenance_work_orders.id"), nullable=False, unique=True, index=True)
    diagnosis = db.Column(db.Text, nullable=True)
    service_performed = db.Column(db.Text, nullable=True)
    failure_started_at = db.Column(db.DateTime, nullable=False, index=True)
    repair_started_at = db.Column(db.DateTime, nullable=True, index=True)
    repair_completed_at = db.Column(db.DateTime, nullable=True, index=True)
    before_evidence_path = db.Column(db.String(255), nullable=True)
    after_evidence_path = db.Column(db.String(255), nullable=True)
    test_result = db.Column(db.String(20), nullable=False, default="PENDENTE", index=True)
    test_notes = db.Column(db.Text, nullable=True)
    test_evidence_path = db.Column(db.String(255), nullable=True)
    release_status = db.Column(db.String(20), nullable=False, default="PENDENTE", index=True)
    released_at = db.Column(db.DateTime, nullable=True, index=True)
    released_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_manaus_naive, onupdate=now_manaus_naive)

    work_order = db.relationship("MaintenanceWorkOrder", back_populates="execution")
    released_by = db.relationship("User", lazy="joined")

    __table_args__ = (
        db.CheckConstraint("test_result IN ('PENDENTE', 'APROVADO', 'REPROVADO')", name="ck_work_order_execution_test"),
        db.CheckConstraint("release_status IN ('PENDENTE', 'LIBERADO', 'NAO_LIBERADO')", name="ck_work_order_execution_release"),
        db.CheckConstraint("repair_started_at IS NULL OR repair_started_at >= failure_started_at", name="ck_work_order_execution_repair_start"),
        db.CheckConstraint("repair_completed_at IS NULL OR repair_completed_at >= repair_started_at", name="ck_work_order_execution_repair_end"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "work_order_id": self.work_order_id,
            "diagnosis": self.diagnosis,
            "service_performed": self.service_performed,
            "failure_started_at": self.failure_started_at.isoformat() if self.failure_started_at else None,
            "repair_started_at": self.repair_started_at.isoformat() if self.repair_started_at else None,
            "repair_completed_at": self.repair_completed_at.isoformat() if self.repair_completed_at else None,
            "before_evidence_path": self.before_evidence_path,
            "after_evidence_path": self.after_evidence_path,
            "test_result": self.test_result,
            "test_notes": self.test_notes,
            "test_evidence_path": self.test_evidence_path,
            "release_status": self.release_status,
            "released_at": self.released_at.isoformat() if self.released_at else None,
            "released_by_user_id": self.released_by_user_id,
            "released_by": self.released_by.to_dict() if self.released_by else None,
        }

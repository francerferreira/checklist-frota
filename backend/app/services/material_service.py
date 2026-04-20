from __future__ import annotations

from flask import g

from app.extensions import db
from app.models import Material, MaterialMovement


def register_material_movement(
    material: Material,
    *,
    quantity: int,
    movement_type: str,
    delta: int,
    observation: str | None = None,
    activity_id: int | None = None,
    checklist_item_id: int | None = None,
) -> MaterialMovement:
    if quantity <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")

    previous_stock = int(material.quantidade_estoque or 0)
    next_stock = previous_stock + delta
    if next_stock < 0:
        raise ValueError(
            f"Estoque insuficiente para {material.referencia}. Saldo atual: {previous_stock}."
        )

    material.quantidade_estoque = next_stock
    movement = MaterialMovement(
        material_id=material.id,
        user_id=getattr(getattr(g, "current_user", None), "id", None),
        activity_id=activity_id,
        checklist_item_id=checklist_item_id,
        tipo_movimento=movement_type,
        quantidade=quantity,
        saldo_anterior=previous_stock,
        saldo_posterior=next_stock,
        observacao=observation,
    )
    db.session.add(movement)
    return movement


def apply_activity_stock_change(
    material: Material | None,
    *,
    previous_status: str,
    new_status: str,
    quantity_per_equipment: int,
    activity_id: int,
    vehicle_label: str,
) -> None:
    if not material:
        return

    if previous_status != "INSTALADO" and new_status == "INSTALADO":
        register_material_movement(
            material,
            quantity=quantity_per_equipment,
            movement_type="ATIVIDADE",
            delta=-quantity_per_equipment,
            observation=f"Baixa por atividade em {vehicle_label}",
            activity_id=activity_id,
        )
    elif previous_status == "INSTALADO" and new_status != "INSTALADO":
        register_material_movement(
            material,
            quantity=quantity_per_equipment,
            movement_type="AJUSTE",
            delta=quantity_per_equipment,
            observation=f"Estorno de atividade em {vehicle_label}",
            activity_id=activity_id,
        )

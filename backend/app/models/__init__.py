from app.models.activity import Activity, ActivityItem, ActivityNonConformityLink
from app.models.automation_execution import AutomationExecution
from app.models.audit_log import AuditLog
from app.models.checklist import Checklist, ChecklistItem
from app.models.checklist_catalog_item import ChecklistCatalogItem
from app.models.dashboard_tv_access import DashboardTvAccessToken
from app.models.employee import Employee, EmployeeAttendanceRecord, EmployeeDocument, EmployeeHistoryEvent, EmployeeSpecialSchedule, EmployeeTraining, EmployeeVacation
from app.models.equipment_structure import (
    EquipmentFamily,
    EquipmentLink,
    EquipmentLocationMovement,
    EquipmentProfile,
    OperationalLocation,
)
from app.models.emergency import EmergencyEvent, WorkOrderExecution
from app.models.maintenance import MaintenanceMaterial, MaintenanceSchedule, MaintenanceScheduleItem, MaintenanceWorkOrder, MaintenanceWorkOrderCost
from app.models.material import Material, MaterialMovement
from app.models.mechanic_non_conformity import MechanicNonConformity
from app.models.mobile_operation import MobileSyncOperation
from app.models.navigation import UserNavigationPreference, UserPagePermission
from app.models.notification import Notification
from app.models.operational_availability import EquipmentOperationalState, EquipmentStatusEvent, HourmeterReading
from app.models.pcm import PreventivePlan
from app.models.preventive import PreventiveExecution, PreventiveMaterial, PreventiveStage
from app.models.purchase import (
    InvoicePurchaseOrderLink,
    PurchaseImportBatch,
    PurchaseImportSourceRow,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseProcessEvent,
    PurchaseReceipt,
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseServiceCatalog,
    Supplier,
)
from app.models.resource import MaintenanceResource, MaintenanceResourceReservation
from app.models.technical_inspection import InspectionExecution, InspectionExecutionItem, InspectionTemplate, InspectionTemplateItem
from app.models.resolution_package import ResolutionPackage, ResolutionPackageLink
from app.models.revoked_token import RevokedToken
from app.models.password_reset_request import PasswordResetRequest
from app.models.supply_library import MaterialFamilyApplication, TechnicalDocument, Warehouse, WarehouseLocation, WarehouseReservation, WarehouseStock, WarehouseTransfer, WarehouseTransferItem
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.wash import WashBlockedDay, WashPlanConfig, WashQueueItem, WashRecord, WashScheduleDecision

__all__ = [
    "Activity",
    "ActivityItem",
    "ActivityNonConformityLink",
    "AutomationExecution",
    "AuditLog",
    "Checklist",
    "ChecklistCatalogItem",
    "ChecklistItem",
    "DashboardTvAccessToken",
    "Employee",
    "EmployeeAttendanceRecord",
    "EmployeeDocument",
    "EmployeeHistoryEvent",
    "EmployeeSpecialSchedule",
    "EmployeeTraining",
    "EmployeeVacation",
    "EquipmentFamily",
    "EquipmentLink",
    "EquipmentLocationMovement",
    "EquipmentProfile",
    "EquipmentOperationalState",
    "EquipmentStatusEvent",
    "EmergencyEvent",
    "HourmeterReading",
    "InspectionExecution",
    "InspectionExecutionItem",
    "InspectionTemplate",
    "InspectionTemplateItem",
    "MaintenanceMaterial",
    "MaintenanceSchedule",
    "MaintenanceScheduleItem",
    "MaintenanceWorkOrder",
    "MaintenanceWorkOrderCost",
    "WorkOrderExecution",
    "Material",
    "MaterialFamilyApplication",
    "MaterialMovement",
    "MechanicNonConformity",
    "MobileSyncOperation",
    "UserNavigationPreference",
    "UserPagePermission",
    "Notification",
    "OperationalLocation",
    "PreventivePlan",
    "PreventiveExecution",
    "PreventiveStage",
    "PreventiveMaterial",
    "PurchaseReceipt",
    "PurchaseRequest",
    "PurchaseRequestItem",
    "PurchaseServiceCatalog",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "PurchaseInvoice",
    "PurchaseInvoiceItem",
    "InvoicePurchaseOrderLink",
    "PurchaseImportBatch",
    "PurchaseImportSourceRow",
    "PurchaseProcessEvent",
    "Supplier",
    "MaintenanceResource",
    "MaintenanceResourceReservation",
    "ResolutionPackage",
    "ResolutionPackageLink",
    "RevokedToken",
    "PasswordResetRequest",
    "SystemSetting",
    "TechnicalDocument",
    "User",
    "Vehicle",
    "WashBlockedDay",
    "WashPlanConfig",
    "WashQueueItem",
    "WashRecord",
    "WashScheduleDecision",
    "Warehouse",
    "WarehouseLocation",
    "WarehouseReservation",
    "WarehouseStock",
    "WarehouseTransfer",
    "WarehouseTransferItem",
]

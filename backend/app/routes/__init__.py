from app.routes.admin import bp as admin_bp
from app.routes.activities import bp as activities_bp
from app.routes.auth import bp as auth_bp
from app.routes.availability import bp as availability_bp
from app.routes.checklist import bp as checklist_bp
from app.routes.equipment_structure import bp as equipment_structure_bp
from app.routes.emergencies import bp as emergencies_bp
from app.routes.employees import bp as employees_bp
from app.routes.employee_attendance import bp as employee_attendance_bp
from app.routes.employee_vacations import bp as employee_vacations_bp
from app.routes.employee_special_schedules import bp as employee_special_schedules_bp
from app.routes.employee_records import bp as employee_records_bp
from app.routes.hr_management import bp as hr_management_bp
from app.routes.maintenance import bp as maintenance_bp
from app.routes.maintenance_dashboard import bp as maintenance_dashboard_bp
from app.routes.maintenance_dashboard_tv import bp as maintenance_dashboard_tv_bp
from app.routes.technical_inspections import bp as technical_inspections_bp
from app.routes.intelligence import bp as intelligence_bp
from app.routes.mechanic_non_conformities import bp as mechanic_non_conformities_bp
from app.routes.materials import bp as materials_bp
from app.routes.mobile_operations import bp as mobile_operations_bp
from app.routes.non_conformities import bp as non_conformities_bp
from app.routes.navigation import bp as navigation_bp
from app.routes.pcm import bp as pcm_bp
from app.routes.purchases import bp as purchases_bp
from app.routes.resolution_packages import bp as resolution_packages_bp
from app.routes.supply_library import bp as supply_library_bp
from app.routes.reports import bp as reports_bp
from app.routes.resources import bp as resources_bp
from app.routes.upload import bp as upload_bp
from app.routes.users import bp as users_bp
from app.routes.vehicles import bp as vehicles_bp
from app.routes.washes import bp as washes_bp


def register_blueprints(app):
    for blueprint in (
        admin_bp,
        auth_bp,
        vehicles_bp,
        availability_bp,
        equipment_structure_bp,
        emergencies_bp,
        employees_bp,
        employee_attendance_bp,
        employee_vacations_bp,
        employee_special_schedules_bp,
        employee_records_bp,
        hr_management_bp,
        users_bp,
        activities_bp,
        maintenance_bp,
        maintenance_dashboard_bp,
        maintenance_dashboard_tv_bp,
        technical_inspections_bp,
        intelligence_bp,
        materials_bp,
        mobile_operations_bp,
        checklist_bp,
        mechanic_non_conformities_bp,
        non_conformities_bp,
        navigation_bp,
        pcm_bp,
        purchases_bp,
        resolution_packages_bp,
        supply_library_bp,
        upload_bp,
        reports_bp,
        resources_bp,
        washes_bp,
    ):
        app.register_blueprint(blueprint)

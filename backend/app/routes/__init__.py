from app.routes.admin import bp as admin_bp
from app.routes.activities import bp as activities_bp
from app.routes.auth import bp as auth_bp
from app.routes.checklist import bp as checklist_bp
from app.routes.maintenance import bp as maintenance_bp
from app.routes.mechanic_non_conformities import bp as mechanic_non_conformities_bp
from app.routes.materials import bp as materials_bp
from app.routes.non_conformities import bp as non_conformities_bp
from app.routes.reports import bp as reports_bp
from app.routes.upload import bp as upload_bp
from app.routes.users import bp as users_bp
from app.routes.vehicles import bp as vehicles_bp
from app.routes.washes import bp as washes_bp


def register_blueprints(app):
    for blueprint in (
        admin_bp,
        auth_bp,
        vehicles_bp,
        users_bp,
        activities_bp,
        maintenance_bp,
        materials_bp,
        checklist_bp,
        mechanic_non_conformities_bp,
        non_conformities_bp,
        upload_bp,
        reports_bp,
        washes_bp,
    ):
        app.register_blueprint(blueprint)

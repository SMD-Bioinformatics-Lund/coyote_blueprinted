from flask import Blueprint

# Blueprint configuration
dashboard_bp = Blueprint(
    "dashboard_bp", __name__, template_folder="templates", static_folder="static"
)

# print(dashboard_bp.static)
from coyote.blueprints.dashboard import views  # noqa: F401, E402

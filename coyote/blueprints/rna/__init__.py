from flask import Blueprint

# Blueprint configuration
rna_bp = Blueprint("rna_bp", __name__, template_folder="templates", static_folder="static")

from coyote.blueprints.rna import views  # noqa: F401, E402
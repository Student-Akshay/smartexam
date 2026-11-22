"""
app/__init__.py
---------------
Flask application factory.
Wires together config, extensions, and all blueprints.
"""

from flask import Flask

from app.config import Config
from app.extensions import db, login_manager


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__, template_folder="templates", static_folder="../static")
    app.config.from_object(config_class)

    # ------------------------------------------------------------------
    # Initialise extensions
    # ------------------------------------------------------------------
    db.init_app(app)
    login_manager.init_app(app)

    # ------------------------------------------------------------------
    # Register blueprints
    # ------------------------------------------------------------------
    from app.auth.routes import auth_bp
    from app.student.routes import student_bp
    from app.admin.routes import admin_bp
    from app.monitoring.routes import monitoring_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(admin_bp,   url_prefix="/admin")
    app.register_blueprint(monitoring_bp, url_prefix="/api/monitor")

    # ------------------------------------------------------------------
    # Flask-Login user loader
    # ------------------------------------------------------------------
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ------------------------------------------------------------------
    # Root redirect
    # ------------------------------------------------------------------
    from flask import redirect, url_for
    from flask_login import current_user

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if current_user.role == "admin":
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("student.dashboard"))
        return redirect(url_for("auth.login"))

    # ------------------------------------------------------------------
    # Custom error pages
    # ------------------------------------------------------------------
    @app.errorhandler(404)
    def page_not_found(e):
        from flask import render_template
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template("errors/500.html"), 500

    return app

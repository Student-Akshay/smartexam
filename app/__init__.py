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

    # ------------------------------------------------------------------
    # Auto-initialize database tables & default seed data
    # ------------------------------------------------------------------
    with app.app_context():
        try:
            db.create_all()
            from app.models.user import User
            from app.models.exam import Exam, Question, ExamConfig
            if not User.query.filter_by(role="admin").first():
                admin = User(full_name="Admin User", email="admin@smartexam.com", role="admin")
                admin.set_password("Admin@123")
                db.session.add(admin)
                db.session.commit()

            if not User.query.filter_by(email="alice@example.com").first():
                student = User(full_name="Alice Johnson", email="alice@example.com", role="student")
                student.set_password("Student@123")
                db.session.add(student)
                db.session.commit()

            if not Exam.query.first():
                admin = User.query.filter_by(role="admin").first()
                if admin:
                    exam1 = Exam(
                        title="Python Basics",
                        description="Test your knowledge of Python fundamentals.",
                        duration_minutes=30,
                        total_marks=10,
                        created_by=admin.id
                    )
                    db.session.add(exam1)
                    db.session.flush()

                    cfg = ExamConfig(
                        exam_id=exam1.id,
                        look_away_threshold_sec=3,
                        max_warnings_before_penalty=3,
                        penalty_marks_per_violation=1,
                        max_penalty_marks=5
                    )
                    db.session.add(cfg)

                    sample_questions = [
                        ("What is the output of print(type([]))?", "<class 'list'>", "<class 'dict'>", "<class 'tuple'>", "<class 'set'>", "A", 1, 1),
                        ("Which keyword is used to define a function in Python?", "function", "def", "fun", "define", "B", 1, 2),
                        ("What does len('hello') return?", "4", "5", "6", "Error", "B", 1, 3),
                        ("Which of these is a mutable data type in Python?", "tuple", "string", "list", "int", "C", 1, 4),
                        ("What is the result of 3 ** 2 in Python?", "6", "8", "9", "5", "C", 1, 5),
                        ("How do you start a comment in Python?", "//", "#", "/*", "--", "B", 1, 6),
                        ("Which method adds an element to the end of a list?", "add()", "insert()", "append()", "push()", "C", 1, 7),
                        ("What is the default return value of a Python function?", "0", "None", "False", "Error", "B", 1, 8),
                        ("Which operator is used for floor division?", "/", "%", "//", "**", "C", 1, 9),
                        ("What does the range(5) function generate?", "[1,2,3,4,5]", "[0,1,2,3,4]", "[0,1,2,3,4,5]", "[1,2,3,4]", "B", 1, 10),
                    ]
                    for q_text, opt_a, opt_b, opt_c, opt_d, cor, m, order in sample_questions:
                        q = Question(
                            exam_id=exam1.id,
                            question_text=q_text,
                            option_a=opt_a,
                            option_b=opt_b,
                            option_c=opt_c,
                            option_d=opt_d,
                            correct_option=cor,
                            marks=m,
                            question_order=order
                        )
                        db.session.add(q)
                    db.session.commit()
        except Exception as exc:
            app.logger.warning("DB auto-init notice: %s", exc)

    return app

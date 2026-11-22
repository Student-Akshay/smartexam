"""
admin/routes.py
---------------
Admin-only dashboard views:
  /admin/dashboard    — overview stats
  /admin/students     — all students
  /admin/results      — all exam results with penalty info
  /admin/violations   — full violation log (filterable)
"""

from flask import (
    Blueprint, render_template, redirect, url_for,
    request, flash, abort
)
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models.user      import User
from app.models.exam      import Exam
from app.models.result    import ExamResult
from app.models.violation import ViolationLog

admin_bp = Blueprint("admin", __name__)


def _admin_only(func):
    """Decorator that aborts with 403 if the current user is not an admin."""
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return func(*args, **kwargs)
    return wrapper


# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------
@admin_bp.route("/dashboard")
@login_required
@_admin_only
def dashboard():
    """Admin overview: total counts and latest activity."""
    total_students  = User.query.filter_by(role="student").count()
    total_exams     = Exam.query.count()
    total_results   = ExamResult.query.filter_by(status="submitted").count()
    total_violations = ViolationLog.query.count()

    # Recent activity (latest 5 submissions)
    recent_results = (
        ExamResult.query
        .filter_by(status="submitted")
        .order_by(ExamResult.submitted_at.desc())
        .limit(5)
        .all()
    )

    # Recent violations
    recent_violations = (
        ViolationLog.query
        .order_by(ViolationLog.detected_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        total_students=total_students,
        total_exams=total_exams,
        total_results=total_results,
        total_violations=total_violations,
        recent_results=recent_results,
        recent_violations=recent_violations,
    )


# ------------------------------------------------------------------
# Students List
# ------------------------------------------------------------------
@admin_bp.route("/students")
@login_required
@_admin_only
def students():
    """List all registered students with their attempt counts."""
    all_students = User.query.filter_by(role="student").order_by(User.created_at.desc()).all()

    # Build a map: student_id → {attempts, latest_result}
    stats = {}
    for s in all_students:
        attempts = ExamResult.query.filter_by(student_id=s.id).count()
        latest   = (
            ExamResult.query
            .filter_by(student_id=s.id, status="submitted")
            .order_by(ExamResult.submitted_at.desc())
            .first()
        )
        total_violations = ViolationLog.query.filter_by(student_id=s.id).count()
        stats[s.id] = {
            "attempts":         attempts,
            "latest_result":    latest,
            "total_violations": total_violations,
        }

    return render_template("admin/students.html", students=all_students, stats=stats)


# ------------------------------------------------------------------
# Add Student by Admin
# ------------------------------------------------------------------
@admin_bp.route("/students/create", methods=["POST"])
@login_required
@_admin_only
def create_student():
    """Create a new student account directly from admin dashboard."""
    full_name = request.form.get("full_name", "").strip()
    email     = request.form.get("email", "").strip().lower()
    password  = request.form.get("password", "").strip()

    errors = []
    if not full_name:
        errors.append("Full name is required.")
    if not email or "@" not in email:
        errors.append("Valid email is required.")
    if len(password) < 6:
        errors.append("Password must be at least 6 characters.")
    if User.query.filter_by(email=email).first():
        errors.append("A user with this email already exists.")

    if errors:
        for err in errors:
            flash(err, "danger")
        return redirect(url_for("admin.students"))

    new_student = User(full_name=full_name, email=email, role="student")
    new_student.set_password(password)
    db.session.add(new_student)
    db.session.commit()

    flash(f"Student '{full_name}' created successfully!", "success")
    return redirect(url_for("admin.students"))


# ------------------------------------------------------------------
# Exam Results
# ------------------------------------------------------------------
@admin_bp.route("/results")
@login_required
@_admin_only
def results():
    """View all submitted and retake-allowed exam results with scores and penalties."""
    exam_filter = request.args.get("exam_id", type=int)
    query = ExamResult.query.filter(ExamResult.status.in_(["submitted", "retake_allowed"]))

    if exam_filter:
        query = query.filter_by(exam_id=exam_filter)

    all_results = query.order_by(ExamResult.started_at.desc()).all()
    all_exams   = Exam.query.order_by(Exam.title).all()

    return render_template(
        "admin/results.html",
        results=all_results,
        exams=all_exams,
        selected_exam_id=exam_filter,
    )


# ------------------------------------------------------------------
# Allow Retake / Reset Exam Attempt
# ------------------------------------------------------------------
@admin_bp.route("/results/<int:result_id>/retake", methods=["POST"])
@login_required
@_admin_only
def allow_retake(result_id):
    """Allow a student to retake an exam."""
    result = ExamResult.query.get_or_404(result_id)
    student_name = result.student.full_name
    exam_title   = result.exam.title
    result.status = "retake_allowed"
    db.session.commit()

    flash(f"Retake allowed for {student_name} on '{exam_title}'.", "success")
    return redirect(request.referrer or url_for("admin.results"))


# ------------------------------------------------------------------
# Violation Log
# ------------------------------------------------------------------
@admin_bp.route("/violations")
@login_required
@_admin_only
def violations():
    """View full violation log with optional filters."""
    student_filter = request.args.get("student_id", type=int)
    exam_filter    = request.args.get("exam_id",    type=int)
    type_filter    = request.args.get("vtype",      type=str)

    query = ViolationLog.query

    if student_filter:
        query = query.filter_by(student_id=student_filter)
    if exam_filter:
        query = query.filter_by(exam_id=exam_filter)
    if type_filter:
        query = query.filter_by(violation_type=type_filter)

    logs         = query.order_by(ViolationLog.detected_at.desc()).all()
    all_students = User.query.filter_by(role="student").order_by(User.full_name).all()
    all_exams    = Exam.query.order_by(Exam.title).all()

    return render_template(
        "admin/violations.html",
        logs=logs,
        students=all_students,
        exams=all_exams,
        violation_types=ViolationLog.VIOLATION_TYPES,
        selected_student_id=student_filter,
        selected_exam_id=exam_filter,
        selected_type=type_filter,
    )

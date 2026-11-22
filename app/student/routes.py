"""
student/routes.py
-----------------
Student-facing routes:
  GET  /student/dashboard          — list available exams + past results
  GET  /student/exam/<exam_id>     — start / resume exam
  POST /student/exam/<exam_id>/submit — grade and save the attempt
  GET  /student/result/<result_id> — view result details
"""

import json
from datetime import datetime, timezone

from flask import (
    Blueprint, render_template, redirect, url_for,
    request, flash, abort, jsonify, current_app
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models.exam   import Exam, ExamConfig
from app.models.result import ExamResult
from app.models.violation import ViolationLog

student_bp = Blueprint("student", __name__)


def _student_only(func):
    """Decorator that aborts with 403 if the user is not a student."""
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.role != "student":
            abort(403)
        return func(*args, **kwargs)
    return wrapper


# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------
@student_bp.route("/dashboard")
@login_required
@_student_only
def dashboard():
    """Show all available exams and the student's past attempts."""
    exams = Exam.query.order_by(Exam.created_at.desc()).all()

    # Map exam_id → most recent result for this student
    results_map = {}
    all_results = (
        ExamResult.query
        .filter_by(student_id=current_user.id)
        .order_by(ExamResult.started_at.desc())
        .all()
    )
    for res in all_results:
        if res.exam_id not in results_map:
            results_map[res.exam_id] = res

    return render_template(
        "student/dashboard.html",
        exams=exams,
        results_map=results_map
    )


# ------------------------------------------------------------------
# Start / Resume Exam
# ------------------------------------------------------------------
@student_bp.route("/exam/<int:exam_id>")
@login_required
@_student_only
def exam(exam_id):
    """
    Load the exam page.
    Creates a fresh ExamResult row only if no in-progress attempt exists.
    """
    exam_obj = Exam.query.get_or_404(exam_id)

    # Check for an existing in-progress attempt
    result = ExamResult.query.filter_by(
        student_id=current_user.id,
        exam_id=exam_id,
        status="in_progress"
    ).first()

    if not result:
        # Start a new attempt
        result = ExamResult(
            student_id=current_user.id,
            exam_id=exam_id,
            status="in_progress"
        )
        db.session.add(result)
        db.session.commit()

    # Load exam config (falls back to app defaults)
    cfg = exam_obj.config or ExamConfig(
        look_away_threshold_sec     = current_app.config["LOOK_AWAY_THRESHOLD_SEC"],
        max_warnings_before_penalty = current_app.config["MAX_WARNINGS_BEFORE_PENALTY"],
        penalty_marks_per_violation = current_app.config["PENALTY_MARKS_PER_VIOLATION"],
        max_penalty_marks           = current_app.config["MAX_PENALTY_MARKS"],
    )

    questions = exam_obj.questions.order_by("question_order").all()
    saved_answers = result.get_answers()

    return render_template(
        "student/exam.html",
        exam=exam_obj,
        result=result,
        questions=questions,
        saved_answers=saved_answers,
        config=cfg
    )


# ------------------------------------------------------------------
# Submit Exam
# ------------------------------------------------------------------
@student_bp.route("/exam/<int:exam_id>/submit", methods=["POST"])
@login_required
@_student_only
def submit_exam(exam_id):
    """
    Receive student answers, grade them, apply existing penalties,
    and finalise the ExamResult.
    """
    exam_obj = Exam.query.get_or_404(exam_id)

    result = ExamResult.query.filter_by(
        student_id=current_user.id,
        exam_id=exam_id,
        status="in_progress"
    ).order_by(ExamResult.started_at.desc()).first()

    if not result:
        # Check if already submitted
        recent_submitted = ExamResult.query.filter_by(
            student_id=current_user.id,
            exam_id=exam_id,
            status="submitted"
        ).order_by(ExamResult.submitted_at.desc()).first()
        if recent_submitted:
            flash("Exam submitted successfully!", "success")
            return redirect(url_for("student.result", result_id=recent_submitted.id))
        flash("No active exam session found.", "warning")
        return redirect(url_for("student.dashboard"))

    try:
        # ---- Collect and grade answers ----
        questions = exam_obj.questions.all()
        answers   = {}
        raw_score = 0

        for q in questions:
            chosen = request.form.get(f"q_{q.id}", "").strip().upper()
            answers[str(q.id)] = chosen
            if chosen == q.correct_option:
                raw_score += q.marks

        # ---- Apply penalties (already accumulated in DB) ----
        final_score = max(0, raw_score - result.penalty_marks)

        # ---- Save ----
        result.score        = raw_score
        result.final_score  = final_score
        result.set_answers(answers)
        result.status       = "submitted"
        result.submitted_at = datetime.now(timezone.utc)
        db.session.commit()

        flash("Exam submitted successfully!", "success")
        return redirect(url_for("student.result", result_id=result.id))
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("Error submitting exam: %s", exc)
        flash("An error occurred while saving your exam. Please try again.", "danger")
        return redirect(url_for("student.exam", exam_id=exam_id))


# ------------------------------------------------------------------
# Result Page
# ------------------------------------------------------------------
@student_bp.route("/result/<int:result_id>")
@login_required
@_student_only
def result(result_id):
    """Show the detailed result of an exam attempt."""
    result_obj = ExamResult.query.get_or_404(result_id)

    # Students can only view their own results
    if result_obj.student_id != current_user.id:
        abort(403)

    questions    = result_obj.exam.questions.all()
    saved_answers = result_obj.get_answers()
    violations   = result_obj.violations.order_by(ViolationLog.detected_at).all()

    return render_template(
        "student/result.html",
        result=result_obj,
        questions=questions,
        saved_answers=saved_answers,
        violations=violations
    )

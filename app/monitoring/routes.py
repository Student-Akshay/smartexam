"""
monitoring/routes.py
--------------------
Two API endpoints consumed by monitor.js:

  POST /api/monitor/frame
      Body: { result_id, frame (base64) }
      Returns: detection result JSON (no DB write — client tracks timing)

  POST /api/monitor/event
      Body: { result_id, violation_type }
      Called by client ONLY after the sustained threshold is exceeded.
      Writes a ViolationLog row; may apply a penalty to ExamResult.
      Returns: { warning_number, penalty_applied, total_penalty, message }
"""

from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.exam      import Exam, ExamConfig
from app.models.result    import ExamResult
from app.models.violation import ViolationLog
from app.monitoring.detector import analyse_frame

monitoring_bp = Blueprint("monitoring", __name__)


def _get_exam_config(exam_id: int) -> dict:
    """
    Fetch per-exam AI thresholds from the database.
    Falls back to application-level defaults from config.py.
    """
    cfg = ExamConfig.query.filter_by(exam_id=exam_id).first()
    if cfg:
        return {
            "look_away_threshold_sec":     cfg.look_away_threshold_sec,
            "max_warnings_before_penalty": cfg.max_warnings_before_penalty,
            "penalty_marks_per_violation": cfg.penalty_marks_per_violation,
            "max_penalty_marks":           cfg.max_penalty_marks,
        }
    return {
        "look_away_threshold_sec":     current_app.config["LOOK_AWAY_THRESHOLD_SEC"],
        "max_warnings_before_penalty": current_app.config["MAX_WARNINGS_BEFORE_PENALTY"],
        "penalty_marks_per_violation": current_app.config["PENALTY_MARKS_PER_VIOLATION"],
        "max_penalty_marks":           current_app.config["MAX_PENALTY_MARKS"],
    }


# ------------------------------------------------------------------
# Frame analysis endpoint
# ------------------------------------------------------------------
@monitoring_bp.route("/frame", methods=["POST"])
@login_required
def analyse():
    """
    Receive a single base64 webcam frame, run AI detection, and return results.
    No database writes happen here — timing and thresholding live in the client.
    """
    data = request.get_json(silent=True) or {}
    b64_frame = data.get("frame", "")
    result_id = data.get("result_id")

    if not b64_frame:
        return jsonify({"error": "No frame data"}), 400

    # Load exam config for thresholds
    cfg = {}
    if result_id:
        result_obj = ExamResult.query.get(result_id)
        if result_obj and result_obj.student_id == current_user.id:
            cfg = _get_exam_config(result_obj.exam_id)

    # Apply config thresholds (or app defaults)
    detection = analyse_frame(
        b64_frame,
        gaze_h_threshold     = current_app.config.get("GAZE_H_THRESHOLD", 0.38),
        gaze_v_threshold     = current_app.config.get("GAZE_V_THRESHOLD", 0.38),
        head_yaw_threshold   = current_app.config.get("HEAD_YAW_THRESHOLD", 25.0),
        head_pitch_threshold = current_app.config.get("HEAD_PITCH_THRESHOLD", 20.0),
    )

    return jsonify(detection)


# ------------------------------------------------------------------
# Violation event endpoint
# ------------------------------------------------------------------
@monitoring_bp.route("/event", methods=["POST"])
@login_required
def record_event():
    """
    Called by monitor.js when a sustained violation threshold is reached.
    Persists a ViolationLog and optionally deducts marks from ExamResult.
    """
    data           = request.get_json(silent=True) or {}
    result_id      = data.get("result_id")
    violation_type = data.get("violation_type", "").upper()

    # ---- Validate ----
    if not result_id or violation_type not in ViolationLog.VIOLATION_TYPES:
        return jsonify({"error": "Invalid payload"}), 400

    result_obj = ExamResult.query.get(result_id)
    if not result_obj or result_obj.student_id != current_user.id:
        return jsonify({"error": "Exam session not found"}), 404

    if result_obj.status != "in_progress":
        return jsonify({"error": "Exam is not active"}), 409

    # ---- Fetch config ----
    cfg = _get_exam_config(result_obj.exam_id)
    max_warn   = cfg["max_warnings_before_penalty"]
    pen_per    = cfg["penalty_marks_per_violation"]
    max_pen    = cfg["max_penalty_marks"]

    # ---- Count existing warnings for this sitting ----
    existing_warnings = ViolationLog.query.filter_by(result_id=result_id).count()
    warning_number    = existing_warnings + 1

    # ---- Determine if a penalty should be applied ----
    penalty_applied = False
    marks_deducted  = 0

    if warning_number % max_warn == 0:
        # Every Nth warning triggers a penalty (if cap not reached)
        remaining_penalty = max_pen - result_obj.penalty_marks
        if remaining_penalty > 0:
            marks_deducted          = min(pen_per, remaining_penalty)
            result_obj.penalty_marks += marks_deducted
            result_obj.final_score   = max(0, result_obj.score - result_obj.penalty_marks)
            penalty_applied         = True

    # ---- Write violation log ----
    log = ViolationLog(
        student_id     = current_user.id,
        exam_id        = result_obj.exam_id,
        result_id      = result_id,
        violation_type = violation_type,
        warning_number = warning_number,
        penalty_marks  = marks_deducted,
        detected_at    = datetime.now(timezone.utc),
    )
    db.session.add(log)
    db.session.commit()

    # ---- Build response message ----
    if penalty_applied:
        message = (
            f"⚠️ Warning #{warning_number}: {log.human_type}. "
            f"{marks_deducted} mark(s) deducted! "
            f"Total penalty: {result_obj.penalty_marks}/{max_pen} mark(s)."
        )
    elif result_obj.penalty_marks >= max_pen:
        message = (
            f"⚠️ Warning #{warning_number}: {log.human_type}. "
            f"Maximum penalty already reached."
        )
    else:
        next_penalty_at = max_warn - (warning_number % max_warn)
        message = (
            f"⚠️ Warning #{warning_number}: {log.human_type}. "
            f"Please focus on your screen. "
            f"Penalty in {next_penalty_at} more warning(s)."
        )

    return jsonify({
        "warning_number":  warning_number,
        "penalty_applied": penalty_applied,
        "marks_deducted":  marks_deducted,
        "total_penalty":   result_obj.penalty_marks,
        "max_penalty":     max_pen,
        "message":         message,
        "violation_type":  violation_type,
    })

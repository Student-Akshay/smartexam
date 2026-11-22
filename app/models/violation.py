"""
models/violation.py
-------------------
ViolationLog model — one row per confirmed suspicious event.
"""

from app.extensions import db


class ViolationLog(db.Model):
    """Records each AI-detected cheating event with warning and penalty info."""
    __tablename__ = "violation_logs"

    # Allowed violation type codes
    VIOLATION_TYPES = [
        "FACE_MISSING",
        "MULTIPLE_FACES",
        "GAZE_LEFT",
        "GAZE_RIGHT",
        "GAZE_UP",
        "GAZE_DOWN",
        "HEAD_TURNED",
    ]

    id             = db.Column(db.Integer,     primary_key=True)
    student_id     = db.Column(db.Integer,     db.ForeignKey("users.id"),        nullable=False)
    exam_id        = db.Column(db.Integer,     db.ForeignKey("exams.id"),         nullable=False)
    result_id      = db.Column(db.Integer,     db.ForeignKey("exam_results.id"), nullable=False)
    violation_type = db.Column(db.String(50),  nullable=False)
    warning_number = db.Column(db.Integer,     nullable=False, default=1)
    penalty_marks  = db.Column(db.Integer,     nullable=False, default=0)
    detected_at    = db.Column(db.DateTime,    server_default=db.func.now())

    # Relationships
    student = db.relationship("User",       back_populates="violations")
    exam    = db.relationship("Exam",       foreign_keys=[exam_id])
    result  = db.relationship("ExamResult", back_populates="violations")

    @property
    def is_penalty(self) -> bool:
        """True if this event actually deducted marks."""
        return self.penalty_marks > 0

    @property
    def human_type(self) -> str:
        """Human-readable violation description."""
        labels = {
            "FACE_MISSING":    "Face Not Detected",
            "MULTIPLE_FACES":  "Multiple Faces Detected",
            "GAZE_LEFT":       "Looking Left",
            "GAZE_RIGHT":      "Looking Right",
            "GAZE_UP":         "Looking Up",
            "GAZE_DOWN":       "Looking Down",
            "HEAD_TURNED":     "Head Turned Away",
        }
        return labels.get(self.violation_type, self.violation_type)

    def __repr__(self) -> str:
        return f"<ViolationLog {self.violation_type} student={self.student_id} warning={self.warning_number}>"

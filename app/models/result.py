"""
models/result.py
----------------
ExamResult model — one row per student per exam sitting.
"""

import json
from app.extensions import db


class ExamResult(db.Model):
    """Stores the outcome of one exam attempt by a student."""
    __tablename__ = "exam_results"

    id            = db.Column(db.Integer,  primary_key=True)
    student_id    = db.Column(db.Integer,  db.ForeignKey("users.id"),  nullable=False)
    exam_id       = db.Column(db.Integer,  db.ForeignKey("exams.id"),  nullable=False)
    score         = db.Column(db.Integer,  nullable=False, default=0)   # raw marks
    penalty_marks = db.Column(db.Integer,  nullable=False, default=0)   # total deducted
    final_score   = db.Column(db.Integer,  nullable=False, default=0)   # score - penalty (>= 0)
    started_at    = db.Column(db.DateTime, server_default=db.func.now())
    submitted_at  = db.Column(db.DateTime, nullable=True)
    status        = db.Column(
        db.Enum("in_progress", "submitted", "terminated", "retake_allowed"),
        nullable=False, default="in_progress"
    )
    answers_json  = db.Column(db.Text, nullable=True)  # JSON dict {question_id: chosen_option}

    # Relationships
    student    = db.relationship("User",         back_populates="exam_results")
    exam       = db.relationship("Exam",         back_populates="results")
    violations = db.relationship("ViolationLog", back_populates="result", lazy="dynamic")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def get_answers(self) -> dict:
        """Deserialise the stored JSON answers (returns {} if none)."""
        if self.answers_json:
            return json.loads(self.answers_json)
        return {}

    def set_answers(self, answers: dict) -> None:
        """Serialise answers dict to JSON for storage."""
        self.answers_json = json.dumps(answers)

    @property
    def percentage(self) -> float:
        """Return final_score as a percentage of total exam marks."""
        total = self.exam.total_marks if self.exam else 1
        return round((self.final_score / max(total, 1)) * 100, 1)

    def __repr__(self) -> str:
        return f"<ExamResult student={self.student_id} exam={self.exam_id} score={self.final_score}>"

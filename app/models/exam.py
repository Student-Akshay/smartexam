"""
models/exam.py
--------------
Exam and Question models.
Exam contains many Questions.
"""

from app.extensions import db


class Exam(db.Model):
    """Represents a single online examination."""
    __tablename__ = "exams"

    id               = db.Column(db.Integer,     primary_key=True)
    title            = db.Column(db.String(200),  nullable=False)
    description      = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer,      nullable=False, default=30)
    total_marks      = db.Column(db.Integer,      nullable=False, default=0)
    created_by       = db.Column(db.Integer,      db.ForeignKey("users.id"), nullable=False)
    created_at       = db.Column(db.DateTime,     server_default=db.func.now())

    # Relationships
    questions = db.relationship(
        "Question", back_populates="exam",
        order_by="Question.question_order", lazy="dynamic"
    )
    results   = db.relationship("ExamResult",  back_populates="exam",   lazy="dynamic")
    config    = db.relationship("ExamConfig",  back_populates="exam",   uselist=False)
    creator   = db.relationship("User",         foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<Exam '{self.title}'>"


class Question(db.Model):
    """A single MCQ question belonging to an exam."""
    __tablename__ = "questions"

    id             = db.Column(db.Integer,     primary_key=True)
    exam_id        = db.Column(db.Integer,     db.ForeignKey("exams.id"), nullable=False)
    question_text  = db.Column(db.Text,        nullable=False)
    option_a       = db.Column(db.String(500), nullable=False)
    option_b       = db.Column(db.String(500), nullable=False)
    option_c       = db.Column(db.String(500), nullable=False)
    option_d       = db.Column(db.String(500), nullable=False)
    correct_option = db.Column(db.Enum("A","B","C","D"), nullable=False)
    marks          = db.Column(db.Integer,     nullable=False, default=1)
    question_order = db.Column(db.Integer,     nullable=False, default=0)

    # Relationship
    exam = db.relationship("Exam", back_populates="questions")

    def __repr__(self) -> str:
        return f"<Question {self.id} (Exam {self.exam_id})>"


class ExamConfig(db.Model):
    """
    Per-exam AI monitoring thresholds.
    Falls back to Config defaults when no row exists.
    """
    __tablename__ = "exam_config"

    id                          = db.Column(db.Integer, primary_key=True)
    exam_id                     = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False, unique=True)
    look_away_threshold_sec     = db.Column(db.Integer, nullable=False, default=3)
    max_warnings_before_penalty = db.Column(db.Integer, nullable=False, default=3)
    penalty_marks_per_violation = db.Column(db.Integer, nullable=False, default=1)
    max_penalty_marks           = db.Column(db.Integer, nullable=False, default=5)

    # Relationship
    exam = db.relationship("Exam", back_populates="config")

    def __repr__(self) -> str:
        return f"<ExamConfig for Exam {self.exam_id}>"

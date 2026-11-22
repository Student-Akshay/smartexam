"""
models/user.py
--------------
User model representing both students and admins.
Flask-Login mixins provide is_authenticated, is_active, etc.
"""

import bcrypt
from flask_login import UserMixin
from app.extensions import db


class User(UserMixin, db.Model):
    """Unified user table for students and admins."""
    __tablename__ = "users"

    id            = db.Column(db.Integer,     primary_key=True)
    full_name     = db.Column(db.String(120),  nullable=False)
    email         = db.Column(db.String(180),  nullable=False, unique=True)
    password_hash = db.Column(db.String(255),  nullable=False)
    role          = db.Column(db.Enum("student", "admin"), nullable=False, default="student")
    created_at    = db.Column(db.DateTime,     server_default=db.func.now())

    # Relationships
    exam_results  = db.relationship("ExamResult",  back_populates="student",  lazy="dynamic")
    violations    = db.relationship("ViolationLog", back_populates="student", lazy="dynamic")

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------
    def set_password(self, plain_text: str) -> None:
        """Hash and store a plain-text password."""
        self.password_hash = bcrypt.hashpw(
            plain_text.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, plain_text: str) -> bool:
        """Verify a plain-text password against the stored hash."""
        return bcrypt.checkpw(
            plain_text.encode("utf-8"),
            self.password_hash.encode("utf-8")
        )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"

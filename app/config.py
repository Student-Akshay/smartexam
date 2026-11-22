"""
config.py
---------
Central configuration for SmartExam.
All tuneable values (AI thresholds, DB credentials, security settings)
live here so they can be changed without touching business logic.
"""

import os


class Config:
    # ------------------------------------------------------------------
    # Flask / Security
    # ------------------------------------------------------------------
    SECRET_KEY = os.environ.get("SECRET_KEY", "smartexam-super-secret-key-change-in-prod")
    DEBUG = os.environ.get("DEBUG", "true").lower() == "true"

    # ------------------------------------------------------------------
    # Database (Supabase / Render PostgreSQL or local MySQL)
    # ------------------------------------------------------------------
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if DATABASE_URL:
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        DB_HOST     = os.environ.get("DB_HOST",     "localhost")
        DB_PORT     = int(os.environ.get("DB_PORT", "3306"))
        DB_USER     = os.environ.get("DB_USER",     "root")
        DB_PASSWORD = os.environ.get("DB_PASSWORD", "Akshay20092006")
        DB_NAME     = os.environ.get("DB_NAME",     "smartexam")

        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            "?charset=utf8mb4"
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ------------------------------------------------------------------
    # AI Monitoring — Default thresholds
    # (Can be overridden per-exam in the exam_config table)
    # ------------------------------------------------------------------

    # Seconds a student must look away continuously before it counts as suspicious
    LOOK_AWAY_THRESHOLD_SEC: int = 3

    # How many confirmed suspicious events before a mark is deducted
    MAX_WARNINGS_BEFORE_PENALTY: int = 3

    # Marks deducted per penalty event
    PENALTY_MARKS_PER_VIOLATION: int = 1

    # Maximum total marks that can be deducted via penalties (hard cap)
    MAX_PENALTY_MARKS: int = 5

    # ------------------------------------------------------------------
    # Gaze / Head-pose detection thresholds
    # (Tuned for typical webcam-to-monitor distances)
    # ------------------------------------------------------------------

    # Eye gaze offset thresholds (normalized deviation from center: 0.0=center, 1.0=edge)
    GAZE_H_THRESHOLD: float = 0.38    # > +0.38 is Right, < -0.38 is Left
    GAZE_V_THRESHOLD: float = 0.38    # > +0.38 is Down, < -0.38 is Up

    # Head yaw angle (degrees) beyond which "head turned" is triggered
    HEAD_YAW_THRESHOLD: float = 25.0

    # Head pitch angle (degrees) — downward/upward tilt
    HEAD_PITCH_THRESHOLD: float = 20.0

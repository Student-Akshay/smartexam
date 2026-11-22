"""
extensions.py
-------------
Initialises shared Flask extensions (SQLAlchemy, LoginManager) without
creating a circular import.  The actual app is bound in app/__init__.py.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# SQLAlchemy instance — imported by models and used everywhere
db = SQLAlchemy()

# Flask-Login manager
login_manager = LoginManager()
login_manager.login_view = "auth.login"          # redirect target for @login_required
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"

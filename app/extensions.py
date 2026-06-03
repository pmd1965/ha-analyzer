from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
# Not init_app'd — started manually in create_app to control lifecycle.
scheduler = BackgroundScheduler(timezone="UTC")

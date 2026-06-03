from __future__ import annotations

from flask import Blueprint, jsonify, render_template

from app.extensions import db
from app.models.analysis_result import AnalysisResult
from app.models.scenario import Scenario

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    scenarios = Scenario.query.order_by(Scenario.name).all()
    recent_anomalies = (
        AnalysisResult.query.filter_by(anomaly_detected=True)
        .order_by(AnalysisResult.run_at.desc())
        .limit(10)
        .all()
    )
    recent_runs = (
        AnalysisResult.query.order_by(AnalysisResult.run_at.desc()).limit(5).all()
    )
    return render_template(
        "main/index.html",
        scenarios=scenarios,
        recent_anomalies=recent_anomalies,
        recent_runs=recent_runs,
    )


@bp.get("/healthz")
def healthz():
    # Confirm DB is reachable
    db.session.execute(db.text("SELECT 1"))
    return jsonify({"status": "ok"})

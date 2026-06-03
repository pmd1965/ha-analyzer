from __future__ import annotations

import structlog
from flask import Blueprint, jsonify

from app.extensions import csrf, db
from app.models.scenario import Scenario
from app.services.analyzer import run_analysis

bp = Blueprint("api", __name__, url_prefix="/api")
logger = structlog.get_logger(__name__)


@bp.get("/analyze/<int:scenario_id>")
@csrf.exempt
def analyze(scenario_id: int):
    """Trigger an analysis run for the given scenario. Returns JSON result."""
    scenario = db.session.get(Scenario, scenario_id)
    if scenario is None:
        return jsonify({"error": f"Scenario {scenario_id} not found"}), 404

    try:
        result = run_analysis(scenario_id, trigger="api")
        return jsonify(
            {
                "id": result.id,
                "scenario_id": scenario_id,
                "scenario_name": scenario.name,
                "anomaly": result.anomaly_detected,
                "severity": result.severity,
                "summary": result.summary,
                "run_at": result.run_at.isoformat(),
            }
        )
    except Exception as exc:
        logger.error("api_analysis_failed", scenario_id=scenario_id, error=str(exc))
        return jsonify({"error": str(exc)}), 500


@bp.get("/scenarios")
@csrf.exempt
def list_scenarios():
    """List all active scenarios (for external integrations)."""
    from app.models.scenario import Scenario

    scenarios = Scenario.query.filter_by(is_active=True).order_by(Scenario.name).all()
    return jsonify(
        [
            {
                "id": s.id,
                "name": s.name,
                "cron": s.cron_expression,
                "entity_ids": s.entity_ids,
            }
            for s in scenarios
        ]
    )

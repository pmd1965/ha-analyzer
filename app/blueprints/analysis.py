from __future__ import annotations

from flask import Blueprint, render_template, request

from app.models.analysis_result import AnalysisResult
from app.models.scenario import Scenario

bp = Blueprint("analysis", __name__, url_prefix="/analysis")


@bp.get("/")
def list_results():
    page = request.args.get("page", 1, type=int)
    scenario_id = request.args.get("scenario_id", type=int)
    anomaly_only = request.args.get("anomaly_only") == "1"

    query = AnalysisResult.query.order_by(AnalysisResult.run_at.desc())
    if scenario_id:
        query = query.filter_by(scenario_id=scenario_id)
    if anomaly_only:
        query = query.filter_by(anomaly_detected=True)

    pagination = query.paginate(page=page, per_page=20, error_out=False)
    scenarios = Scenario.query.order_by(Scenario.name).all()

    return render_template(
        "analysis/list.html",
        pagination=pagination,
        results=pagination.items,
        scenarios=scenarios,
        current_scenario_id=scenario_id,
        anomaly_only=anomaly_only,
    )


@bp.get("/<int:result_id>")
def detail(result_id: int):
    from app.extensions import db
    import json

    result = db.get_or_404(AnalysisResult, result_id)

    # Try to parse the LLM JSON for pretty display
    parsed_llm: dict | None = None
    try:
        parsed_llm = json.loads(result.llm_response)
    except (json.JSONDecodeError, TypeError):
        pass

    return render_template(
        "analysis/detail.html",
        result=result,
        parsed_llm=parsed_llm,
    )

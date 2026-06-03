from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

import structlog

from app.extensions import db
from app.models.scenario import Scenario
from app.services.analyzer import DEFAULT_PROMPT_TEMPLATE, run_analysis

bp = Blueprint("scenarios", __name__, url_prefix="/scenarios")
logger = structlog.get_logger(__name__)


@bp.get("/")
def list_scenarios():
    scenarios = Scenario.query.order_by(Scenario.name).all()
    return render_template("scenarios/list.html", scenarios=scenarios)


@bp.get("/new")
def new():
    from app.services.influxdb_service import list_entity_ids

    entity_ids = list_entity_ids()
    return render_template(
        "scenarios/form.html",
        scenario=None,
        entity_ids=entity_ids,
        default_prompt=DEFAULT_PROMPT_TEMPLATE,
    )


@bp.post("/new")
def create():
    scenario = Scenario()
    _apply_form(scenario, request.form)
    db.session.add(scenario)
    db.session.commit()
    _sync_scheduler_job(scenario)
    flash(f"Scenario '{scenario.name}' created.", "success")
    logger.info("scenario_created", scenario_id=scenario.id)
    return redirect(url_for("scenarios.list_scenarios"))


@bp.get("/<int:scenario_id>/edit")
def edit(scenario_id: int):
    from app.services.influxdb_service import list_entity_ids

    scenario = db.get_or_404(Scenario, scenario_id)
    entity_ids = list_entity_ids()
    return render_template(
        "scenarios/form.html",
        scenario=scenario,
        entity_ids=entity_ids,
        default_prompt=DEFAULT_PROMPT_TEMPLATE,
    )


@bp.post("/<int:scenario_id>/edit")
def update(scenario_id: int):
    scenario = db.get_or_404(Scenario, scenario_id)
    _apply_form(scenario, request.form)
    db.session.commit()
    _sync_scheduler_job(scenario)
    flash(f"Scenario '{scenario.name}' updated.", "success")
    logger.info("scenario_updated", scenario_id=scenario.id)
    return redirect(url_for("scenarios.list_scenarios"))


@bp.post("/<int:scenario_id>/delete")
def delete(scenario_id: int):
    scenario = db.get_or_404(Scenario, scenario_id)
    name = scenario.name
    from app.services.scheduler import remove_scenario_job
    remove_scenario_job(scenario_id)
    db.session.delete(scenario)
    db.session.commit()
    flash(f"Scenario '{name}' deleted.", "info")
    logger.info("scenario_deleted", scenario_id=scenario_id)
    return redirect(url_for("scenarios.list_scenarios"))


@bp.post("/<int:scenario_id>/run")
def run(scenario_id: int):
    scenario = db.get_or_404(Scenario, scenario_id)
    try:
        result = run_analysis(scenario_id, trigger="manual")
        flash(
            f"Analysis complete — {'Anomaly detected' if result.anomaly_detected else 'Normal'}.",
            "warning" if result.anomaly_detected else "success",
        )
        return redirect(url_for("analysis.detail", result_id=result.id))
    except Exception as exc:
        logger.error("manual_run_failed", scenario_id=scenario_id, error=str(exc))
        flash(f"Analysis failed: {exc}", "danger")
        return redirect(url_for("scenarios.list_scenarios"))


def _apply_form(scenario: Scenario, form: dict) -> None:
    scenario.name = form.get("name", "").strip()
    scenario.description = form.get("description", "").strip() or None
    scenario.is_active = form.get("is_active") == "on"
    scenario.time_window_hours = int(form.get("time_window_hours", 24))
    scenario.aggregate_window = form.get("aggregate_window", "30m").strip()
    scenario.cron_expression = form.get("cron_expression", "").strip() or None
    scenario.alert_on_anomaly = form.get("alert_on_anomaly") == "on"
    scenario.prompt_template = form.get("prompt_template", DEFAULT_PROMPT_TEMPLATE).strip()

    raw_ids = form.get("entity_ids", "")
    ids = [eid.strip() for eid in raw_ids.splitlines() if eid.strip()]
    scenario.entity_ids = ids


def _sync_scheduler_job(scenario: Scenario) -> None:
    from app.extensions import scheduler
    from app.services.scheduler import add_scenario_job, remove_scenario_job
    import flask

    app = flask.current_app._get_current_object()
    if scenario.is_active and scenario.cron_expression:
        add_scenario_job(scheduler, app, scenario)
    else:
        remove_scenario_job(scenario.id)

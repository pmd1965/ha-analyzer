from __future__ import annotations

import os

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask

logger = structlog.get_logger(__name__)


def start_scheduler(app: Flask) -> None:
    """Register all active scenario jobs and start the APScheduler background thread."""
    from app.extensions import scheduler

    # In Flask dev mode the reloader forks a child process; only start the scheduler
    # in the child (WERKZEUG_RUN_MAIN=true) to avoid double-firing.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    if scheduler.running:
        return

    with app.app_context():
        _register_all_jobs(scheduler, app)

    scheduler.start()
    logger.info("scheduler_started")


def _register_all_jobs(scheduler: BackgroundScheduler, app: Flask) -> None:
    from app.models.scenario import Scenario

    scenarios = Scenario.query.filter(
        Scenario.is_active.is_(True),
        Scenario.cron_expression.isnot(None),
    ).all()

    for scenario in scenarios:
        add_scenario_job(scheduler, app, scenario)

    logger.info("scheduler_jobs_registered", count=len(scenarios))


def add_scenario_job(scheduler: BackgroundScheduler, app: Flask, scenario: object) -> None:
    """Register (or re-register) an APScheduler job for a scenario."""
    job_id = f"scenario_{scenario.id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if not scenario.cron_expression:
        return

    trigger = CronTrigger.from_crontab(scenario.cron_expression, timezone="UTC")
    scheduler.add_job(
        func=_run_in_context,
        trigger=trigger,
        id=job_id,
        name=scenario.name,
        args=[app, scenario.id],
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info("job_registered", scenario_id=scenario.id, cron=scenario.cron_expression)


def remove_scenario_job(scenario_id: int) -> None:
    from app.extensions import scheduler

    job_id = f"scenario_{scenario_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info("job_removed", scenario_id=scenario_id)


def _run_in_context(app: Flask, scenario_id: int) -> None:
    with app.app_context():
        from app.services.analyzer import run_analysis

        try:
            run_analysis(scenario_id, trigger="scheduled")
        except Exception as exc:
            logger.error("scheduled_analysis_failed", scenario_id=scenario_id, error=str(exc))

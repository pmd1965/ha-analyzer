from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog

from app.extensions import db
from app.models.analysis_result import AnalysisResult
from app.models.scenario import Scenario
from app.services.influxdb_service import EntityReading, get_entity_data
from app.services.notifier import notify_anomaly
from app.services.ollama_service import run_analysis_prompt

logger = structlog.get_logger(__name__)

# Default prompt template used when creating a new scenario.
DEFAULT_PROMPT_TEMPLATE = """\
Analysis scenario: {scenario_name}
Time window: {time_window}
Analysis run at: {run_at}

=== Sensor Data ===
{entity_summary}

=== Context ===
{context}

Analyse this data and determine if there are any anomalies. Consider whether the \
sensors are behaving as expected given the time of day, the relationships between \
entities (e.g. indoor vs outdoor temperature), and normal operating patterns for \
a UK residential home.
"""


def run_analysis(scenario_id: int, trigger: str = "manual") -> AnalysisResult:
    """Fetch data, run LLM analysis, persist result, notify if anomaly."""
    scenario = db.session.get(Scenario, scenario_id)
    if scenario is None:
        raise ValueError(f"Scenario {scenario_id!r} not found")

    logger.info("analysis_started", scenario_id=scenario_id, trigger=trigger)

    readings = get_entity_data(
        scenario.entity_ids,
        scenario.time_window_hours,
        scenario.aggregate_window,
    )

    entity_summary = _format_entity_summary(readings)
    context = _build_context(readings)

    now = datetime.now(timezone.utc)
    user_prompt = scenario.prompt_template.format(
        scenario_name=scenario.name,
        time_window=f"last {scenario.time_window_hours} hours",
        run_at=now.strftime("%Y-%m-%d %H:%M UTC"),
        entity_summary=entity_summary,
        context=context,
    )

    llm_response, anomaly_detected, severity = run_analysis_prompt(
        user_prompt, now.strftime("%Y-%m-%d %H:%M")
    )

    summary = _extract_summary(llm_response)

    result = AnalysisResult(
        scenario_id=scenario_id,
        trigger=trigger,
        llm_response=llm_response,
        anomaly_detected=anomaly_detected,
        severity=severity,
        summary=summary,
        data_snapshot=entity_summary[:4000],
    )
    db.session.add(result)
    db.session.commit()

    if anomaly_detected and scenario.alert_on_anomaly:
        try:
            notify_anomaly(scenario.name, result.id, summary or "Anomaly detected", severity)
            result.notification_sent = True
        except Exception as exc:
            logger.error("notification_failed", error=str(exc))
            result.notification_error = str(exc)
        db.session.commit()

    logger.info(
        "analysis_complete",
        scenario_id=scenario_id,
        anomaly=anomaly_detected,
        severity=severity,
    )
    return result


def _format_entity_summary(readings: list[EntityReading]) -> str:
    lines: list[str] = []
    for r in readings:
        lines.append(f"Entity: {r.entity_id} ({r.friendly_name})")
        lines.append(f"  Domain: {r.domain} | Unit: {r.unit or 'N/A'} | Readings: {len(r.values)}")
        if r.min_val is not None:
            lines.append(
                f"  Min: {r.min_val}{r.unit} | Max: {r.max_val}{r.unit} | "
                f"Mean: {r.mean_val}{r.unit} | Last: {r.last_val}{r.unit}"
            )
        # Sample at most 24 values for the trend
        if len(r.values) > 24:
            step = len(r.values) // 24
            sampled = r.values[::step][:24]
        else:
            sampled = list(r.values)
        # Format numeric values to 1 dp
        formatted = [
            f"{v:.1f}" if isinstance(v, float) else str(v)
            for v in sampled
        ]
        lines.append(f"  Trend (sampled): [{', '.join(formatted)}]")
        lines.append("")
    return "\n".join(lines)


def _build_context(readings: list[EntityReading]) -> str:
    """Extract contextual observations to help ground the LLM analysis."""
    notes: list[str] = []

    outdoor = next(
        (r for r in readings if "outdoor" in r.entity_id or "outside" in r.entity_id
         or "weather" in r.entity_id), None
    )
    if outdoor and outdoor.mean_val is not None:
        notes.append(
            f"Outdoor temperature (approx): mean={outdoor.mean_val}{outdoor.unit}, "
            f"last={outdoor.last_val}{outdoor.unit}"
        )

    indoor_temps = [
        r for r in readings
        if r.domain == "sensor" and "temperature" in r.entity_id and r != outdoor
    ]
    if indoor_temps and outdoor and outdoor.mean_val is not None:
        for r in indoor_temps:
            if r.mean_val is not None:
                diff = round(r.mean_val - outdoor.mean_val, 1)
                notes.append(f"{r.friendly_name} is on average {diff:+}{r.unit} vs outdoor")

    if not notes:
        notes.append("No additional context derived from entity relationships.")

    return "\n".join(notes)


def _extract_summary(llm_response: str) -> str | None:
    try:
        data = json.loads(llm_response)
        return str(data.get("summary", ""))[:500]
    except (json.JSONDecodeError, KeyError):
        first_line = llm_response.strip().splitlines()[0] if llm_response.strip() else ""
        return first_line[:500] or None

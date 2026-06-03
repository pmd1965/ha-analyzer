from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import structlog
from flask import current_app
from influxdb_client import InfluxDBClient

logger = structlog.get_logger(__name__)


@dataclass
class EntityReading:
    entity_id: str
    friendly_name: str
    domain: str
    unit: str
    timestamps: list[datetime] = field(default_factory=list)
    values: list[float | str] = field(default_factory=list)
    min_val: float | None = None
    max_val: float | None = None
    mean_val: float | None = None
    last_val: float | str | None = None


def get_entity_data(
    entity_ids: list[str],
    time_window_hours: int,
    aggregate_window: str = "30m",
) -> list[EntityReading]:
    """Fetch and downsample time-series data for the given HA entity IDs from InfluxDB."""
    if not entity_ids:
        return []

    entity_filter = " or ".join(f'r["entity_id"] == "{eid}"' for eid in entity_ids)
    bucket = current_app.config["INFLUXDB_BUCKET"]

    flux_query = f"""
from(bucket: "{bucket}")
  |> range(start: -{time_window_hours}h)
  |> filter(fn: (r) => {entity_filter})
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: {aggregate_window}, fn: mean, createEmpty: false)
  |> sort(columns: ["_time"])
"""

    results: dict[str, EntityReading] = {}
    client = _get_client()
    try:
        tables = client.query_api().query(flux_query)
        for table in tables:
            for record in table.records:
                eid = record.values.get("entity_id", "unknown")
                if eid not in results:
                    results[eid] = EntityReading(
                        entity_id=eid,
                        friendly_name=record.values.get("friendly_name", eid),
                        domain=record.values.get("domain", ""),
                        unit=record.values.get("unit_of_measurement", ""),
                    )
                results[eid].timestamps.append(record.get_time())
                val = record.get_value()
                results[eid].values.append(val)

        for reading in results.values():
            numeric = [v for v in reading.values if isinstance(v, (int, float))]
            if numeric:
                reading.min_val = round(min(numeric), 2)
                reading.max_val = round(max(numeric), 2)
                reading.mean_val = round(sum(numeric) / len(numeric), 2)
            if reading.values:
                reading.last_val = reading.values[-1]

        logger.info(
            "influxdb_query_ok",
            entity_count=len(results),
            window_hours=time_window_hours,
        )
    except Exception as exc:
        logger.error("influxdb_query_failed", error=str(exc))
        raise
    finally:
        client.close()

    return list(results.values())


def list_entity_ids(limit: int = 500) -> list[str]:
    """Return a distinct list of entity_ids present in the bucket (for the scenario form)."""
    bucket = current_app.config["INFLUXDB_BUCKET"]
    flux_query = f"""
from(bucket: "{bucket}")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_field"] == "value")
  |> keep(columns: ["entity_id"])
  |> distinct(column: "entity_id")
  |> limit(n: {limit})
"""
    client = _get_client()
    try:
        tables = client.query_api().query(flux_query)
        ids = []
        for table in tables:
            for record in table.records:
                val = record.get_value()
                if val:
                    ids.append(val)
        return sorted(ids)
    except Exception as exc:
        logger.error("influxdb_list_entities_failed", error=str(exc))
        return []
    finally:
        client.close()


def _get_client() -> InfluxDBClient:
    return InfluxDBClient(
        url=current_app.config["INFLUXDB_URL"],
        token=current_app.config["INFLUXDB_TOKEN"],
        org=current_app.config["INFLUXDB_ORG"],
        timeout=30_000,
    )

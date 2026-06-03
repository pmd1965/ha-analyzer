from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import structlog
from flask import current_app
from influxdb_client import InfluxDBClient

logger = structlog.get_logger(__name__)

# Fields exposed as selectable sub-items for multi-field domains.
# climate entities store attributes as separate InfluxDB fields alongside "value".
_DOMAIN_EXTRA_FIELDS: dict[str, list[str]] = {
    "climate": [
        "current_temperature",
        "temperature",        # setpoint / target temperature
        "hvac_action_str",    # heat, idle, cool, off
    ],
}


def _parse_spec(spec: str) -> tuple[str, str]:
    """Split 'entity_id::field_name' into (entity_id, field_name).
    Plain 'entity_id' defaults to field_name='value'.
    """
    if "::" in spec:
        eid, fld = spec.split("::", 1)
        return eid.strip(), fld.strip()
    return spec.strip(), "value"


@dataclass
class EntityReading:
    entity_id: str
    field_name: str         # the InfluxDB _field queried ("value", "current_temperature", etc.)
    friendly_name: str
    domain: str
    unit: str
    timestamps: list[datetime] = field(default_factory=list)
    values: list[float | str] = field(default_factory=list)
    min_val: float | None = None
    max_val: float | None = None
    mean_val: float | None = None
    last_val: float | str | None = None

    @property
    def label(self) -> str:
        """Human-readable label combining entity_id and field (if not 'value')."""
        if self.field_name == "value":
            return self.entity_id
        return f"{self.entity_id}::{self.field_name}"


def get_entity_data(
    entity_specs: list[str],
    time_window_hours: int,
    aggregate_window: str = "30m",
) -> list[EntityReading]:
    """Fetch and downsample time-series data for the given entity specs from InfluxDB.

    Each spec is either a plain entity_id (uses _field="value") or
    'entity_id::field_name' to query a specific attribute field.
    """
    if not entity_specs:
        return []

    # Group specs by field so we can issue one Flux query per unique field.
    by_field: dict[str, list[str]] = {}
    for spec in entity_specs:
        eid, fld = _parse_spec(spec)
        by_field.setdefault(fld, []).append(eid)

    bucket = current_app.config["INFLUXDB_BUCKET"]
    all_readings: list[EntityReading] = []

    client = _get_client()
    try:
        for field_name, eids in by_field.items():
            entity_filter = " or ".join(f'r["entity_id"] == "{eid}"' for eid in eids)

            # String fields (like hvac_action_str) can't be mean-aggregated.
            if field_name.endswith("_str") or field_name == "value" and _is_string_field(field_name):
                agg_clause = ""
            else:
                agg_clause = f"|> aggregateWindow(every: {aggregate_window}, fn: mean, createEmpty: false)"

            flux_query = f"""
from(bucket: "{bucket}")
  |> range(start: -{time_window_hours}h)
  |> filter(fn: (r) => {entity_filter})
  |> filter(fn: (r) => r["_field"] == "{field_name}")
  {agg_clause}
  |> sort(columns: ["_time"])
"""
            tables = client.query_api().query(flux_query)
            readings: dict[str, EntityReading] = {}

            for table in tables:
                for record in table.records:
                    eid = record.values.get("entity_id", "unknown")
                    key = f"{eid}::{field_name}"
                    if key not in readings:
                        readings[key] = EntityReading(
                            entity_id=eid,
                            field_name=field_name,
                            friendly_name=record.values.get("friendly_name", eid),
                            domain=record.values.get("domain", ""),
                            unit=record.values.get("unit_of_measurement", ""),
                        )
                    readings[key].timestamps.append(record.get_time())
                    readings[key].values.append(record.get_value())

            for reading in readings.values():
                numeric = [v for v in reading.values if isinstance(v, (int, float))]
                if numeric:
                    reading.min_val = round(min(numeric), 2)
                    reading.max_val = round(max(numeric), 2)
                    reading.mean_val = round(sum(numeric) / len(numeric), 2)
                if reading.values:
                    reading.last_val = reading.values[-1]
                all_readings.append(reading)

        logger.info(
            "influxdb_query_ok",
            entity_count=len(all_readings),
            window_hours=time_window_hours,
        )
    except Exception as exc:
        logger.error("influxdb_query_failed", error=str(exc))
        raise
    finally:
        client.close()

    return all_readings


def list_entity_ids(limit: int = 500) -> list[str]:
    """Return selectable entity specs for the scenario form.

    Returns plain entity_ids (field=value) for most domains, plus
    'entity_id::field_name' entries for domains with useful extra fields
    (e.g. climate::current_temperature, climate::temperature).
    """
    bucket = current_app.config["INFLUXDB_BUCKET"]

    # Query all entity_ids that have a "value" field (covers sensor, binary_sensor, switch, etc.)
    base_query = f"""
from(bucket: "{bucket}")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_field"] == "value")
  |> keep(columns: ["entity_id"])
  |> distinct(column: "entity_id")
  |> limit(n: {limit})
"""
    # Also query entity_ids per extra field for domains that expose attributes.
    extra_queries: dict[str, str] = {}
    for domain, fields in _DOMAIN_EXTRA_FIELDS.items():
        for fld in fields:
            extra_queries[f"{domain}::{fld}"] = f"""
from(bucket: "{bucket}")
  |> range(start: -7d)
  |> filter(fn: (r) => r["domain"] == "{domain}")
  |> filter(fn: (r) => r["_field"] == "{fld}")
  |> keep(columns: ["entity_id"])
  |> distinct(column: "entity_id")
  |> limit(n: 200)
"""

    client = _get_client()
    try:
        specs: list[str] = []

        # Base entity_ids
        for table in client.query_api().query(base_query):
            for record in table.records:
                val = record.get_value()
                if val:
                    specs.append(val)

        # Extra attribute specs — rendered as "entity_id::field_name"
        for field_spec, query in extra_queries.items():
            _, fld = field_spec.split("::", 1)
            for table in client.query_api().query(query):
                for record in table.records:
                    eid = record.get_value()
                    if eid:
                        specs.append(f"{eid}::{fld}")

        return sorted(set(specs))
    except Exception as exc:
        logger.error("influxdb_list_entities_failed", error=str(exc))
        return []
    finally:
        client.close()


def _is_string_field(field_name: str) -> bool:
    return field_name.endswith("_str")


def _get_client() -> InfluxDBClient:
    return InfluxDBClient(
        url=current_app.config["INFLUXDB_URL"],
        token=current_app.config["INFLUXDB_TOKEN"],
        org=current_app.config["INFLUXDB_ORG"],
        timeout=30_000,
    )

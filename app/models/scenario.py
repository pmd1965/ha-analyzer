from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.analysis_result import AnalysisResult


class Scenario(db.Model):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # JSON list of InfluxDB entity_id tag values
    # e.g. ["sensor.living_room_temperature", "climate.living_room", "sensor.outdoor_temp"]
    entity_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # How far back to fetch data (hours)
    time_window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)

    # InfluxDB aggregation window for downsampling (e.g. "30m", "1h")
    aggregate_window: Mapped[str] = mapped_column(String(10), nullable=False, default="30m")

    # Jinja2-style template with {scenario_name}, {time_window}, {run_at},
    # {entity_summary}, {context} placeholders
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Cron expression for scheduled runs; null = manual / API only
    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Whether to send Telegram + email when anomaly_detected=True
    alert_on_anomaly: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    results: Mapped[list[AnalysisResult]] = relationship(
        "AnalysisResult",
        back_populates="scenario",
        order_by="AnalysisResult.run_at.desc()",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )

    @property
    def entity_ids(self) -> list[str]:
        return json.loads(self.entity_ids_json)

    @entity_ids.setter
    def entity_ids(self, value: list[str]) -> None:
        self.entity_ids_json = json.dumps(value)

    @property
    def last_result(self) -> AnalysisResult | None:
        return self.results.first()

    def __repr__(self) -> str:
        return f"<Scenario {self.id} {self.name!r}>"

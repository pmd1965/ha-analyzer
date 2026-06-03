from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.scenario import Scenario


class AnalysisResult(db.Model):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )

    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # "scheduled" | "manual" | "api"
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    # Raw LLM response (full JSON string)
    llm_response: Mapped[str] = mapped_column(Text, nullable=False)

    anomaly_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Parsed severity from LLM JSON: "none" | "low" | "medium" | "high"
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="none")

    # Short summary extracted from LLM JSON
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Formatted entity data that was sent to the LLM (truncated to 4000 chars for storage)
    data_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notification_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    scenario: Mapped[Scenario] = relationship("Scenario", back_populates="results")

    def __repr__(self) -> str:
        return f"<AnalysisResult {self.id} scenario={self.scenario_id} anomaly={self.anomaly_detected}>"

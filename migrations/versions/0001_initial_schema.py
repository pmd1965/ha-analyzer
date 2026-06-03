"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("entity_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("time_window_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("aggregate_window", sa.String(10), nullable=False, server_default="30m"),
        sa.Column("prompt_template", sa.Text(), nullable=False, server_default=""),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("alert_on_anomaly", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("llm_response", sa.Text(), nullable=False),
        sa.Column("anomaly_detected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("severity", sa.String(10), nullable=False, server_default="none"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("data_snapshot", sa.Text(), nullable=True),
        sa.Column("notification_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notification_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_results_scenario_id", "analysis_results", ["scenario_id"])
    op.create_index("ix_analysis_results_run_at", "analysis_results", ["run_at"])


def downgrade():
    op.drop_index("ix_analysis_results_run_at", "analysis_results")
    op.drop_index("ix_analysis_results_scenario_id", "analysis_results")
    op.drop_table("analysis_results")
    op.drop_table("scenarios")

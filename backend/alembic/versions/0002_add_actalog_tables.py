"""add actalog tables

Revision ID: 0002_add_actalog_tables
Revises: 0c196bca2dc0
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_actalog_tables"
down_revision = "0c196bca2dc0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "actalog_workouts",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("workout_date", sa.DateTime(), nullable=True),
        sa.Column("workout_name", sa.Text(), nullable=True),
        sa.Column("workout_type", sa.String(32), nullable=True),
        sa.Column("total_time_s", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_actalog_workouts_date", "actalog_workouts", ["workout_date"])

    op.create_table(
        "actalog_movements",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("movement_type", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "actalog_wods",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("regime", sa.String(64), nullable=True),
        sa.Column("score_type", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "actalog_workout_movements",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("workout_id", sa.Integer(), sa.ForeignKey("actalog_workouts.id"), nullable=True),
        sa.Column("movement_id", sa.Integer(), sa.ForeignKey("actalog_movements.id"), nullable=True),
        sa.Column("sets", sa.Integer(), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("time_s", sa.Integer(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("rpe", sa.Integer(), nullable=True),
        sa.Column("is_pr", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("order_index", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_actalog_wm_workout", "actalog_workout_movements", ["workout_id"])
    op.create_index("ix_actalog_wm_movement", "actalog_workout_movements", ["movement_id"])

    op.create_table(
        "actalog_workout_wods",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("workout_id", sa.Integer(), sa.ForeignKey("actalog_workouts.id"), nullable=True),
        sa.Column("wod_id", sa.Integer(), sa.ForeignKey("actalog_wods.id"), nullable=True),
        sa.Column("score_value", sa.Text(), nullable=True),
        sa.Column("time_s", sa.Integer(), nullable=True),
        sa.Column("rounds", sa.Integer(), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("rpe", sa.Integer(), nullable=True),
        sa.Column("is_pr", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("order_index", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_actalog_ww_workout", "actalog_workout_wods", ["workout_id"])

    op.create_table(
        "actalog_personal_records",
        sa.Column("movement_id", sa.Integer(), sa.ForeignKey("actalog_movements.id"), nullable=False),
        sa.Column("max_weight_kg", sa.Float(), nullable=True),
        sa.Column("max_reps", sa.Integer(), nullable=True),
        sa.Column("best_time_s", sa.Integer(), nullable=True),
        sa.Column("workout_id", sa.Integer(), sa.ForeignKey("actalog_workouts.id"), nullable=True),
        sa.Column("workout_date", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("movement_id"),
    )


def downgrade() -> None:
    op.drop_table("actalog_personal_records")
    op.drop_index("ix_actalog_ww_workout", "actalog_workout_wods")
    op.drop_table("actalog_workout_wods")
    op.drop_index("ix_actalog_wm_movement", "actalog_workout_movements")
    op.drop_index("ix_actalog_wm_workout", "actalog_workout_movements")
    op.drop_table("actalog_workout_movements")
    op.drop_table("actalog_wods")
    op.drop_table("actalog_movements")
    op.drop_index("ix_actalog_workouts_date", "actalog_workouts")
    op.drop_table("actalog_workouts")

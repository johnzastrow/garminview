"""add daily_hr_zones table

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = :tname"
        ),
        {"tname": table_name},
    )
    return result.scalar() > 0


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "daily_hr_zones"):
        return
    op.create_table(
        "daily_hr_zones",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("z1_min", sa.SmallInteger(), nullable=True),
        sa.Column("z2_min", sa.SmallInteger(), nullable=True),
        sa.Column("z3_min", sa.SmallInteger(), nullable=True),
        sa.Column("z4_min", sa.SmallInteger(), nullable=True),
        sa.Column("z5_min", sa.SmallInteger(), nullable=True),
        sa.Column("valid_max_hr", sa.SmallInteger(), nullable=True),
        sa.Column("raw_max_hr", sa.SmallInteger(), nullable=True),
        sa.Column("rejected_count", sa.SmallInteger(), nullable=True),
        sa.Column("total_count", sa.SmallInteger(), nullable=True),
        sa.Column("zone_method", sa.String(20), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("date"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "daily_hr_zones"):
        op.drop_table("daily_hr_zones")

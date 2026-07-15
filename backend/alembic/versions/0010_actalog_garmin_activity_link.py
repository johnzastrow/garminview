"""link actalog workouts to garmin activities for HR lookup

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0010'
down_revision: Union[str, Sequence[str], None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Link column — points at activities.activity_id (BigInteger).
    op.add_column(
        'actalog_workouts',
        sa.Column('garmin_activity_id', sa.BigInteger, nullable=True),
    )
    # Flag distinguishing "user reviewed and chose" (True) from
    # "never reviewed, auto-match still live" (False). When True and
    # garmin_activity_id is NULL, the user confirmed no Garmin activity
    # was recorded for this workout.
    op.add_column(
        'actalog_workouts',
        sa.Column(
            'garmin_match_confirmed',
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column('actalog_workouts', 'garmin_match_confirmed')
    op.drop_column('actalog_workouts', 'garmin_activity_id')

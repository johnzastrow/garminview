"""add source column to sleep, resting_heart_rate, vo2max

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0009'
down_revision: Union[str, Sequence[str], None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sleep', sa.Column('source', sa.String(32)))
    op.add_column('resting_heart_rate', sa.Column('source', sa.String(32)))
    op.add_column('vo2max', sa.Column('source', sa.String(32)))


def downgrade() -> None:
    op.drop_column('vo2max', 'source')
    op.drop_column('resting_heart_rate', 'source')
    op.drop_column('sleep', 'source')

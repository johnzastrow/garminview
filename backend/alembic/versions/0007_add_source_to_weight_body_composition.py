"""add source column to weight and body_composition

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-07
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('weight',
        sa.Column('source', sa.String(16), nullable=True, server_default='garmin'))
    op.execute("UPDATE weight SET source = 'garmin' WHERE source IS NULL")

    op.add_column('body_composition',
        sa.Column('source', sa.String(16), nullable=True, server_default='garmin'))
    op.execute("UPDATE body_composition SET source = 'garmin' WHERE source IS NULL")


def downgrade() -> None:
    op.drop_column('weight', 'source')
    op.drop_column('body_composition', 'source')

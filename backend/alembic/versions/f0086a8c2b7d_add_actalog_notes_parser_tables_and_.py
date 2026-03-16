"""add actalog notes parser tables and columns

Revision ID: f0086a8c2b7d
Revises: 0002_add_actalog_tables
Create Date: 2026-03-16 10:43:16.109082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f0086a8c2b7d'
down_revision: Union[str, Sequence[str], None] = '0002_add_actalog_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # actalog_workouts — formatted and performance notes fields
    op.add_column('actalog_workouts', sa.Column('formatted_notes', sa.Text(), nullable=True))
    op.add_column('actalog_workouts', sa.Column('performance_notes', sa.Text(), nullable=True))

    # actalog_wods — dual-name support
    op.add_column('actalog_wods', sa.Column('alt_name', sa.Text(), nullable=True))
    op.add_column('actalog_wods', sa.Column('name_source', sa.String(length=16), nullable=True))

    # actalog_note_parses — LLM parse staging table
    op.create_table(
        'actalog_note_parses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workout_id', sa.Integer(), nullable=True),
        sa.Column('content_class', sa.String(length=32), nullable=True),
        sa.Column('raw_notes', sa.Text(), nullable=True),
        sa.Column('parsed_json', sa.Text(), nullable=True),
        sa.Column('parse_status', sa.String(length=16), nullable=True),
        sa.Column('parsed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('llm_model', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['workout_id'], ['actalog_workouts.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('actalog_note_parses')
    op.drop_column('actalog_wods', 'name_source')
    op.drop_column('actalog_wods', 'alt_name')
    op.drop_column('actalog_workouts', 'performance_notes')
    op.drop_column('actalog_workouts', 'formatted_notes')

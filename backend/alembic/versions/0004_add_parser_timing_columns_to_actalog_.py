"""add parser timing columns to actalog_note_parses

Revision ID: 0004
Revises: f0086a8c2b7d
Create Date: 2026-03-16 16:25:16.055234

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = 'f0086a8c2b7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("actalog_note_parses", sa.Column("parse_duration_s", sa.Float(), nullable=True))
    op.add_column("actalog_note_parses", sa.Column("llm_tokens_prompt", sa.Integer(), nullable=True))
    op.add_column("actalog_note_parses", sa.Column("llm_tokens_generated", sa.Integer(), nullable=True))
    op.add_column("actalog_note_parses", sa.Column("llm_inference_s", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("actalog_note_parses", "llm_inference_s")
    op.drop_column("actalog_note_parses", "llm_tokens_generated")
    op.drop_column("actalog_note_parses", "llm_tokens_prompt")
    op.drop_column("actalog_note_parses", "parse_duration_s")

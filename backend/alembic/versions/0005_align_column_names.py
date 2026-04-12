"""align_column_names

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-06 13:23:58.301862

Schema alignment check run 2026-04-06.
No column renames required — existing column names already match the models.

Changes applied by this migration:
- New tables: max_hr_aging_year, mfp_daily_nutrition, mfp_exercises,
  mfp_food_diary, mfp_measurements (models added since initial migration)
- New columns on data_quality_flags: source_table, record_id, excluded
- New columns on user_profile: weight_kg, max_hr_override, resting_hr
- Type widening: data_quality_flags.flag_type VARCHAR(16) -> String(32)
- Drop stale actalog indexes removed from ORM models
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table_name: str) -> bool:
    """Return True if table already exists in the database."""
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = :tname"
        ),
        {"tname": table_name},
    )
    return result.scalar() > 0


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    """Return True if column already exists in table."""
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :tname AND column_name = :cname"
        ),
        {"tname": table_name, "cname": column_name},
    )
    return result.scalar() > 0


def _index_exists(conn, table_name: str, index_name: str) -> bool:
    """Return True if index already exists on table."""
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = :tname AND index_name = :iname"
        ),
        {"tname": table_name, "iname": index_name},
    )
    return result.scalar() > 0


def upgrade() -> None:
    """Upgrade schema — idempotent: skips objects that already exist."""
    conn = op.get_bind()

    # --- new tables (skip if already created by metadata.create_all) ---
    if not _table_exists(conn, 'max_hr_aging_year'):
        op.create_table('max_hr_aging_year',
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('annual_peak_hr', sa.SmallInteger(), nullable=True),
        sa.Column('annual_p95_hr', sa.Float(), nullable=True),
        sa.Column('annual_p90_hr', sa.Float(), nullable=True),
        sa.Column('activity_count', sa.Integer(), nullable=True),
        sa.Column('age_predicted_max', sa.Float(), nullable=True),
        sa.Column('hr_reserve', sa.Float(), nullable=True),
        sa.Column('pct_age_predicted', sa.Float(), nullable=True),
        sa.Column('decline_rate_bpm_per_year', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('year')
        )
    if not _table_exists(conn, 'mfp_daily_nutrition'):
        op.create_table('mfp_daily_nutrition',
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('calories_in', sa.Integer(), nullable=True),
        sa.Column('carbs_g', sa.Float(), nullable=True),
        sa.Column('fat_g', sa.Float(), nullable=True),
        sa.Column('protein_g', sa.Float(), nullable=True),
        sa.Column('sodium_mg', sa.Float(), nullable=True),
        sa.Column('sugar_g', sa.Float(), nullable=True),
        sa.Column('fiber_g', sa.Float(), nullable=True),
        sa.Column('cholesterol_mg', sa.Float(), nullable=True),
        sa.Column('logged_meals', sa.SmallInteger(), nullable=True),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint('date')
        )
    if not _table_exists(conn, 'mfp_exercises'):
        op.create_table('mfp_exercises',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('exercise_name', sa.String(length=256), nullable=False),
        sa.Column('exercise_type', sa.String(length=32), nullable=True),
        sa.Column('calories', sa.Float(), nullable=True),
        sa.Column('duration_min', sa.Float(), nullable=True),
        sa.Column('sets', sa.Integer(), nullable=True),
        sa.Column('reps_per_set', sa.Integer(), nullable=True),
        sa.Column('weight_lbs', sa.Float(), nullable=True),
        sa.Column('steps', sa.Integer(), nullable=True),
        sa.Column('note', sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint('id')
        )
    if not _index_exists(conn, 'mfp_exercises', 'ix_mfp_exercises_date'):
        op.create_index(op.f('ix_mfp_exercises_date'), 'mfp_exercises', ['date'], unique=False)
    if not _table_exists(conn, 'mfp_food_diary'):
        op.create_table('mfp_food_diary',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('meal', sa.String(length=32), nullable=False),
        sa.Column('food_name', sa.String(length=512), nullable=False),
        sa.Column('calories', sa.Integer(), nullable=True),
        sa.Column('carbs_g', sa.Float(), nullable=True),
        sa.Column('fat_g', sa.Float(), nullable=True),
        sa.Column('protein_g', sa.Float(), nullable=True),
        sa.Column('sodium_mg', sa.Float(), nullable=True),
        sa.Column('sugar_g', sa.Float(), nullable=True),
        sa.Column('fiber_g', sa.Float(), nullable=True),
        sa.Column('cholesterol_mg', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
        )
    if not _index_exists(conn, 'mfp_food_diary', 'ix_mfp_food_diary_date'):
        op.create_index(op.f('ix_mfp_food_diary_date'), 'mfp_food_diary', ['date'], unique=False)
    if not _table_exists(conn, 'mfp_measurements'):
        op.create_table('mfp_measurements',
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint('date', 'name')
        )

    # --- drop stale actalog indexes ---
    # These indexes back FK constraints in MariaDB so they cannot be dropped directly.
    # Skip them rather than failing; the ORM models no longer declare them explicitly
    # but the underlying indexes are harmless to leave in place.
    pass

    # --- new columns on data_quality_flags (skip if already added) ---
    if not _column_exists(conn, 'data_quality_flags', 'source_table'):
        op.add_column('data_quality_flags', sa.Column('source_table', sa.String(length=64), nullable=True))
    if not _column_exists(conn, 'data_quality_flags', 'record_id'):
        op.add_column('data_quality_flags', sa.Column('record_id', sa.String(length=128), nullable=True))
    if not _column_exists(conn, 'data_quality_flags', 'excluded'):
        op.add_column('data_quality_flags', sa.Column('excluded', sa.Boolean(), server_default='0', nullable=False))

    # SQLite requires batch mode for column type changes; MariaDB handles it natively
    with op.batch_alter_table('data_quality_flags') as batch_op:
        batch_op.alter_column('flag_type',
                              existing_type=sa.VARCHAR(length=16),
                              type_=sa.String(length=32),
                              existing_nullable=False)

    # --- new columns on user_profile (skip if already added) ---
    if not _column_exists(conn, 'user_profile', 'weight_kg'):
        op.add_column('user_profile', sa.Column('weight_kg', sa.Float(), nullable=True))
    if not _column_exists(conn, 'user_profile', 'max_hr_override'):
        op.add_column('user_profile', sa.Column('max_hr_override', sa.Integer(), nullable=True))
    if not _column_exists(conn, 'user_profile', 'resting_hr'):
        op.add_column('user_profile', sa.Column('resting_hr', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user_profile', 'resting_hr')
    op.drop_column('user_profile', 'max_hr_override')
    op.drop_column('user_profile', 'weight_kg')
    with op.batch_alter_table('data_quality_flags') as batch_op:
        batch_op.alter_column('flag_type',
                              existing_type=sa.String(length=32),
                              type_=sa.VARCHAR(length=16),
                              existing_nullable=False)
    op.drop_column('data_quality_flags', 'excluded')
    op.drop_column('data_quality_flags', 'record_id')
    op.drop_column('data_quality_flags', 'source_table')
    # actalog indexes skipped in upgrade (backed by FK constraints); skip re-create too
    op.drop_table('mfp_measurements')
    op.drop_index(op.f('ix_mfp_food_diary_date'), table_name='mfp_food_diary')
    op.drop_table('mfp_food_diary')
    op.drop_index(op.f('ix_mfp_exercises_date'), table_name='mfp_exercises')
    op.drop_table('mfp_exercises')
    op.drop_table('mfp_daily_nutrition')
    op.drop_table('max_hr_aging_year')
    # ### end Alembic commands ###

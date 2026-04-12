"""add polar staging tables (26 tables for Polar Flow GDPR export)

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# MEDIUMTEXT on MariaDB (16MB), plain TEXT on SQLite (unlimited)
_LT = sa.Text(2**24)


def upgrade() -> None:
    # ── Training sessions ──
    op.create_table(
        'polar_training_sessions',
        sa.Column('session_id', sa.String(64), primary_key=True),
        sa.Column('created', sa.DateTime),
        sa.Column('modified', sa.DateTime),
        sa.Column('start_time', sa.DateTime),
        sa.Column('stop_time', sa.DateTime),
        sa.Column('name', sa.String(256)),
        sa.Column('sport_id', sa.String(64)),
        sa.Column('device_id', sa.String(64)),
        sa.Column('device_model', sa.String(128)),
        sa.Column('app_name', sa.String(128)),
        sa.Column('latitude', sa.Float),
        sa.Column('longitude', sa.Float),
        sa.Column('duration_ms', sa.BigInteger),
        sa.Column('distance_m', sa.Float),
        sa.Column('calories', sa.Integer),
        sa.Column('training_load', sa.Float),
        sa.Column('recovery_time_ms', sa.BigInteger),
        sa.Column('tz_offset_min', sa.Integer),
        sa.Column('max_hr', sa.Integer),
        sa.Column('resting_hr', sa.Integer),
        sa.Column('aerobic_threshold', sa.Integer),
        sa.Column('anaerobic_threshold', sa.Integer),
        sa.Column('vo2max', sa.Float),
        sa.Column('weight_kg', sa.Float),
        sa.Column('source_file', sa.String(256)),
        sa.Column('imported_at', sa.DateTime),
    )

    op.create_table(
        'polar_exercises',
        sa.Column('exercise_id', sa.String(64), primary_key=True),
        sa.Column('session_id', sa.String(64), index=True),
        sa.Column('exercise_index', sa.Integer),
        sa.Column('start_time', sa.DateTime),
        sa.Column('stop_time', sa.DateTime),
        sa.Column('duration_ms', sa.BigInteger),
        sa.Column('distance_m', sa.Float),
        sa.Column('calories', sa.Integer),
        sa.Column('training_load', sa.Float),
        sa.Column('recovery_time_ms', sa.BigInteger),
        sa.Column('sport_id', sa.String(64)),
        sa.Column('latitude', sa.Float),
        sa.Column('longitude', sa.Float),
        sa.Column('tz_offset_min', sa.Integer),
    )

    op.create_table(
        'polar_exercise_statistics',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('exercise_id', sa.String(64), index=True),
        sa.Column('stat_type', sa.String(64)),
        sa.Column('avg', sa.Float),
        sa.Column('max', sa.Float),
    )

    op.create_table(
        'polar_exercise_zones',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('exercise_id', sa.String(64), index=True),
        sa.Column('zone_type', sa.String(64)),
        sa.Column('zone_index', sa.Integer),
        sa.Column('lower_limit', sa.Float),
        sa.Column('higher_limit', sa.Float),
    )

    op.create_table(
        'polar_exercise_laps',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('exercise_id', sa.String(64), index=True),
        sa.Column('lap_index', sa.Integer),
        sa.Column('raw_json', _LT),
    )

    op.create_table(
        'polar_exercise_samples',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('exercise_id', sa.String(64), index=True),
        sa.Column('sample_type', sa.String(32)),
        sa.Column('interval_ms', sa.Integer),
        sa.Column('values_json', _LT),
        sa.UniqueConstraint('exercise_id', 'sample_type', name='uq_polar_ex_sample'),
    )

    op.create_table(
        'polar_exercise_routes',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('exercise_id', sa.String(64), index=True),
        sa.Column('route_type', sa.String(16)),
        sa.Column('start_time', sa.DateTime),
        sa.Column('waypoints_json', _LT),
        sa.UniqueConstraint('exercise_id', 'route_type', name='uq_polar_ex_route'),
    )

    # ── Daily activities ──
    op.create_table(
        'polar_activities',
        sa.Column('date', sa.Date, primary_key=True),
        sa.Column('export_version', sa.String(16)),
        sa.Column('source_file', sa.String(256)),
        sa.Column('imported_at', sa.DateTime),
    )

    op.create_table(
        'polar_activity_samples',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date, index=True),
        sa.Column('sample_type', sa.String(16)),
        sa.Column('values_json', _LT),
        sa.UniqueConstraint('date', 'sample_type', name='uq_polar_act_sample'),
    )

    op.create_table(
        'polar_activity_met_sources',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date, index=True),
        sa.Column('source_index', sa.Integer),
        sa.Column('source_name', sa.String(128)),
    )

    op.create_table(
        'polar_activity_physical_info',
        sa.Column('date', sa.Date, primary_key=True),
        sa.Column('sex', sa.String(16)),
        sa.Column('birthday', sa.Date),
        sa.Column('height_cm', sa.Float),
        sa.Column('weight_kg', sa.Float),
    )

    # ── Sleep ──
    op.create_table(
        'polar_sleep',
        sa.Column('night', sa.Date, primary_key=True),
        sa.Column('sleep_type', sa.String(32)),
        sa.Column('sleep_span', sa.String(32)),
        sa.Column('asleep_duration', sa.String(32)),
        sa.Column('age', sa.Integer),
        sa.Column('efficiency_pct', sa.Float),
        sa.Column('continuity_index', sa.Float),
        sa.Column('continuity_class', sa.Integer),
        sa.Column('feedback', sa.Integer),
        sa.Column('interruption_total_dur', sa.String(32)),
        sa.Column('interruption_total_count', sa.Integer),
        sa.Column('interruption_short_count', sa.Integer),
        sa.Column('interruption_long_count', sa.Integer),
        sa.Column('sleep_start', sa.DateTime),
        sa.Column('sleep_end', sa.DateTime),
        sa.Column('sleep_goal', sa.String(32)),
        sa.Column('rating', sa.String(32)),
        sa.Column('device_id', sa.String(64)),
        sa.Column('battery_ran_out', sa.Boolean),
        sa.Column('source_file', sa.String(256)),
        sa.Column('imported_at', sa.DateTime),
    )

    op.create_table(
        'polar_sleep_states',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('night', sa.Date, index=True),
        sa.Column('state_index', sa.Integer),
        sa.Column('offset_from_start', sa.String(32)),
        sa.Column('state', sa.String(16)),
    )

    # ── 24/7 OHR ──
    op.create_table(
        'polar_247ohr',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('date', sa.Date, index=True),
        sa.Column('device_id', sa.String(64)),
        sa.Column('user_id', sa.Integer),
        sa.Column('samples_json', _LT),
        sa.Column('source_file', sa.String(256)),
        sa.Column('imported_at', sa.DateTime),
        sa.UniqueConstraint('date', 'device_id', name='uq_polar_247ohr'),
    )

    # ── Fitness tests ──
    op.create_table(
        'polar_fitness_tests',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('created', sa.DateTime),
        sa.Column('start_time', sa.DateTime),
        sa.Column('own_index', sa.Float),
        sa.Column('avg_hr', sa.Integer),
        sa.Column('fitness_class', sa.String(32)),
        sa.Column('tz_offset_min', sa.Integer),
        sa.Column('weight_kg', sa.Float),
        sa.Column('vo2max', sa.Float),
        sa.Column('source_file', sa.String(256)),
        sa.Column('imported_at', sa.DateTime),
    )

    # ── Training targets ──
    op.create_table(
        'polar_training_targets',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('start_time', sa.DateTime),
        sa.Column('name', sa.String(256)),
        sa.Column('description', sa.Text),
        sa.Column('done', sa.Boolean),
        sa.Column('program_ref', sa.Integer),
        sa.Column('non_user_editable', sa.Boolean),
        sa.Column('source_file', sa.String(256)),
        sa.Column('imported_at', sa.DateTime),
    )

    op.create_table(
        'polar_training_target_phases',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('target_id', sa.Integer, index=True),
        sa.Column('exercise_index', sa.Integer),
        sa.Column('sport', sa.String(64)),
        sa.Column('phase_index', sa.Integer),
        sa.Column('phase_name', sa.String(128)),
        sa.Column('change_type', sa.String(32)),
        sa.Column('goal_type', sa.String(32)),
        sa.Column('goal_duration', sa.String(32)),
        sa.Column('intensity_type', sa.String(32)),
        sa.Column('intensity_upper_zone', sa.Integer),
        sa.Column('intensity_lower_zone', sa.Integer),
    )

    # ── Account ──
    op.create_table(
        'polar_account',
        sa.Column('user_id', sa.Integer, primary_key=True),
        sa.Column('username', sa.String(256)),
        sa.Column('first_name', sa.String(128)),
        sa.Column('last_name', sa.String(128)),
        sa.Column('nickname', sa.String(128)),
        sa.Column('sex', sa.String(16)),
        sa.Column('birthday', sa.Date),
        sa.Column('height_cm', sa.Float),
        sa.Column('weight_kg', sa.Float),
        sa.Column('vo2max', sa.Float),
        sa.Column('resting_hr', sa.Integer),
        sa.Column('sleep_goal', sa.String(32)),
        sa.Column('timezone', sa.String(64)),
        sa.Column('settings_json', sa.Text),
        sa.Column('linked_apps_json', sa.Text),
        sa.Column('motto', sa.String(256)),
        sa.Column('phone', sa.String(32)),
        sa.Column('country_code', sa.String(8)),
        sa.Column('city', sa.String(128)),
        sa.Column('favourite_sports_json', sa.Text),
        sa.Column('source_file', sa.String(256)),
        sa.Column('imported_at', sa.DateTime),
    )

    # ── Catch-all JSON blob tables ──
    op.create_table(
        'polar_devices',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('raw_json', _LT),
        sa.Column('source_file', sa.String(256)),
        sa.Column('imported_at', sa.DateTime),
    )

    op.create_table(
        'polar_sport_profiles',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('sport', sa.String(64)),
        sa.Column('raw_json', _LT),
        sa.Column('source_file', sa.String(256)),
        sa.Column('imported_at', sa.DateTime),
    )

    op.create_table(
        'polar_calendar_items',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('datetime', sa.DateTime),
        sa.Column('height_cm', sa.Float),
        sa.Column('weight_kg', sa.Float),
        sa.Column('vo2max', sa.Float),
        sa.Column('max_hr', sa.Integer),
        sa.Column('resting_hr', sa.Integer),
        sa.Column('aerobic_threshold', sa.Integer),
        sa.Column('anaerobic_threshold', sa.Integer),
        sa.Column('ftp', sa.Integer),
        sa.Column('training_background', sa.String(32)),
        sa.Column('typical_day', sa.String(32)),
    )

    op.create_table(
        'polar_programs',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('program_type', sa.String(64)),
        sa.Column('raw_json', _LT),
        sa.Column('source_file', sa.String(256)),
        sa.Column('imported_at', sa.DateTime),
    )

    op.create_table(
        'polar_planned_routes',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('raw_json', _LT),
        sa.Column('source_file', sa.String(256)),
        sa.Column('imported_at', sa.DateTime),
    )

    op.create_table(
        'polar_favourite_targets',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('raw_json', _LT),
        sa.Column('source_file', sa.String(256)),
        sa.Column('imported_at', sa.DateTime),
    )

    # ── Import tracking ──
    op.create_table(
        'polar_import_log',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('started_at', sa.DateTime),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('source_path', sa.String(512)),
        sa.Column('files_found', sa.Integer),
        sa.Column('files_imported', sa.Integer),
        sa.Column('files_skipped', sa.Integer),
        sa.Column('files_errored', sa.Integer),
        sa.Column('status', sa.String(16)),
        sa.Column('error_detail', sa.Text),
    )

    op.create_table(
        'polar_import_files',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('import_id', sa.Integer, index=True),
        sa.Column('filename', sa.String(256)),
        sa.Column('file_type', sa.String(64)),
        sa.Column('file_size_bytes', sa.Integer),
        sa.Column('status', sa.String(16)),
        sa.Column('records_upserted', sa.Integer),
        sa.Column('error_detail', sa.Text),
        sa.Column('processed_at', sa.DateTime),
    )


def downgrade() -> None:
    tables = [
        'polar_import_files', 'polar_import_log',
        'polar_favourite_targets', 'polar_planned_routes', 'polar_programs',
        'polar_calendar_items', 'polar_sport_profiles', 'polar_devices',
        'polar_account',
        'polar_training_target_phases', 'polar_training_targets',
        'polar_fitness_tests',
        'polar_247ohr',
        'polar_sleep_states', 'polar_sleep',
        'polar_activity_physical_info', 'polar_activity_met_sources',
        'polar_activity_samples', 'polar_activities',
        'polar_exercise_routes', 'polar_exercise_samples',
        'polar_exercise_laps', 'polar_exercise_zones',
        'polar_exercise_statistics', 'polar_exercises',
        'polar_training_sessions',
    ]
    for t in tables:
        op.drop_table(t)

def test_all_tables_created(engine):
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "daily_summary" in tables
    assert "sleep" in tables
    assert "activities" in tables
    assert "hrv_data" in tables
    assert "body_composition" in tables


def test_derived_and_config_tables(engine):
    from sqlalchemy import inspect
    tables = inspect(engine).get_table_names()
    for t in ["daily_derived", "goals", "assessments", "app_config",
              "sync_schedule", "sync_log", "schema_version", "user_profile"]:
        assert t in tables, f"Missing table: {t}"

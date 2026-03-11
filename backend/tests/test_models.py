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


def test_mfp_exercise_model(session):
    from garminview.models.nutrition import MFPExercise
    from datetime import date
    ex = MFPExercise(
        date=date(2024, 1, 15),
        exercise_name="Running",
        exercise_type="Cardio",
        calories=350.0,
        duration_min=30.0,
    )
    session.add(ex)
    session.commit()
    row = session.get(MFPExercise, ex.id)
    assert row.exercise_name == "Running"
    assert row.duration_min == 30.0


def test_mfp_food_diary_extended_columns(session):
    from garminview.models.nutrition import MFPFoodDiaryEntry
    from datetime import date
    entry = MFPFoodDiaryEntry(
        date=date(2024, 1, 15),
        meal="Breakfast",
        food_name="Breakfast before 8a",
        calories=450,
        carbs_g=55.0,
        fat_g=12.0,
        protein_g=22.0,
        sodium_mg=800.0,
        sugar_g=18.0,
        fiber_g=6.0,
        cholesterol_mg=95.0,
    )
    session.add(entry)
    session.commit()
    row = session.query(MFPFoodDiaryEntry).filter_by(id=entry.id).one()
    assert row.sodium_mg == 800.0
    assert row.fiber_g == 6.0

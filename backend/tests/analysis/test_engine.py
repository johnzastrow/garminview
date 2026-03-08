def test_engine_runs_without_data(session):
    from garminview.analysis.engine import AnalysisEngine
    engine = AnalysisEngine(session)
    engine.run_all()  # must not raise with empty DB

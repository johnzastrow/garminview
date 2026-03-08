def test_orchestrator_runs_file_adapters(session, tmp_path, monkeypatch):
    from garminview.ingestion.orchestrator import IngestionOrchestrator
    from datetime import date

    orch = IngestionOrchestrator(session=session, health_data_dir=tmp_path)
    # Should not raise even with empty data dir
    orch.run_incremental()
    from garminview.models.sync import SyncLog
    logs = session.query(SyncLog).all()
    assert len(logs) > 0

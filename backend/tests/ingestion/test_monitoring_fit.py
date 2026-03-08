def test_monitoring_fit_adapter_interface():
    from garminview.ingestion.file_adapters.monitoring_fit import MonitoringFitAdapter
    adapter = MonitoringFitAdapter(data_dir="/tmp/nonexistent")
    assert adapter.source_name() == "garmin_files:monitoring_fit"
    assert adapter.target_table() == "monitoring_heart_rate"

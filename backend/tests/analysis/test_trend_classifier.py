def test_classify_improving_trend():
    from garminview.analysis.assessments.trend_classifier import classify_trend
    import datetime
    series = [62, 61, 60, 59, 58, 57, 56, 55, 54, 53, 52, 51, 50, 49]
    dates = [datetime.date(2026, 1, i+1) for i in range(len(series))]
    result = classify_trend(dates, series, lower_is_better=True)
    assert result.direction == "improving"
    assert result.p_value < 0.05


def test_insufficient_data():
    from garminview.analysis.assessments.trend_classifier import classify_trend
    import datetime
    dates = [datetime.date(2026, 1, i+1) for i in range(3)]
    result = classify_trend(dates, [50, 51, 50], lower_is_better=False)
    assert result.direction == "insufficient_data"

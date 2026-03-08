def test_sleep_efficiency():
    from garminview.analysis.metrics.sleep_science import calc_sleep_efficiency
    eff = calc_sleep_efficiency(total_sleep_min=420, awake_min=30, time_in_bed_min=480)
    assert abs(eff - 87.5) < 0.1


def test_sleep_debt_positive():
    from garminview.analysis.metrics.sleep_science import calc_sleep_debt
    actual = [6.5, 7.0, 6.0, 7.5, 6.5, 7.0, 6.0]
    debt = calc_sleep_debt(actual_hours=actual, target_hours=8.0)
    assert debt > 0


def test_social_jet_lag():
    from garminview.analysis.metrics.sleep_science import calc_social_jet_lag
    weekday_mids = [2.0, 2.5, 2.0, 2.5, 2.0]
    weekend_mids = [4.0, 4.5]
    sjl = calc_social_jet_lag(weekday_mids, weekend_mids)
    assert abs(sjl - 2.0) < 0.5

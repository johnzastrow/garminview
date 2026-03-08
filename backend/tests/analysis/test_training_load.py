from garminview.analysis.metrics.training_load import calc_trimp, calc_ewma_series


def test_trimp_calculation():
    result = calc_trimp(duration_min=60, avg_hr=150, max_hr=190)
    assert 80 < result < 200  # Banister TRIMP with hr_fraction ~0.71


def test_ewma_series():
    loads = [100, 80, 120, 90, 110, 95, 105]
    atl = calc_ewma_series(loads, tau=7)
    assert len(atl) == len(loads)
    assert atl[-1] > 0
    assert min(loads) * 0.5 < atl[-1] < max(loads) * 1.5


def test_acwr_in_safe_zone():
    from garminview.analysis.metrics.training_load import calc_acwr
    atl, ctl = 80.0, 90.0
    acwr = calc_acwr(atl, ctl)
    assert 0.85 < acwr < 0.95

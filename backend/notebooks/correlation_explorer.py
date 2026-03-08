# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "altair>=5.0.0",
#     "pandas>=2.0.0",
#     "scipy>=1.10.0",
#     "garminview",
# ]
# ///

import marimo

__generated_with = "0.10.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    is_script_mode = mo.app_meta().mode == "script"
    return (is_script_mode,)


@app.cell
def _(mo):
    mo.md("## Correlation Explorer — any two metrics, scatter + regression")
    return


@app.cell
def _(mo):
    from datetime import date, timedelta
    date_range = mo.ui.date_range(
        start=date.today() - timedelta(days=180),
        stop=date.today(),
        label="Date Range",
    )
    return date, date_range, timedelta


@app.cell
def _(mo):
    _metrics = ["steps", "hr_resting", "stress_avg", "sleep_score",
                "body_battery_max", "spo2_avg", "atl", "ctl", "tsb"]
    x_metric = mo.ui.dropdown(_metrics, value="steps", label="X Metric")
    y_metric = mo.ui.dropdown(_metrics, value="hr_resting", label="Y Metric")
    return x_metric, y_metric


@app.cell
def _(date_range, mo, x_metric, y_metric):
    mo.hstack([date_range, x_metric, y_metric])
    return


@app.cell
def _(date_range, is_script_mode, timedelta):
    from datetime import date as _date, timedelta as _timedelta
    if is_script_mode:
        _start = _date.today() - _timedelta(days=180)
        _end = _date.today()
    else:
        _start, _end = date_range.value
    start_date = _start
    end_date = _end
    return end_date, start_date


@app.cell
def _(end_date, start_date):
    import pandas as pd
    from notebooks.shared.db import get_notebook_session
    from notebooks.shared.queries import get_daily_summary_df, get_training_load_df

    _session = get_notebook_session()
    _summary = get_daily_summary_df(_session, start_date, end_date)
    _load = get_training_load_df(_session, start_date, end_date)
    _session.close()

    df = _summary.merge(_load, on="date", how="left") if not _summary.empty else _summary
    df
    return df, get_daily_summary_df, get_notebook_session, get_training_load_df, pd


@app.cell
def _(df, x_metric, y_metric):
    import altair as alt
    from scipy import stats

    _x_col = x_metric.value
    _y_col = y_metric.value

    _valid = df[[_x_col, _y_col, "date"]].dropna()

    _scatter = alt.Chart(_valid).mark_circle(size=60, opacity=0.7).encode(
        x=alt.X(f"{_x_col}:Q", title=_x_col),
        y=alt.Y(f"{_y_col}:Q", title=_y_col),
        tooltip=["date:T", f"{_x_col}:Q", f"{_y_col}:Q"],
    )

    _regression = _scatter.transform_regression(
        _x_col, _y_col, method="linear"
    ).mark_line(color="#ef4444")

    _r, _p = stats.pearsonr(_valid[_x_col], _valid[_y_col]) if len(_valid) > 2 else (0, 1)

    chart = alt.layer(_scatter, _regression).properties(
        width=600, height=400,
        title=f"{_x_col} vs {_y_col}  (r={_r:.3f}, p={_p:.4f})"
    )
    chart
    return alt, chart, stats


if __name__ == "__main__":
    app.run()

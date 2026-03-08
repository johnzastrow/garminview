# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "altair>=5.0.0",
#     "pandas>=2.0.0",
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
    mo.md("## Health Explorer")
    return


@app.cell
def _(mo):
    from datetime import date, timedelta
    date_range = mo.ui.date_range(
        start=date.today() - timedelta(days=90),
        stop=date.today(),
        label="Date Range",
    )
    return date, date_range, timedelta


@app.cell
def _(mo):
    metric = mo.ui.dropdown(
        ["steps", "hr_resting", "stress_avg", "sleep_score", "body_battery_max"],
        value="hr_resting",
        label="Metric",
    )
    return (metric,)


@app.cell
def _(date_range, metric, mo):
    mo.hstack([date_range, metric])
    return


@app.cell
def _(date, date_range, is_script_mode, timedelta):
    import pandas as pd
    if is_script_mode:
        from datetime import date as _date, timedelta as _timedelta
        _start = _date.today() - _timedelta(days=90)
        _end = _date.today()
    else:
        _start, _end = date_range.value
    start_date = _start
    end_date = _end
    return pd, end_date, start_date


@app.cell
def _(end_date, pd, start_date):
    from notebooks.shared.db import get_notebook_session
    from notebooks.shared.queries import get_daily_summary_df
    _session = get_notebook_session()
    df = get_daily_summary_df(_session, start_date, end_date)
    _session.close()
    df
    return df, get_daily_summary_df, get_notebook_session


@app.cell
def _(df, metric):
    import altair as alt
    chart = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y(f"{metric.value}:Q", title=metric.value),
        tooltip=["date:T", f"{metric.value}:Q"],
    ).properties(width=700, height=300, title=f"{metric.value} over time")
    chart
    return alt, chart


if __name__ == "__main__":
    app.run()

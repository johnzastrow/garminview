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
    mo.md("## Activity Explorer")
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
    activity_type = mo.ui.dropdown(
        ["running", "cycling", "swimming", "walking", "strength_training"],
        value="running",
        label="Activity Type",
    )
    return (activity_type,)


@app.cell
def _(mo):
    y_axis = mo.ui.dropdown(
        ["avg_hr", "distance", "duration_secs", "avg_speed"],
        value="avg_hr",
        label="Y Axis",
    )
    return (y_axis,)


@app.cell
def _(activity_type, date_range, mo, y_axis):
    mo.hstack([date_range, activity_type, y_axis])
    return


@app.cell
def _(date_range, is_script_mode, timedelta):
    from datetime import date as _date, timedelta as _timedelta
    if is_script_mode:
        _start = _date.today() - _timedelta(days=90)
        _end = _date.today()
    else:
        _start, _end = date_range.value
    start_date = _start
    end_date = _end
    return end_date, start_date


@app.cell
def _(activity_type, end_date, is_script_mode, start_date):
    import pandas as pd
    from notebooks.shared.db import get_notebook_session
    from garminview.models.activities import Activity
    _session = get_notebook_session()
    _query = _session.query(Activity).filter(
        Activity.start_time >= str(start_date),
        Activity.start_time <= str(end_date),
    )
    if not is_script_mode:
        _query = _query.filter(Activity.type == activity_type.value)
    _rows = _query.order_by(Activity.start_time).all()
    df = pd.DataFrame([{
        "date": r.start_time,
        "type": r.type,
        "distance": r.distance,
        "duration_secs": r.duration_secs,
        "avg_hr": r.avg_hr,
        "avg_speed": r.avg_speed,
        "elevation_gain": r.elevation_gain,
    } for r in _rows])
    _session.close()
    df
    return df, get_notebook_session, pd


@app.cell
def _(df, y_axis):
    import altair as alt
    chart = alt.Chart(df).mark_circle(size=60).encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y(f"{y_axis.value}:Q", title=y_axis.value),
        color=alt.Color("type:N"),
        tooltip=["date:T", "type:N", f"{y_axis.value}:Q", "distance:Q"],
    ).properties(width=700, height=350, title="Activity Explorer")
    chart
    return alt, chart


if __name__ == "__main__":
    app.run()

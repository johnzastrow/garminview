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
    mo.md("## Training Load (PMC) — ATL / CTL / TSB")
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
    atl_tau = mo.ui.slider(start=3, stop=14, value=7, label="ATL τ (days)")
    ctl_tau = mo.ui.slider(start=28, stop=60, value=42, label="CTL τ (days)")
    return atl_tau, ctl_tau


@app.cell
def _(atl_tau, ctl_tau, date_range, mo):
    mo.hstack([date_range, atl_tau, ctl_tau])
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
    from notebooks.shared.db import get_notebook_session
    from notebooks.shared.queries import get_training_load_df
    _session = get_notebook_session()
    df = get_training_load_df(_session, start_date, end_date)
    _session.close()
    df
    return df, get_notebook_session, get_training_load_df


@app.cell
def _(df):
    import altair as alt
    import pandas as pd

    _base = alt.Chart(df).encode(x=alt.X("date:T", title="Date"))

    _ctl = _base.mark_line(color="#3b82f6").encode(
        y=alt.Y("ctl:Q", title="Fitness (CTL)"),
        tooltip=["date:T", "ctl:Q"],
    )
    _atl = _base.mark_line(color="#f59e0b").encode(
        y=alt.Y("atl:Q", title="Fatigue (ATL)"),
        tooltip=["date:T", "atl:Q"],
    )
    _tsb = _base.mark_bar(color="#10b981", opacity=0.5).encode(
        y=alt.Y("tsb:Q", title="Form (TSB)"),
        tooltip=["date:T", "tsb:Q"],
    )

    chart = alt.layer(_tsb, _ctl, _atl).resolve_scale(y="independent").properties(
        width=700, height=350, title="Performance Management Chart"
    )
    chart
    return alt, chart, pd


if __name__ == "__main__":
    app.run()

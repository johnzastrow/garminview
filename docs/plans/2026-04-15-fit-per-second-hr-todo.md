# TODO — Per-second HR for Calendar workout charts

**Status:** deferred. UI gap accepted for now. Investigate and fix when
the chart-vs-summary HR mismatch becomes annoying enough.

## Problem

The Calendar tab's per-workout HR chart shows the wrong peak vs. the
matched Garmin activity's `max_hr`. Concrete example from 2026-04-08
"Quick Log Wed, Apr 8, 2026" (workout 294, matched activity
22451624754, hiit, 64 min):

- Activity summary: `avg_hr=107`, **`max_hr=160`**
- Chart peak (rendered from `monitoring_heart_rate`): **148**
- Chart sample count: 62, with intervals of **60-120s**

The 160 spike fell between minute samples and was missed entirely by
the daily monitoring stream. The Activity summary's max came from the
watch's per-second FIT data — accurate, but not in the chart.

## Why it isn't already fixed

The right source for a fine-grained chart is `activity_records.hr`
(per-second). For activity 22451624754 there are zero rows in
`activity_records`, so we have nothing to chart at sub-minute
resolution.

But — and this is the key finding — **FIT files exist on disk**:

- `ls ~/HealthData/FitFiles/Activities/*_ACTIVITY.fit | wc -l` →
  **3,065 files** as of 2026-04-15.
- `Activity` source breakdown: `garmin_api: 1026`, `polar: 674`,
  `garmin_fit: 0`. Yet `activity_records` has rows for ~16,630 distinct
  `activity_id` values, most of which don't correspond to any current
  `Activity` row (orphan records — likely from an old import schema).

So the GarminDB download is fine. The garminview ingestion pipeline
just isn't pulling FIT files into the live DB for new activities.

## Investigation checklist

Work through these in order:

1. **`backend/garminview/ingestion/file_adapters/activity_fit.py`** —
   the `ActivityFitAdapter`. Verify it's actually invoked by the
   orchestrator on each sync. Add a quick log line counting the FIT
   files it sees per run.

2. **`backend/garminview/api/routes/sync.py:55`** — sync calls
   `garmindb_cli.py --all --download --import --latest`. Confirm what
   `--all` actually scopes to (daily monitoring + activities both?
   activity FIT download too?). If `--all` doesn't include activity
   FIT download, find the right flag combo. The CLAUDE.md note bans
   `--analyze` but doesn't prohibit other download scopes.

3. **Orchestrator wiring** — the adapter exists, but is the
   orchestrator scheduling it on the regular sync path? Search for
   `ActivityFitAdapter` usage and see what triggers it. The fact that
   nothing has `source=garmin_fit` strongly suggests the adapter is
   either (a) not being invoked, (b) being invoked but its output not
   marked with that source string, or (c) running in a path where its
   results don't link to existing Activity rows.

4. **Orphan `activity_records`** — explain the 16,630 vs 1,700
   mismatch. Either (a) old activities were pruned from `Activity` but
   not `activity_records`, leaving widows, or (b) the FIT adapter's
   activity_id derivation differs from the one used by the API
   adapter, so per-second records are landing under different ids than
   the summary rows. Hypothesis (b) is suggested by the
   `activity_id = data.get("activity_id") or hash(str(path))` line in
   `activity_fit.py:35` — `hash(str(path))` would generate a totally
   different id than Garmin's real activity_id if the FIT file's
   session message lacks one. Worth verifying.

5. **Once records flow** — switch the session-vitals endpoint to
   prefer `activity_records.hr` (windowed by `activity_records.timestamp`
   filtered to the matched activity_id) over `monitoring_heart_rate`.
   Backend handler is at
   `backend/garminview/api/routes/actalog.py` in `get_session_vitals`.

## Definition of done

- New `garmin_api` activities sync to `garmin_fit` source after the
  next sync run, OR a new column/process tracks per-second HR data
  separately.
- For activity 22451624754 (or any future activity), `activity_records`
  has rows with non-null `hr` covering the full activity window.
- Calendar HR chart for that workout shows a peak ≥160 (matching the
  activity summary).
- No regression for activities that don't have per-second data — they
  fall back to the existing `monitoring_heart_rate` window.

## Related context

- `backend/CLAUDE.md` — sync flags allowlist
- `backend/garminview/api/routes/actalog.py` — `get_session_vitals`
  and the new `_match_garmin_activity` helper added 2026-04-15
- `docs/plans/2026-04-15-wod-review-edit-flow.md` — neighboring work
  on the Calendar tab (Garmin activity matching)

## Workaround in the meantime

The `MatchInfo.activity.{avg_hr, max_hr}` fields are already exposed
on the SessionVitals response and rendered as the headline numbers
above the chart. Users see the correct peak even when the chart can't
draw it at full resolution. Adding a small "chart is minute-resolution"
note next to the chart would close the explanation gap without code
changes — could be done now if the chart vs. headline mismatch keeps
generating questions.

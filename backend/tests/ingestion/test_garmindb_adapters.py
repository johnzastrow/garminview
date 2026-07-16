"""Unit tests for the GarminDB file adapters.

These are the file->dict readers at the head of the ingestion pipeline that was
0-50% covered and recently lost three months of data. Each test builds a real
throwaway SQLite database mirroring the exact table/columns the adapter queries,
seeds edge-case rows (nulls, negatives, malformed timestamps, out-of-range
dates), and asserts on the dicts the adapter yields.
"""

from datetime import date, datetime

import pytest

from garminview.ingestion.file_adapters.garmindb_hr_zones import GarminDBHRZonesAdapter
from garminview.ingestion.file_adapters.garmindb_stress import GarminDBStressAdapter
from garminview.ingestion.file_adapters.garmindb_sleep_events import (
    GarminDBSleepEventsAdapter,
)
from garminview.ingestion.file_adapters.garmindb_steps_activities import (
    GarminDBStepsActivitiesAdapter,
)
from garminview.ingestion.file_adapters.garmindb_activity_laps import (
    GarminDBActivityLapsAdapter,
)
from garminview.ingestion.file_adapters.garmindb_monitoring import (
    GarminDBRespirationAdapter,
    GarminDBPulseOxAdapter,
    GarminDBClimbAdapter,
    GarminDBIntensityAdapter,
    GarminDBStepsAdapter,
)

# A window used by most tests; rows must fall inside/outside this deliberately.
START = date(2025, 6, 1)
END = date(2025, 6, 30)


# --------------------------------------------------------------------------- #
# hr_zones  (garmin_activities.db -> activities.hrz_N_time)
# --------------------------------------------------------------------------- #
class TestHRZonesAdapter:
    def _seed(self, conn):
        conn.executescript(
            """
            CREATE TABLE activities (
                activity_id INTEGER,
                start_time  TEXT,
                hrz_1_time  TEXT,
                hrz_2_time  TEXT,
                hrz_3_time  TEXT,
                hrz_4_time  TEXT,
                hrz_5_time  TEXT
            );
            """
        )
        conn.executemany(
            "INSERT INTO activities VALUES (?,?,?,?,?,?,?)",
            [
                # In-range activity: z1=600s, z2=330s, z3 NULL(skip), z4=0s(kept), z5 NULL(skip)
                (100, "2025-06-15 08:00:00.000000",
                 "00:10:00.000000", "00:05:30.000000", None,
                 "00:00:00.000000", None),
                # Out-of-range date -> excluded entirely by WHERE start_time
                (200, "2025-01-01 08:00:00.000000",
                 "00:20:00.000000", "00:10:00.000000", "00:05:00.000000",
                 "00:02:00.000000", "00:01:00.000000"),
                # In range but hrz_1_time NULL -> excluded by WHERE hrz_1_time IS NOT NULL
                (300, "2025-06-16 08:00:00.000000",
                 None, "00:05:00.000000", None, None, None),
            ],
        )

    def test_parses_and_filters(self, make_garmindb):
        hdd = make_garmindb("garmin_activities.db", self._seed)
        rows = list(GarminDBHRZonesAdapter(hdd).fetch(START, END))

        # Only activity 100 survives; zones 3 & 5 dropped for NULL time.
        assert rows == [
            {"activity_id": 100, "zone": 1, "time_in_zone_s": 600},
            {"activity_id": 100, "zone": 2, "time_in_zone_s": 330},
            {"activity_id": 100, "zone": 4, "time_in_zone_s": 0},
        ]

    def test_metadata(self, make_garmindb):
        hdd = make_garmindb("garmin_activities.db", self._seed)
        a = GarminDBHRZonesAdapter(hdd)
        assert a.source_name() == "garmindb:hr_zones"
        assert a.target_table() == "activity_hr_zones"

    def test_missing_db(self, tmp_path):
        assert list(GarminDBHRZonesAdapter(tmp_path).fetch(START, END)) == []


# --------------------------------------------------------------------------- #
# stress  (garmin.db -> stress.timestamp/stress)
# --------------------------------------------------------------------------- #
class TestStressAdapter:
    def _seed(self, conn):
        conn.executescript(
            "CREATE TABLE stress (timestamp TEXT, stress INTEGER);"
        )
        conn.executemany(
            "INSERT INTO stress VALUES (?,?)",
            [
                ("2025-06-15 10:00:00.000000", 42),     # valid
                ("2025-06-15 10:01:00.000000", -1),     # negative sentinel -> skip
                ("2025-06-15 10:02:00.000000", None),   # NULL stress -> skip
                ("2025-06-16 10:00:00.000000", 0),      # zero is valid (not < 0)
                ("2025-05-01 10:00:00.000000", 50),     # out of range -> excluded
                # passes string range filter but is not a real time -> skip
                ("2025-06-20 99:99:99.000000", 30),
            ],
        )

    def test_parses_and_guards(self, make_garmindb):
        hdd = make_garmindb("garmin.db", self._seed)
        rows = list(GarminDBStressAdapter(hdd).fetch(START, END))

        assert rows == [
            {"timestamp": datetime(2025, 6, 15, 10, 0, 0), "stress_level": 42},
            {"timestamp": datetime(2025, 6, 16, 10, 0, 0), "stress_level": 0},
        ]

    def test_metadata(self, make_garmindb):
        hdd = make_garmindb("garmin.db", self._seed)
        a = GarminDBStressAdapter(hdd)
        assert a.source_name() == "garmindb:stress"
        assert a.target_table() == "stress"

    def test_missing_db(self, tmp_path):
        assert list(GarminDBStressAdapter(tmp_path).fetch(START, END)) == []


# --------------------------------------------------------------------------- #
# sleep_events  (garmin.db -> sleep_events.timestamp/event/duration)
# --------------------------------------------------------------------------- #
class TestSleepEventsAdapter:
    def _seed(self, conn):
        conn.executescript(
            "CREATE TABLE sleep_events (timestamp TEXT, event TEXT, duration TEXT);"
        )
        conn.executemany(
            "INSERT INTO sleep_events VALUES (?,?,?)",
            [
                ("2025-06-15 23:30:00.000000", "deep_sleep", "00:45:00.000000"),
                ("2025-06-15 23:45:00.000000", "light", None),  # NULL duration -> None
                # event longer than the 16-char column -> must be truncated
                ("2025-06-15 23:50:00.000000", "abcdefghijklmnopqrstuvwxyz", "00:10:00.000000"),
                (None, "rem", "00:05:00.000000"),   # NULL ts -> skip
                ("2025-06-20 25:61:00.000000", "awake", "00:01:00.000000"),  # bad ts -> skip
                ("2025-05-01 22:00:00.000000", "deep", "00:30:00.000000"),   # out of range
            ],
        )

    def test_parses_and_guards(self, make_garmindb):
        hdd = make_garmindb("garmin.db", self._seed)
        rows = list(GarminDBSleepEventsAdapter(hdd).fetch(START, END))

        assert rows == [
            {
                "date": date(2025, 6, 15),
                "event_type": "deep_sleep",
                "start": datetime(2025, 6, 15, 23, 30, 0),
                "duration_min": 45,
            },
            {
                "date": date(2025, 6, 15),
                "event_type": "light",
                "start": datetime(2025, 6, 15, 23, 45, 0),
                "duration_min": None,
            },
            {
                "date": date(2025, 6, 15),
                "event_type": "abcdefghijklmnop",  # truncated to 16 chars
                "start": datetime(2025, 6, 15, 23, 50, 0),
                "duration_min": 10,
            },
        ]

    def test_missing_db(self, tmp_path):
        assert list(GarminDBSleepEventsAdapter(tmp_path).fetch(START, END)) == []


# --------------------------------------------------------------------------- #
# steps_activities  (garmin_activities.db -> steps_activities JOIN activities)
# --------------------------------------------------------------------------- #
class TestStepsActivitiesAdapter:
    def _seed(self, conn):
        conn.executescript(
            """
            CREATE TABLE activities (activity_id, start_time TEXT);
            CREATE TABLE steps_activities (
                activity_id, avg_pace TEXT, avg_moving_pace TEXT, max_pace TEXT,
                avg_steps_per_min, avg_step_length, avg_vertical_oscillation,
                avg_vertical_ratio, avg_gct_balance, avg_stance_time_percent, vo2_max
            );
            """
        )
        conn.executemany(
            "INSERT INTO activities VALUES (?,?)",
            [
                (100, "2025-06-15 08:00:00.000000"),
                (200, "2025-01-01 08:00:00.000000"),   # out of range
                (300, "2025-06-16 08:00:00.000000"),
                ("xyz", "2025-06-17 08:00:00.000000"),  # non-numeric id -> skipped
            ],
        )
        conn.executemany(
            "INSERT INTO steps_activities VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                (100, "00:05:30.000000", "00:05:20.000000", "00:04:00.000000",
                 170.0, 1.2, 8.5, 6.5, 50.0, 32.0, 52.0),
                (200, "00:06:00.000000", "00:05:50.000000", "00:04:30.000000",
                 160.0, 1.1, 9.0, 7.0, 51.0, 33.0, 49.0),
                # avg_pace NULL -> pace_avg None, but row still yields (has other data)
                (300, None, "00:05:00.000000", "00:04:10.000000",
                 175.0, 1.3, 8.0, 6.0, 49.0, 31.0, 53.0),
                ("xyz", "00:05:00.000000", None, None,
                 100.0, 1.0, 5.0, 5.0, 40.0, 30.0, 40.0),
            ],
        )

    def test_parses_and_filters(self, make_garmindb):
        hdd = make_garmindb("garmin_activities.db", self._seed)
        rows = list(GarminDBStepsActivitiesAdapter(hdd).fetch(START, END))

        by_id = {r["activity_id"]: r for r in rows}
        # Out-of-range (200) and non-numeric (xyz) excluded.
        assert set(by_id) == {100, 300}

        assert by_id[100]["pace_avg"] == pytest.approx(330.0)      # 5:30
        assert by_id[100]["pace_moving"] == pytest.approx(320.0)   # 5:20
        assert by_id[100]["pace_max"] == pytest.approx(240.0)      # 4:00
        assert by_id[100]["steps_per_min"] == pytest.approx(170.0)
        assert by_id[100]["vo2max"] == pytest.approx(52.0)

        # NULL time string maps to None rather than raising.
        assert by_id[300]["pace_avg"] is None
        assert by_id[300]["pace_moving"] == pytest.approx(300.0)

    def test_missing_db(self, tmp_path):
        assert list(GarminDBStepsActivitiesAdapter(tmp_path).fetch(START, END)) == []


# --------------------------------------------------------------------------- #
# activity_laps  (garmin_activities.db -> activity_laps JOIN activities)
# --------------------------------------------------------------------------- #
class TestActivityLapsAdapter:
    def _seed(self, conn):
        conn.executescript(
            """
            CREATE TABLE activities (activity_id, start_time TEXT);
            CREATE TABLE activity_laps (
                activity_id, lap, start_time TEXT, elapsed_time TEXT,
                distance, avg_hr, max_hr, avg_speed, ascent, calories
            );
            """
        )
        conn.executemany(
            "INSERT INTO activities VALUES (?,?)",
            [
                (100, "2025-06-15 08:00:00.000000"),
                (200, "2025-01-01 08:00:00.000000"),   # out of range
                ("xyz", "2025-06-17 08:00:00.000000"),  # non-numeric id
            ],
        )
        conn.executemany(
            "INSERT INTO activity_laps VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (100, 1, "2025-06-15 08:05:00.000000", "00:04:30.000000",
                 1000.0, 150, 165, 3.7, 5.0, 80),
                # NULL start/elapsed -> None; malformed nothing here
                (100, 2, None, None, 900.0, 140, 155, 3.5, 4.0, 70),
                # malformed start_time -> start_time None but row kept
                (100, 3, "2025-06-15 99:99:99.000000", "00:03:00.000000",
                 800.0, 145, 160, 3.6, 3.0, 60),
                (200, 1, "2025-01-01 08:05:00.000000", "00:04:00.000000",
                 1000.0, 150, 165, 3.7, 5.0, 80),
                ("xyz", 1, "2025-06-17 08:05:00.000000", "00:04:00.000000",
                 1000.0, 150, 165, 3.7, 5.0, 80),
            ],
        )

    def test_parses_and_filters(self, make_garmindb):
        hdd = make_garmindb("garmin_activities.db", self._seed)
        rows = list(GarminDBActivityLapsAdapter(hdd).fetch(START, END))

        # Only activity 100's three laps survive filtering.
        assert {(r["activity_id"], r["lap_index"]) for r in rows} == {
            (100, 1), (100, 2), (100, 3)
        }
        laps = {r["lap_index"]: r for r in rows}

        assert laps[1]["start_time"] == datetime(2025, 6, 15, 8, 5, 0)
        assert laps[1]["elapsed_time_s"] == 270  # 4:30
        assert laps[1]["distance_m"] == pytest.approx(1000.0)
        assert laps[1]["avg_hr"] == 150
        assert laps[1]["calories"] == 80

        # NULL start/elapsed -> None
        assert laps[2]["start_time"] is None
        assert laps[2]["elapsed_time_s"] is None

        # Malformed start_time swallowed to None; the rest of the row is intact.
        assert laps[3]["start_time"] is None
        assert laps[3]["elapsed_time_s"] == 180

    def test_missing_db(self, tmp_path):
        assert list(GarminDBActivityLapsAdapter(tmp_path).fetch(START, END)) == []


# --------------------------------------------------------------------------- #
# monitoring  (garmin_monitoring.db -> the five per-minute streams)
# --------------------------------------------------------------------------- #
class TestMonitoringAdapters:
    def test_steps_filters_nulls_and_dates(self, make_garmindb):
        def seed(conn):
            conn.executescript(
                "CREATE TABLE monitoring (timestamp TEXT, steps INTEGER, activity_type TEXT);"
            )
            conn.executemany(
                "INSERT INTO monitoring VALUES (?,?,?)",
                [
                    ("2025-06-15 00:01:00.000000", 5, "walking"),
                    ("2025-06-15 00:02:00.000000", None, "walking"),  # steps NULL -> excluded
                    ("2025-05-01 00:01:00.000000", 9, "running"),     # out of range
                ],
            )

        hdd = make_garmindb("garmin_monitoring.db", seed)
        rows = list(GarminDBStepsAdapter(hdd).fetch(START, END))
        assert rows == [
            {
                "timestamp": datetime(2025, 6, 15, 0, 1, 0),
                "steps": 5,
                "activity_type": "walking",
            }
        ]

    def test_intensity_time_conversion(self, make_garmindb):
        def seed(conn):
            conn.executescript(
                "CREATE TABLE monitoring_intensity "
                "(timestamp TEXT, moderate_activity_time TEXT, vigorous_activity_time TEXT);"
            )
            conn.executemany(
                "INSERT INTO monitoring_intensity VALUES (?,?,?)",
                [
                    ("2025-06-15 12:00:00.000000", "00:15:00.000000", "00:05:00.000000"),
                    ("2025-06-15 12:01:00.000000", None, None),        # -> None/None, still yielded
                    ("2025-05-01 12:00:00.000000", "00:20:00.000000", "00:10:00.000000"),  # excluded
                ],
            )

        hdd = make_garmindb("garmin_monitoring.db", seed)
        rows = list(GarminDBIntensityAdapter(hdd).fetch(START, END))
        assert rows == [
            {
                "timestamp": datetime(2025, 6, 15, 12, 0, 0),
                "moderate_time_s": 900,
                "vigorous_time_s": 300,
            },
            {
                "timestamp": datetime(2025, 6, 15, 12, 1, 0),
                "moderate_time_s": None,
                "vigorous_time_s": None,
            },
        ]

    def test_climb_maps_columns(self, make_garmindb):
        def seed(conn):
            conn.executescript(
                "CREATE TABLE monitoring_climb "
                "(timestamp TEXT, ascent, descent, cum_ascent, cum_descent);"
            )
            conn.executemany(
                "INSERT INTO monitoring_climb VALUES (?,?,?,?,?)",
                [
                    ("2025-06-15 09:00:00.000000", 10.0, 5.0, 100.0, 90.0),
                    ("2025-05-01 09:00:00.000000", 1.0, 1.0, 1.0, 1.0),  # excluded
                ],
            )

        hdd = make_garmindb("garmin_monitoring.db", seed)
        rows = list(GarminDBClimbAdapter(hdd).fetch(START, END))
        assert rows == [
            {
                "timestamp": datetime(2025, 6, 15, 9, 0, 0),
                "ascent_m": 10.0,
                "descent_m": 5.0,
                "cum_ascent_m": 100.0,
                "cum_descent_m": 90.0,
            }
        ]

    def test_respiration_and_pulse_ox(self, make_garmindb):
        def seed(conn):
            conn.executescript(
                """
                CREATE TABLE monitoring_rr (timestamp TEXT, rr);
                CREATE TABLE monitoring_pulse_ox (timestamp TEXT, pulse_ox);
                """
            )
            conn.execute(
                "INSERT INTO monitoring_rr VALUES (?,?)",
                ("2025-06-15 03:00:00.000000", 14.5),
            )
            conn.execute(
                "INSERT INTO monitoring_rr VALUES (?,?)",
                ("2025-05-01 03:00:00.000000", 99.0),  # out of range
            )
            conn.execute(
                "INSERT INTO monitoring_pulse_ox VALUES (?,?)",
                ("2025-06-15 03:00:00.000000", 97.0),
            )

        hdd = make_garmindb("garmin_monitoring.db", seed)
        rr = list(GarminDBRespirationAdapter(hdd).fetch(START, END))
        assert rr == [{"timestamp": datetime(2025, 6, 15, 3, 0, 0), "rr": 14.5}]

        ox = list(GarminDBPulseOxAdapter(hdd).fetch(START, END))
        assert ox == [{"timestamp": datetime(2025, 6, 15, 3, 0, 0), "spo2": 97.0}]

    def test_missing_db(self, tmp_path):
        for cls in (
            GarminDBStepsAdapter,
            GarminDBIntensityAdapter,
            GarminDBClimbAdapter,
            GarminDBRespirationAdapter,
            GarminDBPulseOxAdapter,
        ):
            assert list(cls(tmp_path).fetch(START, END)) == []

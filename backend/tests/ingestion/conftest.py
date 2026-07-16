"""Shared helpers for ingestion adapter/orchestrator tests.

These build real, throwaway SQLite databases on disk under the layout the
garmindb file adapters expect (``<health_data_dir>/DBs/<name>.db``), so the
adapters exercise their genuine ``sqlite3`` query paths rather than mocks.
"""

import sqlite3

import pytest


@pytest.fixture
def make_garmindb(tmp_path):
    """Factory that materialises ``<tmp_path>/DBs/<db_name>`` on disk.

    ``populate`` receives an open :class:`sqlite3.Connection`; the caller runs
    whatever DDL/inserts it needs. The connection is committed and closed for
    you. Returns ``tmp_path`` — pass it straight in as ``health_data_dir``.
    """

    def _make(db_name, populate):
        dbs = tmp_path / "DBs"
        dbs.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(dbs / db_name))
        try:
            populate(conn)
            conn.commit()
        finally:
            conn.close()
        return tmp_path

    return _make

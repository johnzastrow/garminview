def test_sqlite_engine_created(test_config, engine):
    from garminview.core.database import verify_connection
    verify_connection(engine)  # must not raise


def test_mariadb_url_format():
    from garminview.core.config import Config, DBBackend
    cfg = Config(db_backend=DBBackend.mariadb, db_url="user:pass@localhost:3306/gv")
    assert cfg.db_backend == DBBackend.mariadb

from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from garminview.core.config import Config, DBBackend


class Base(DeclarativeBase):
    pass


def create_db_engine(config: Config) -> Engine:
    if config.db_backend == DBBackend.mariadb:
        url = f"mysql+pymysql://{config.db_url}?charset=utf8mb4"
        return create_engine(url, pool_pre_ping=True, pool_size=10)
    db_path = config.db_path.replace("~", __import__("os").path.expanduser("~"))
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )


def get_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


def verify_connection(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

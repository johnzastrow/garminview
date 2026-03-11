from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict


class DBBackend(str, Enum):
    sqlite = "sqlite"
    mariadb = "mariadb"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GARMINVIEW_")

    db_backend: DBBackend = DBBackend.sqlite
    db_path: str = "garminview.db"          # sqlite only
    db_url: str = ""                         # mariadb: user:pass@host:port/dbname
    health_data_dir: str = "~/HealthData"
    log_level: str = "INFO"
    log_dir: str = "logs"
    secret_key: str = "change-me-in-production"
    cors_origins: list[str] = ["http://localhost:5173"]


def get_config() -> Config:
    return Config()

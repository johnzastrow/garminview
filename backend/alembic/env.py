import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from garminview.core.config import get_config, DBBackend
from garminview.core.database import Base
import garminview.models  # noqa — registers all models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    cfg = get_config()
    if cfg.db_backend == DBBackend.mariadb:
        return f"mysql+pymysql://{cfg.db_url}?charset=utf8mb4"
    return f"sqlite:///{cfg.db_path}"


def run_migrations_offline():
    context.configure(url=get_url(), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    cfg = config.get_section(config.config_ini_section)
    cfg["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(cfg, prefix="sqlalchemy.",
                                     poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

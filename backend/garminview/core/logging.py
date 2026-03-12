import logging
import logging.handlers
from pathlib import Path

import structlog


def get_sync_logger(log_dir: str) -> logging.Logger:
    """Return a dedicated logger that writes sync output to a rotating file."""
    path = Path(log_dir).expanduser()
    path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("garminview.sync.file")
    if logger.handlers:
        return logger  # already configured

    handler = logging.handlers.RotatingFileHandler(
        path / "sync.log",
        maxBytes=2 * 1024 * 1024,  # 2 MB per file
        backupCount=5,              # keep sync.log + 5 rotated = 10 MB max
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, level.upper()))
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str):
    return structlog.get_logger(name)

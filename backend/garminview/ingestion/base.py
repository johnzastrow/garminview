from abc import ABC, abstractmethod
from datetime import date
from typing import Iterator


class BaseAdapter(ABC):
    @abstractmethod
    def fetch(self, start_date: date, end_date: date) -> Iterator[dict]:
        """Yield records as dicts for upsert into target table."""

    @abstractmethod
    def source_name(self) -> str:
        """Identifier for sync_log and data_provenance."""

    @abstractmethod
    def target_table(self) -> str:
        """Name of the DB table this adapter writes to."""

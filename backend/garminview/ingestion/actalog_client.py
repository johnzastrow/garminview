from __future__ import annotations
import httpx
from tenacity import retry, retry_if_exception, wait_exponential, stop_after_attempt
from garminview.core.logging import get_logger

log = get_logger(__name__)

LBS_TO_KG = 0.453592


def _is_429(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


_retry = retry(
    retry=retry_if_exception(_is_429),
    wait=wait_exponential(multiplier=1, min=30, max=300),
    stop=stop_after_attempt(5),
    reraise=True,
)


class ActalogClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        refresh_token: str | None = None,
        weight_unit: str = "kg",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.refresh_token = refresh_token
        self.weight_unit = weight_unit
        self._access_token: str | None = None

    # ── Auth ──────────────────────────────────────────────────────────

    async def _login(self) -> str:
        async with httpx.AsyncClient() as http:
            r = await http.post(
                f"{self.base_url}/api/auth/login",
                json={"email": self.email, "password": self.password, "remember_me": True},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            self.refresh_token = data.get("refresh_token")
            return data["access_token"]

    async def _refresh(self) -> str:
        async with httpx.AsyncClient() as http:
            r = await http.post(
                f"{self.base_url}/api/auth/refresh",
                json={"refresh_token": self.refresh_token},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            if "refresh_token" in data:
                self.refresh_token = data["refresh_token"]
            return data["access_token"]

    async def authenticate(self) -> str:
        """Return a valid access token, refreshing or logging in as needed."""
        if self.refresh_token:
            try:
                self._access_token = await self._refresh()
                return self._access_token
            except Exception:
                log.warning("actalog_refresh_failed", reason="falling back to login")
        self._access_token = await self._login()
        return self._access_token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    # ── Data fetching ──────────────────────────────────────────────────

    @_retry
    async def _get_page(self, url: str, params: dict) -> list[dict]:
        async with httpx.AsyncClient() as http:
            r = await http.get(url, headers=self._auth_headers(), params=params, timeout=30)
            r.raise_for_status()
            return r.json()

    async def list_workouts(self, page_size: int = 100) -> list[dict]:
        """Fetch all workout list entries via pagination."""
        results: list[dict] = []
        page = 1
        while True:
            batch = await self._get_page(
                f"{self.base_url}/api/workouts",
                {"page": page, "page_size": page_size},
            )
            if not batch:
                break
            results.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        return results

    @_retry
    async def get_workout(self, workout_id: int) -> dict:
        """Fetch full workout detail including embedded movements and WODs."""
        async with httpx.AsyncClient() as http:
            r = await http.get(
                f"{self.base_url}/api/workouts/{workout_id}",
                headers=self._auth_headers(),
                timeout=15,
            )
            r.raise_for_status()
            return r.json()

    @_retry
    async def list_pr_movements(self) -> list[dict]:
        """Fetch pre-aggregated MovementPRSummary rows from /api/pr-movements."""
        async with httpx.AsyncClient() as http:
            r = await http.get(
                f"{self.base_url}/api/pr-movements",
                headers=self._auth_headers(),
                timeout=15,
            )
            r.raise_for_status()
            return r.json()

    def convert_weight(self, raw: float | None) -> float | None:
        """Convert raw weight value to kg based on configured unit."""
        if raw is None:
            return None
        if self.weight_unit == "lbs":
            return round(raw * LBS_TO_KG, 3)
        return raw

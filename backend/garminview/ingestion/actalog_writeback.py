"""
Actalog API write-back client.

Authenticates with the Actalog API (JWT), pushes approved workout data:
- Updated Markdown notes via PUT /workouts/{id}
- New WODs via POST /wods
- New movements via POST /movements
"""
import json
import logging
from datetime import datetime

import httpx

from garminview.models.actalog import ActalogNoteParse, ActalogWorkout
from garminview.models.config import AppConfig

_log = logging.getLogger(__name__)


class ActalogWritebackClient:
    """HTTP client for writing data back to the Actalog API."""

    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.token: str | None = None
        self.client = httpx.Client(timeout=30)

    def login(self) -> None:
        """Authenticate with Actalog API and store JWT token."""
        resp = self.client.post(
            f"{self.base_url}/api/auth/login",
            json={"email": self.email, "password": self.password},
        )
        resp.raise_for_status()
        data = resp.json()
        self.token = data.get("token") or data.get("access_token")
        if not self.token:
            raise ValueError("No token in login response")
        _log.info("Authenticated with Actalog API")

    def _headers(self) -> dict:
        if not self.token:
            self.login()
        return {"Authorization": f"Bearer {self.token}"}

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an authenticated request, retry once on 401."""
        resp = self.client.request(
            method, f"{self.base_url}{path}",
            headers=self._headers(), **kwargs,
        )
        if resp.status_code == 401:
            self.login()
            resp = self.client.request(
                method, f"{self.base_url}{path}",
                headers=self._headers(), **kwargs,
            )
        resp.raise_for_status()
        return resp

    def update_workout_notes(self, workout_id: int, notes: str) -> dict:
        """Update workout notes via PUT /api/workouts/{id}."""
        resp = self._request("PUT", f"/api/workouts/{workout_id}", json={"notes": notes})
        return resp.json()

    def get_wods(self) -> list[dict]:
        """Fetch all WODs from Actalog."""
        resp = self._request("GET", "/api/wods")
        return resp.json()

    def create_wod(self, name: str, regime: str = "", score_type: str = "") -> dict:
        """Create a new WOD in Actalog."""
        resp = self._request("POST", "/api/wods", json={
            "name": name,
            "regime": regime,
            "score_type": score_type,
        })
        return resp.json()

    def get_movements(self) -> list[dict]:
        """Fetch all movements from Actalog."""
        resp = self._request("GET", "/api/movements")
        return resp.json()

    def create_movement(self, name: str, movement_type: str = "") -> dict:
        """Create a new movement in Actalog."""
        resp = self._request("POST", "/api/movements", json={
            "name": name,
            "type": movement_type,
        })
        return resp.json()

    def close(self):
        self.client.close()


def _get_client_from_config(session) -> ActalogWritebackClient:
    """Create an ActalogWritebackClient from app_config settings."""
    def cfg(key: str) -> str | None:
        row = session.get(AppConfig, key)
        return row.value if row else None

    url = cfg("actalog_url")
    email = cfg("actalog_email")
    password = cfg("actalog_password")

    if not url or not email or not password:
        raise ValueError("Actalog connection not configured (URL, email, or password missing)")

    return ActalogWritebackClient(base_url=url, email=email, password=password)


def write_back_approved(session, parse_id: int, edited_markdown: str | None = None) -> str:
    """
    Push an approved parse record to the Actalog API.

    Args:
        session: SQLAlchemy session
        parse_id: ID of the actalog_note_parses record
        edited_markdown: If provided, use this instead of DB value (ensures
                         human edits are sent even if session caching is stale)

    Returns "sent" on success, "approved" on failure (stays approved locally).
    """
    record = session.get(ActalogNoteParse, parse_id)
    if not record:
        raise ValueError(f"Parse record {parse_id} not found")
    if record.parse_status not in ("approved",):
        raise ValueError(f"Parse {parse_id} has status '{record.parse_status}', expected 'approved'")

    workout = session.get(ActalogWorkout, record.workout_id)
    if not workout:
        raise ValueError(f"Workout {record.workout_id} not found")

    try:
        client = _get_client_from_config(session)

        # 1. Update workout notes with approved Markdown
        # Prefer the explicitly passed edited_markdown (from the approve endpoint)
        # over the DB value, to ensure human edits are always sent
        markdown = edited_markdown or workout.formatted_notes or workout.notes
        if markdown:
            client.update_workout_notes(workout.id, markdown)
            _log.info("Updated notes for workout %d on Actalog", workout.id)

        # 2. Create WODs from parsed JSON if present
        if record.parsed_json:
            parsed = json.loads(record.parsed_json)
            # Handle double-encoded JSON (string inside string)
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            if not isinstance(parsed, dict):
                _log.warning("parsed_json for parse %d is not a dict: %s", parse_id, type(parsed))
                parsed = {}
            wods = parsed.get("wods", [])
            _log.info("Parse %d: found %d WOD(s) in parsed_json: %s",
                       parse_id, len(wods),
                       [w.get("name", w) if isinstance(w, dict) else w for w in wods[:5]])

            if wods:
                # Fetch existing WODs for dedup — handle various response shapes
                try:
                    remote_wods = client.get_wods()
                    # API may return list of dicts or list of strings or a wrapper dict
                    if isinstance(remote_wods, dict):
                        remote_wods = remote_wods.get("wods", remote_wods.get("data", []))
                    existing_wods = set()
                    for w in remote_wods:
                        if isinstance(w, dict):
                            name = w.get("name", "")
                        elif isinstance(w, str):
                            name = w
                        else:
                            continue
                        if name:
                            existing_wods.add(name.lower())
                except Exception as exc:
                    _log.warning("Could not fetch existing WODs: %s — skipping dedup", exc)
                    existing_wods = set()

                for wod in wods:
                    # Handle wod being a dict or a string
                    if isinstance(wod, str):
                        wod_name = wod
                        regime = ""
                        score_type = ""
                    elif isinstance(wod, dict):
                        wod_name = wod.get("name", "")
                        regime = wod.get("regime", "")
                        score_type = wod.get("score_type", "")
                    else:
                        _log.warning("Unexpected WOD type: %s", type(wod))
                        continue

                    _log.info("  WOD '%s': exists=%s", wod_name, wod_name.lower() in existing_wods if wod_name else "empty")
                    if wod_name and wod_name.lower() not in existing_wods:
                        try:
                            client.create_wod(name=wod_name, regime=regime, score_type=score_type)
                            _log.info("Created WOD '%s' on Actalog", wod_name)
                        except Exception as exc:
                            _log.warning("Failed to create WOD '%s': %s", wod_name, exc)

        # 3. Mark as sent
        record.parse_status = "sent"
        record.reviewed_at = datetime.now()
        session.commit()
        client.close()
        return "sent"

    except Exception as exc:
        _log.error("Write-back to Actalog failed for parse %d: %s", parse_id, exc)
        record.error_message = str(exc)
        session.commit()
        return "approved"

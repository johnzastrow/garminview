# 2026-04-15 — WOD review/edit flow + Actalog dedup resolution

## Goal

Make the Review tab a real editing surface for approved WODs, not just a
rubber-stamp of the LLM's output. Let the user adjust per-WOD name and
description before Approve, and resolve name conflicts with Actalog
(create-new / overwrite / skip) consciously rather than via silent dedup.

## What shipped

### Backend

- **Schema** (`api/schemas/actalog.py`) — `NoteParseApproveIn` now carries
  `wod_edits: list[WodEditIn]`. Each `WodEditIn` has `name`, `description`,
  `dedup_action` (`create` | `overwrite` | `skip`), `existing_wod_id`.

- **Route** (`api/routes/actalog.py — _parse_item`) seeds per-WOD data on
  read:
    - `description` — auto-generated via `_build_wod_description()` when the
      stored parsed_json doesn't already have one
    - `exists_on_actalog` + `existing_wod_id` — checked against the local
      `actalog_wods` cache (synced by `actalog_sync.py`)
  Saved edits in `parsed_json` are preserved; the function never overwrites
  human-authored values.

- **Route** (`approve_parse`) merges every supplied `wod_edits[i]` into
  `parsed_json["wods"][i]` before calling `write_back_approved`.

- **Writeback client** (`ingestion/actalog_writeback.py`):
    - New `ActalogWritebackClient.update_wod()` → `PUT /api/wods/{id}` with
      any of `name`, `description`, `regime`, `score_type`.
    - `write_back_approved` branches on `wod["dedup_action"]`:
        - `create`    → `POST /api/wods` with edited name + description
        - `overwrite` → `PUT /api/wods/{existing_wod_id}` with edited name +
          description. Falls back to a live lookup by name if the frontend
          didn't pass an id.
        - `skip`      → no Actalog call for that WOD
    - Actalog 403 on overwrite (standard/canonical WODs like "Fran" that
      the user doesn't own) is caught and surfaced as a readable
      `error_message`, record stays `approved` for retry/adjustment.
    - Default action when the frontend didn't specify one: `skip` on
      conflict, `create` otherwise — so old payloads never accidentally
      overwrite anything.

- **LLM prompt** (`ingestion/notes_parser.py`) — added a `description` field
  to the per-WOD schema plus a rule block describing the expected format
  (regime header → tier sections if multi-tier, flat list otherwise →
  stimulus → RPE, no name header, no performance_notes). `WodSchema`
  Pydantic model gained `description: str | None = None` so the field
  passes through validation.

- **DB-stored prompt** (`app_config.parser.system_prompt`) overwritten
  with the refreshed `DEFAULT_SYSTEM_PROMPT`.

### Frontend — `frontend/src/components/actalog/ReviewQueue.vue`

- Fetches `GET /actalog/wods` once on mount → lowercase-name → id index
  used for live conflict detection without a server roundtrip on every
  keystroke.

- Per-WOD state moved from `editedWodDescriptions: string[]` to
  `wodEdits: WodEdit[]` carrying `name`, `description`, `dedup_action`,
  `existing_wod_id`.

- WOD card layout (pending parses):
    - Always-editable **Name** input (not just on conflict).
    - Conflict panel (only when current edited name matches the index):
      three radios — Create (disabled while the name still collides),
      Overwrite, Skip. **Default is Skip** so an unconsidered Approve
      cannot silently overwrite.
    - Description textarea as before.

- On Approve, re-resolves `existing_wod_id` from the currently-edited
  name so a rename targets the correct Actalog row (or clears the id if
  the rename made the name unique).

## Actalog API reference

Server repo: `/home/jcz/Github/actionlog/`
Swagger:     `/home/jcz/Github/actionlog/docs/swagger.yaml`

- `PUT /api/wods/{id}` accepts `{name, description, regime, score_type,
  notes, source, type, url}` — all optional.
- Returns `403` ("not your WOD") when attempting to update a WOD the user
  doesn't own (standard benchmarks are immutable). The backend handles
  this and keeps status=`approved`.

## Known gaps / follow-ups

1. **Reparse to backfill descriptions on existing records.** The Feb 20
   "Quick Log" parse (and the 16 other pending records) still have
   empty-ish auto-generated descriptions because their `parsed_json` was
   written before the new prompt. They need a Reparse click to get
   LLM-authored descriptions. Or we add a one-shot CLI that walks
   pending records and reparses them.

2. **Stale `actalog_wods` cache.** Conflict detection uses the local
   copy. If a WOD was created on Actalog since the last `actalog_sync`,
   the UI won't show it as a conflict and we'll fall through to create —
   Actalog then returns `500 "already exists"` which we already log as
   success but skip the description update. Low priority; only bites
   when the user creates WODs directly on Actalog between syncs.

3. **End-to-end not yet verified against real Actalog.** Backend tests
   142/142 pass; frontend typecheck clean. Need a live approve against a
   conflicting WOD to confirm the overwrite PUT lands as expected.

## Dev session gotchas worth remembering

- **CORS allowlist** is `http://localhost:5173` exactly — browsing the
  Vite dev server at `http://127.0.0.1:5173` fails preflight silently
  (preflight 400, no `access-control-allow-origin` in the response).
  Always open `http://localhost:5173` instead.

- **Changing `DEFAULT_SYSTEM_PROMPT`** in `notes_parser.py` is a no-op on
  existing installs until the DB row `app_config.parser.system_prompt`
  is overwritten. Use `seed_default_config(session, update_prompt=True)`
  or the `POST /admin/actalog/parser/config` endpoint to push the new
  prompt live.

## Status at end of session

- Dev backend: http://localhost:8000 (uvicorn `--reload`, running)
- Dev frontend: http://localhost:5173 (Vite, running)
- Docker containers (`:local` images, port 8010) untouched — still
  serving the old code. Rebuild + redeploy when the Review tab flow has
  been validated live.
- Next action: daisy reparses the Feb 20 "Quick Log" parse and verifies
  the new per-WOD description is populated by the LLM and renders in
  the Review tab textarea.

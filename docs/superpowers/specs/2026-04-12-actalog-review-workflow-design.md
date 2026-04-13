# Actalog Review Workflow — Design Spec

**Date:** 2026-04-12
**Sub-project:** C of 3 (A = HR Zones ✅, B = Tasks Panel ✅)

---

## Goal

Complete the Actalog integration pipeline: auto-parse new workout notes after sync, provide a review queue UI for human QA of parsed output (with manual edit capability), and write approved data back to the Actalog API. Consolidate all Actalog-related UI into a dedicated screen with tabs.

---

## What Already Exists

| Component | Status |
|-----------|--------|
| Scheduled Actalog sync (APScheduler) | ✅ Built |
| Workout notes parser (Ollama LLM) | ✅ Built |
| `actalog_note_parses` staging table | ✅ Built |
| Parser admin API (approve/reject/reparse/run/stats/config) | ✅ Built |
| Tasks panel showing pending count | ✅ Built |
| Parser config UI in Admin panel | ✅ Built |
| ActalogDashboard with workouts/analytics | ✅ Built |
| Actalog connection/sync config in Admin | ✅ Built |
| Auto-parse after sync | ❌ Missing |
| Review queue frontend UI | ❌ Missing |
| Write-back to Actalog API | ❌ Missing |
| Consolidated Actalog screen | ❌ Missing |

---

## Architecture

Four changes to the existing codebase:

1. **Auto-parse hook** — call the parser after each scheduled sync completes
2. **Review queue UI** — Vue component for browsing, editing, and approving parsed notes
3. **Write-back service** — authenticate with Actalog API (JWT), push approved WODs/notes
4. **UI consolidation** — move all Actalog UI into tabbed `/actalog` screen

---

## 1. Auto-Parse After Sync

### Change: `backend/garminview/core/startup.py`

In `_actalog_job()`, after the sync completes successfully, trigger the parser:

```python
# After sync completes:
from garminview.ingestion.actalog_parser import run_parser
run_parser(session)
```

The parser already:
- Skips workouts that already have a parse record (idempotent)
- Only processes workouts with non-empty notes above `min_note_length`
- Creates `actalog_note_parses` rows with `parse_status='pending'`

No new API endpoints needed. The existing `POST /admin/actalog/parser/run` manual trigger stays as a fallback.

---

## 2. Review Queue UI

### New component: `frontend/src/components/actalog/ReviewQueue.vue`

**List view:**
- Table of parses: workout date, workout name, content_class badge (WORKOUT/MIXED/PERFORMANCE/SKIP), status badge (pending/approved/rejected/sent), LLM model
- **Sorting:** Date column sortable ascending/descending (click header to toggle, default newest first)
- **Filters:**
  - Status dropdown: pending (default), approved, rejected, sent, all
  - Content class dropdown: all, WORKOUT, MIXED, PERFORMANCE_ONLY, SKIP
  - Keyword search: free-text search across workout name and raw notes content
- Click a row to open detail view

**Detail view (inline expand or modal):**
- **Left panel:** Original raw notes (plain text, read-only, monospace)
- **Right panel:** Parsed Markdown with Edit/Preview toggle:
  - **Edit mode:** `<textarea>` with the Markdown, user can manually correct
  - **Preview mode:** Rendered Markdown (use a lightweight MD renderer like `marked`)
- **Below:** Structured data summary — WODs extracted (name, regime, score_type), movements list
- **Action buttons:**
  - **Edit/Preview** toggle
  - **Save** — persist Markdown edits to `parsed_json` without changing status
  - **Approve** — save edits + set status to approved + trigger write-back to Actalog
  - **Reject** — set status to rejected, advance to next pending item
  - **Reparse** — delete parse record, re-run LLM, show new result
- **Keyboard shortcuts:** `a` approve, `r` reject, `n` next pending, `e` toggle edit

**Empty state:** "No pending reviews — all caught up!" with count of total approved/rejected.

### API changes

The existing parser admin API already has the core endpoints:
- `GET /admin/actalog/parser/queue` — list parses by status
- `POST /admin/actalog/parser/approve/{id}` — approve
- `POST /admin/actalog/parser/reject/{id}` — reject
- `POST /admin/actalog/parser/reparse/{workout_id}` — reparse

**Modification needed for queue endpoint:** Add query parameters to support sorting, filtering, and search:

```
GET /admin/actalog/parser/queue?status=pending&content_class=WORKOUT&q=deadlift&sort=date&order=desc
```

- `status` — filter by parse_status (existing)
- `content_class` — filter by content_class (new)
- `q` — keyword search across workout name and raw_notes (new, SQL LIKE)
- `sort` — sort field: `date` (default) (new)
- `order` — `asc` or `desc` (default: `desc`) (new)

**One modification needed:** The approve endpoint currently only writes Markdown to `actalog_workouts.notes` locally. It needs to also trigger the write-back service (Section 3). Add an optional `edited_markdown` field to the approve request body so the frontend can send user-corrected Markdown.

Modified endpoint:
```
POST /admin/actalog/parser/approve/{id}
Body: { "edited_markdown": "optional corrected markdown" }
```

If `edited_markdown` is provided, use it instead of the parsed Markdown. Update both `actalog_note_parses.parsed_json` and `actalog_workouts.notes`.

---

## 3. Write-Back to Actalog API

### New module: `backend/garminview/ingestion/actalog_writeback.py`

**`class ActalogClient:`**
- Reads Actalog URL, email, password from `app_config`
- `login()` — `POST /auth/login` → stores JWT token
- Auto-refreshes token on 401
- Methods:
  - `update_workout_notes(workout_id, markdown)` → `PUT /workouts/{id}`
  - `create_wod(name, regime, score_type)` → `POST /wods` → returns WOD ID
  - `create_movement(name, type)` → `POST /movements` → returns movement ID
  - `get_wods()` → `GET /wods` — for checking if WOD already exists
  - `get_movements()` → `GET /movements` — for checking if movement exists

**`write_back_approved(session, parse_id):`**
1. Load the `actalog_note_parses` record
2. Authenticate with Actalog API
3. Update workout notes with approved Markdown: `PUT /workouts/{id}`
4. For each WOD in parsed JSON:
   - Check if WOD name already exists in Actalog (fuzzy match)
   - If new: `POST /wods` to create it
5. For each movement in parsed JSON:
   - Check if movement already exists
   - If new: `POST /movements` to create it
6. On success: set `parse_status = 'sent'`
7. On failure: keep `parse_status = 'approved'`, store error in `error_message`

**Status flow:**
```
pending → approved → sent
   ↓
rejected
```

- `approved` = human approved, not yet pushed to Actalog
- `sent` = successfully pushed to Actalog
- If push fails, stays `approved` — user sees a "Retry Push" button for approved-but-not-sent items

### Error handling

- Actalog unreachable: approve succeeds locally (status=approved), warning shown in UI. "Push to Actalog" button appears.
- Duplicate WOD/movement: skip creation, log info
- Auth failure: show error, suggest checking credentials in Settings tab

---

## 4. Consolidated Actalog Screen

### Restructured `frontend/src/views/ActalogDashboard.vue`

Tabbed layout with 4 tabs:

| Tab | Content | Source |
|-----|---------|--------|
| **Workouts** | Workout list, detail with movements/WODs, session vitals, cross-reference | Existing ActalogDashboard content |
| **Review** | Review queue (Section 2) | New `ReviewQueue.vue` component |
| **Analytics** | PRs, movement history, WOD history charts | Existing components |
| **Settings** | Connection config (URL, email, password, test button), sync schedule, parser config (Ollama URL, model, system prompt, run/reparse buttons) | Move from Admin.vue |

### Admin panel cleanup

**Comment out** (do not delete — keep for reference) from `Admin.vue`:
- The "parser" tab (entire `<div v-if="activeTab === 'parser'">` section) — wrap in `<!-- MOVED TO /actalog Settings tab ... -->`
- Actalog connection/sync config (if it's in Admin) — wrap in `<!-- MOVED TO /actalog Settings tab ... -->`

The code stays in the file as a commented reference while the new Settings tab is validated.

Keep in Admin:
- Tasks Panel still references `/actalog` for pending review count — update the link to point to `/actalog?tab=review`

### Navigation

The existing `/actalog` nav item stays. The Tasks Panel "N workout notes awaiting review" action item links to `/actalog?tab=review`.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Ollama not running when auto-parse triggers | Parser logs error, skips. No crash. Workouts stay un-parsed until next run or manual trigger. |
| Actalog API unreachable on approve | Approve succeeds locally (status=approved). Warning shown. "Push to Actalog" button for retry. |
| WOD already exists in Actalog | Skip creation, link to existing. Match by name (case-insensitive). |
| Movement already exists in Actalog | Skip creation, link to existing. |
| User edits Markdown then clicks Reparse | Confirm dialog: "Reparse will discard your edits. Continue?" |
| Parse produces SKIP content_class | Shows in queue with SKIP badge. Can approve (writes notes) or reject (no action). |
| Multiple WODs in one workout | All WODs created/linked on approve. Each shown in the structured data preview. |

---

## Testing

- **Auto-parse:** Unit test — mock sync completion, verify parser called
- **Write-back:** Unit test — mock Actalog API responses, verify correct endpoints called with correct data
- **Approve with edits:** Integration test — approve with `edited_markdown`, verify both local DB and write-back use edited version
- **Review queue API:** Existing tests cover queue/approve/reject — add test for `edited_markdown` field
- **Frontend:** Manual smoke test — navigate through list → detail → edit → preview → approve flow

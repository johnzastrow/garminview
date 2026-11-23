# Frontend v2: UX/UI restart and anti-slop test (DRAFT)

Status: DRAFT, awaiting sign-off on direction and phasing. Written 2026-11-22.
Context: pilot test for the LLM usage objectives exercise (ck note rQliJ7w8Gmkz), objective O4,
KR4.1: each new UI is rated 1-5 and the average must be 4 or higher. Baseline: rate the current UI.

## Decisions so far (from the user, 2026-11-22)

| Topic | Decision |
| --- | --- |
| Scope | Completely start over on UX/UI (all 21 views), not a re-skin |
| Reference | Dashboard layout like Color Admin v4 (https://seantheme.com/color-admin/admin/html/index_v4.html) |
| Isolation | New `frontend-v2/` folder next to `frontend/`; old UI untouched until v2 is accepted |
| Direction | Claude proposes 2-3 written directions; user picks before any build |
| Stack | "Whatever achieves the Color Admin style" (see Stack, below) |

## What the reference is (fetched 2026-11-22, page text only)

Color Admin is a commercial Bootstrap 5 + jQuery template sold through WrapBootstrap. Layout pattern:

- Dark left sidebar with collapsible groups; fixed top bar with search, notifications, profile.
- Page header: title, one-line subtitle, date-range control, Export button.
- Body: one hero KPI panel, a row of small stat tiles with deltas, then a 12-column grid of
  panels (chart with 1D/7D/1M/1Y toggles, ranked table, map, breakdown list, KPI lists).
- Panels carry round header controls (expand, reload, collapse, remove).
- App-settings drawer: dark mode, fixed header or sidebar, 20 theme colors.

Colors, fonts and density could not be read from the page text; take a screenshot before relying on them.

## Constraints

1. **Licence.** Color Admin is paid. Its licence terms were not readable from the pages fetched.
   Do not copy its code, CSS, icons or images. Reproduce only the layout pattern (sidebar,
   KPI tiles, panel grid), which is a generic admin-dashboard structure.
2. **Test validity.** The reference is itself a template look. The anti-slop test is
   therefore: same structure, distinctive identity (type, palette, chart styling, motion,
   one signature element). A result that looks like Color Admin with a new accent colour fails.
3. **Self-hosted only.** No CDN fonts or scripts (privacy preference). Fonts come from npm
   packages (for example fontsource) and are bundled. Keep the existing Caddy setup and any
   CSP headers.
4. **Existing production app.** Frontend-only change. API client, stores and routes are reused;
   no backend changes. Existing unit tests are ported or replaced; the type-check must stay green.
5. **Versioning.** Bump the version in `backend/pyproject.toml` and add a changelog entry only
   when v2 is merged, not while it lives in `frontend-v2/`.

## Stack

Keep Vue 3, Vite, Pinia, vue-router, vue-echarts and the existing axios client. Do not add
Bootstrap or jQuery: they are what makes templates look alike. Build a small design system
instead: CSS custom properties (tokens) for color, type, spacing and elevation; light and dark
themes; a handful of components (AppShell, SideNav, PageHeader, KpiTile, Panel, RangeToggle,
DataTable, ChartPanel). ECharts gets a custom theme object so charts share the identity.

## Candidate directions (pick one; fonts are candidates, confirm after a type test)

Each keeps the Color Admin structure and differs in identity.

**A. Instrument panel (training log).** Graphite canvas, dark sidebar, hairline grid lines,
monospace tabular numerals for every metric, one signal accent (amber or orange) plus a cool
secondary for comparisons. Signature: KPI tiles that look like gauge readouts, with a thin
tick-scale along the bottom edge. Dense, utilitarian. Candidate type: a characterful grotesque
for headings with a tabular mono for numbers.

**B. Field journal (editorial).** Warm paper background in light mode, deep ink in dark mode,
serif display headings, small-caps labels, charts annotated like figures with captions and
callouts. Signature: each chart panel has a figure number and a one-sentence takeaway written
from the data. Less dense, more reading. Candidate type: a text serif for headings, a quiet
humanist sans for UI.

**C. Altimeter (terrain).** Deep night-teal canvas, faint topographic contour texture behind
the grid, luminous data colors with a restrained palette, rounded geometric sans. Signature:
sparklines drawn as elevation profiles. Atmospheric, most distinct from a stock admin look.

Recommendation: A for density and fit with training data; C if you want the strongest
departure from the template look. Both are testable with the same pilot views.

## Phasing

Rolling out all 21 views blind would be expensive to abandon. Stage it, with a rating gate.

| Phase | Output | Gate |
| --- | --- | --- |
| 0. Baseline | Playwright screenshots of the current UI (phone and desktop width); user rates the last 5 UIs or pages 1-5 | Baseline recorded in ck |
| 1. Brief | Chosen direction, type test, palette, one-page style guide | User sign-off |
| 2. Foundation | `frontend-v2/` scaffold, tokens, themes, shell, core components, ECharts theme | Type-check and unit tests green |
| 3. Pilot views | DailyOverview, one chart dashboard (SleepDashboard), Admin | User rates each 1-5; average of 4 or more to continue |
| 4. Rollout | Remaining 18 views, grouped by shared layout | Per-group screenshots at two widths |
| 5. Cutover | Replace `frontend/`, update Dockerfile and Caddyfile if paths change, version bump, changelog, tag | User approval before merge or tag |

## Verification (O3: nothing is "done" without evidence)

- Playwright (headless Chromium) screenshots at phone and desktop width for every view built.
- `npm run type-check` and `npm run test:unit` output reported, not assumed.
- Contrast check on the palette (WCAG AA for text), keyboard focus visible, reduced-motion respected.
- Each rated view logged in ck with the score and date.

## Open questions

1. Confirm the licence stance: layout pattern only, no Color Admin code or assets.
2. Confirm staged rollout (phases 0-3 first), rather than all 21 views at once.
3. Pick a direction: A, B, C, or a mix.
4. Are the current dev server and API runnable here for baseline screenshots (needs backend up on localhost, not 127.0.0.1, per the CORS note)?
5. Who rates? Proposed: user rates 1-5 per pilot view; Claude does not self-rate.

## Decisions update (2026-11-22, later)

- Direction **A (Instrument panel)** chosen. Staged rollout (phases 0-3 first) confirmed.
- Licence stance (layout pattern only, no Color Admin code or assets) stands; not objected to.

## Phase 0 baseline (2026-11-22)

Servers: backend `uv run uvicorn garminview.api.main:create_app --factory --host 127.0.0.1 --port 8000`
(dev DB `backend/garminview.db`, data current to 2026-11-21, no catch-up sync triggered);
frontend `npm run dev -- --host localhost --port 5173`. Use `localhost`, not `127.0.0.1` (CORS).
Note: the backend starts APScheduler with cron jobs at 03:00 (sync) and 04:00 (actalog); stop it
when not in use.

Screenshots (Playwright, headless Chromium): home, sleep, cardio, training, admin at 1440x900
and 390x844, stored in the session scratchpad `baseline/` folder.

Observed in the current UI:

- Light warm-grey canvas, white rounded cards, blue accent, pastel sidebar with line icons,
  small-caps labels, sparkline in every KPI tile. Competent but generic.
- **Defect:** at phone width the 228 px sidebar does not collapse, so the page content is
  squeezed to about 160 px and cut off. v2 must handle this (collapsible sidebar, bottom nav or drawer).
- The Overview leads with a long system-activity log rather than the athlete's data.
- Admin does not reach network idle (long-lived connection), so tests must not wait for it.

User baseline rating (KR4.1, 1-5): **3** (current UI, given 2026-11-22). Target for v2: average 4 or higher on the three pilot views.

## User feedback on baseline screenshots (2026-11-22)

Verbatim summary: "looks wise" (overall impression), less warm and more gray; the font needs to be
less friendly and more straight and professional; wants a completely different app-wide navigation.

Design consequences for Direction A:

- **Color:** cool, neutral grays (no cream or beige undertone). Canvas, panels and borders drawn
  from one desaturated slate-gray ramp; one signal accent; semantic colors used only for status.
- **Type:** replace the rounded, friendly geometric sans with a straight, engineered grotesque
  (candidates to test: IBM Plex Sans with Plex Mono, Archivo, Geist with Geist Mono). Tabular
  numerals for every metric. No rounded terminals.
- **Navigation:** discard the flat 19-item sidebar; see options below.

## Navigation options (decision pending)

Current routes (19 pages) grouped by task, used by every option:

| Section | Pages |
| --- | --- |
| Today | Overview, Recovery and stress |
| Training | Training load, Activities, Running, Intensity minutes, Cardiovascular, Max HR aging |
| Body | Sleep, Weight and body comp, Calories, Nutrition |
| Analysis | Long-term trends, Correlations, Assessments and goals, Athlete profile |
| System | Data quality, Actalog (workouts), Admin |

1. **Icon rail plus section panel.** A 56 px rail with five section icons; selecting one opens a
   panel listing that section's pages. Closest to the Color Admin pattern; always visible; phone
   collapses to a bottom bar of five sections.
2. **Top section bar plus contextual tabs.** Five sections in the header, page tabs under the
   page title, no sidebar, so panels get the full width. Fewest clicks for related pages; wide
   sections (Training has six) need a tab overflow.
3. **Command palette plus pinned boards.** Minimal rail (sections only), Ctrl+K jump-to-anything,
   and user-pinned dashboards on Overview. Most distinctive and fastest for a single expert user;
   weakest discoverability and needs the most new code.

## Decisions update (2026-11-23): navigation and home screen

- Navigation: **option 1, icon rail plus section panel** (56 px rail, 208 px section panel). Options 2 and 3 not chosen; kept on the design canvas for reference.
- First screen (Overview): **calendar of day squares** showing stats plus the date.
- Each square is colour coded twice: **orange #EF6B45 = workout kcal** (sum of logged activity kcal),
  **blue #4FA8D8 = non-workout kcal** (active kcal minus workout kcal, minimum 0). The pair is colourblind-safe.
  The selected metric (steps, sleep, resting HR, body battery, stress, active kcal) sets the large value and a neutral gray shade.
- Prototype: design canvas https://claude.ai/artifact/L2Z7aA3U51WDQR5sVCSJaU (private, Version 7). Real data, 1 Oct to 21 Nov 2026.
  Not yet checked in a browser; user reaction to the calendar pending.

## TODO (paused 2026-11-23)

Awaiting user feedback
- [ ] User reacts to the calendar home (blue bar as calories vs steps; bar scaling linear vs square-root; "Missing watch" 6 Oct counted as workout).

Design
- [ ] Phone artboard for option 1 (bottom bar of five sections, smaller calendar squares). Fixes the baseline defect (sidebar never collapses).
- [ ] Phase 1 style brief: type test (IBM Plex Sans/Mono, Archivo, Geist/Geist Mono), palette with WCAG AA contrast checks, one-page style guide, user sign-off.

Build (after sign-off)
- [ ] Phase 2: scaffold `frontend-v2/` (tokens, light and dark themes, AppShell, rail and section panel, PageHeader, KpiTile, Panel, RangeToggle, DataTable, ChartPanel, ECharts theme). Type-check and unit tests green.
- [ ] Phase 3: pilot views DailyOverview (calendar home), SleepDashboard, Admin. User rates each 1-5 (baseline 3, target average 4 or higher). Playwright screenshots at 1440x900 and 390x844.
- [ ] Phases 4 and 5: rollout of remaining views, then cutover. Version bump, changelog and tag only on merge, with user approval.

Housekeeping
- [ ] Stop the garminview backend and frontend dev servers while paused (scheduler fires at 03:00 and 04:00).
- [ ] This plan file is not committed yet; commit when the user asks.

Pilot (ck rQliJ7w8Gmkz, outside garminview)
- [ ] Install Trilium MCP on iMac, T14Gen3, tabellaria (test POSIX helper under Git Bash, then the PowerShell variant).
- [ ] Re-test recall around 2026-12-03 on rainbozen plus one Windows machine (baseline 33/40, about 33 tool calls).
- [ ] Choose verification gate: Stop hook vs reviewer subagent. RTK and AGENTS.md deferred.

## Decisions update (2026-11-23, after calendar review)

- Calendar home approved. Colour coding revised by the user: **blue = steps, red = total calories for the day, yellow = workout / high-intensity calories**. Replaces the earlier orange (workout kcal) and blue (non-workout kcal) pair.
- Clicking a day square opens a **day detail screen** (a routed page, not only the side panel).
- **Mobile layouts deferred** until desktop development is finished. The phone artboard and bottom bar TODO is parked.
- Consequence for Phase 1: red and yellow are now data colors, so the palette must keep them distinct from status colors (error red, warning amber) and from the amber UI accent. To resolve in the style brief.

## Phase 1 sign-off (2026-11-23)

Style board: https://claude.ai/artifact/M7QrRUX9AuhU3YAtg5jFpQ (private). User: "Looks good."

- Type: **Archivo** (UI) with **JetBrains Mono** (numbers), self-hosted via npm (fontsource), no CDN.
- Theme: **dark only**; light theme dropped.
- Palette: the board's "Normal" palette. Canvas #11151A, panel #181D23, raised #1F252C, border #2A323B, border-strong #3B4652, text #E6EAEF, muted #9AA6B2, accent ice #D4E4F5.
  Data: steps #4DA3E0, total kcal #E5594F, workout kcal #F2C230. Status: ok #46C28A, warn #E08A3A, error #FF6B8A (always with icon and word).
- Rule: hue means data or status; UI chrome uses the ice accent only. Amber accent retired.
- All 12 contrast pairs on the board pass (text 4.5:1, graphics 3:1).
- Open before Phase 2/3: see the decision list in the session (day detail contents, pilot view set, calendar range, intensity-only days, branch and commit).

## Decisions update (2026-11-23, Phase 2 questions answered)

| # | Decision |
| --- | --- |
| 1 | Day detail screen at `/day/:date`: header with date and prev/next, kcal and steps tiles, sleep, heart rate, stress, body battery, logged activities, back link to the month. Built after the calendar, not first. |
| 2 | **Phase 3 starts with the Sleep view only.** Screens are added slowly and deliberately, one at a time. Build order: shell with nav and placeholder home, then Sleep, then rate it. Calendar home, day detail and Admin come later as separate steps. |
| 3 | Calendar is a real month grid with prev/next arrows, opening on the current month. |
| 4 | **Option C: yellow is intensity-based workout kcal on every day**, not only logged workouts. Days with no logged activity get an **icon** that marks "not logged". Exact kcal-from-intensity formula is still open (see below). |
| 5 | New branch `frontend-v2` in the garminview repo; commit locally, do not push. |
| 6 | Dev: `frontend-v2` on port 5174 beside the old UI on 5173, same backend API. Stop the backend when pausing. |
| - | Charts: one shared dark ECharts theme from the data colors, faint grid, emphasized last point, no animated entrances. Tests: new unit tests for new components, type-check green, old tests not ported. |

### Open: intensity-to-kcal formula (needed before the calendar is built)

Evidence from the dev DB (1 Oct to 21 Nov 2026): on logged-workout days, workout kcal is close to the day's active kcal
(for example 12 Oct: 532 workout, 500 active, 78 intensity min), but the ratio of kcal to intensity minutes varies
(6.8 on 12 Oct, 5.5 on 27 Oct, 3.7 on 6 Nov). Five days had 36 to 87 intensity minutes and no logged workout
(20 Oct, 31 Oct, 10 Nov, 12 Nov, 21 Nov). Candidates to test against the data: (a) active kcal on days with at least
20 intensity minutes; (b) intensity minutes times a fitted kcal-per-minute rate. Choose with a check on logged days
(how far the estimate is from the logged kcal). Walking-only days (for example 9 Oct, 22,078 steps, 6 intensity min) must stay near 0.

## Status at pause (2026-11-23)

- Done: plan, direction A, navigation (icon rail plus section panel), calendar prototype, Phase 1 style board signed off.
- Artifacts (private): design canvas https://claude.ai/artifact/L2Z7aA3U51WDQR5sVCSJaU ; style board https://claude.ai/artifact/M7QrRUX9AuhU3YAtg5jFpQ
- Not started: `frontend-v2/` (no branch created yet), Phase 2 scaffold.
- Next action: create branch `frontend-v2`, scaffold `frontend-v2/` (Vite, Vue 3, Pinia, vue-router, ECharts), tokens and fonts (Archivo, JetBrains Mono via fontsource), app shell with icon rail, core components, then the Sleep view. Report type-check and unit test output and a screenshot of the shell.
- Dev servers may still be running on rainbozen (backend 8000, frontend 5173). Stop them before the reboot; they do not survive it anyway.
- Plan file is uncommitted.

## Progress (2026-11-23, Phase 2 and first Phase 3 screen)

- Branch `frontend-v2` created. `frontend-v2/` scaffolded: Vue 3, Vite 8, Pinia, vue-router, vue-echarts; Archivo and JetBrains Mono self-hosted via fontsource.
- Tokens (`src/styles/tokens.css`), ECharts theme (`src/charts/theme.ts`, no animation), shell (icon rail plus section panel), components: PageHeader, Panel, KpiTile with TickScale, RangeToggle, StatusLine.
- Routes are generated from `src/nav/sections.ts`. Page paths avoid the API proxy prefixes; a unit test enforces it.
  Renamed paths that clashed: activities -> /activity-log, nutrition -> /food, assessments -> /goals, admin -> /system-admin, actalog -> /workouts, body -> /weight.
- API calls use relative URLs; the Vite dev proxy (port 5174) forwards API paths to 127.0.0.1:8000, mirroring Caddy. No backend or CORS change.
- Sleep view built: four tiles (last night, score, deep share, REM share) with target bands, nightly duration with 7-night average and 7-9 h band, stage shares, score with bands, recent-nights table. Zero-minute nights are shown as "not recorded".
- Checks: `vue-tsc --build` clean; 16 unit tests pass; `vite build` passes (SleepView chunk 645 kB because it carries ECharts; split later); Playwright 1440x900 shows no console errors and no horizontal overflow.
- Waiting on: user rating (1-5) of the Sleep view.

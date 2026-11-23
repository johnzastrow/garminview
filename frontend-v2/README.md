# garminview frontend v2

A rewrite of the garminview UI, built beside the existing `frontend/` until cutover.
Plan, decisions and status: [docs/plans/2026-11-22-frontend-v2-redesign-plan.md](../docs/plans/2026-11-22-frontend-v2-redesign-plan.md).

Status: preview. 1 of 19 pages built (Sleep). The other pages render a placeholder.

## Run it

The backend must be running on `127.0.0.1:8000` (see the main README).

```bash
cd frontend-v2
npm install
npm run dev        # http://localhost:5174 (the old UI stays on 5173)
```

| Command | What it does |
| --- | --- |
| `npm run dev` | Dev server on port 5174, strict port |
| `npm run type-check` | `vue-tsc --build` |
| `npm run test:unit` | Vitest unit tests (watch mode; add `-- --run` for a single pass) |
| `npm run build` | Type-check and production build to `dist/` |

## How API calls reach the backend

The app calls the API with relative URLs (`/health/sleep`, not `http://...:8000/health/sleep`).

- Dev: the Vite proxy forwards API paths to `127.0.0.1:8000`.
- Production: Caddy does the same, with the same path regex.

The regex lives in `src/nav/apiPrefixes.ts` and is shared by `vite.config.ts`.
No CORS or backend change is needed. `VITE_API_URL` can override the base URL, but leave it empty for normal use.

**Page paths must never start with an API prefix** (`/health`, `/training`, `/body`, `/admin`,
`/activities`, `/assessments`, `/nutrition`, and the others in the regex). A reload on such a path
would go to the API instead of the app. `src/nav/__tests__/routes.spec.ts` fails if a page path clashes.

## Layout

| Path | Contents |
| --- | --- |
| `src/styles/tokens.css` | Design tokens: grays, ice accent, data and status colours, type scale, spacing |
| `src/styles/base.css` | Resets and shared classes (`.num`, `.label`, `.muted`, `.sr-only`) |
| `src/nav/sections.ts` | Navigation model: 5 sections, 19 pages. Routes are generated from it |
| `src/router/index.ts` | Routes; `VIEWS` maps built pages to their view, others get `PlaceholderView` |
| `src/charts/theme.ts` | ECharts module registration, the dark "instrument" theme, `esc()` for tooltip HTML |
| `src/components/shell/` | Icon rail and section panel |
| `src/components/ui/` | PageHeader, Panel, KpiTile, TickScale, RangeToggle, StatusLine |
| `src/stores/range.ts` | Shared date range (30D, 90D, 1Y; default 90D) |
| `src/utils/useRangeData.ts` | Fetch composable: ignores stale responses, generic error message |
| `src/utils/sleep.ts` | Pure sleep helpers (zero-minute nights become "not recorded", rolling mean, formatting) |
| `src/views/` | One file per screen |

## Adding a screen

1. Build the view in `src/views/`.
2. Add it to `VIEWS` in `src/router/index.ts`.
3. Set `built: true` for its page in `src/nav/sections.ts`.
4. Add unit tests for any new helper or component, then run type-check, tests and build.

Screens are added one at a time, and the user rates each one before the next is started.

## Design rules

- Dark only. Archivo for UI text, JetBrains Mono for numbers. Both are self-hosted via fontsource, with no CDN.
- Hue means data or status. UI chrome uses the ice accent and grays only.
- Data colours: steps blue `#4DA3E0`, total kcal red `#E5594F`, workout kcal yellow `#F2C230`, plus the sleep family.
- Status colours are always shown with an icon and a word, never colour alone.
- Charts have no entrance animation. A missing recording is shown as a gap or "Not recorded", never as zero.

## Security notes

- Tooltip HTML from ECharts goes through `esc()`. Do not use `v-html` with API data.
- No secrets in the frontend. Requests send cookies (`withCredentials`) for the existing session model.
- `npm audit` reports 5 moderate findings in the dev-only `@vue/test-utils` chain. They do not ship in the build.

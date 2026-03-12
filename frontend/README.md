# GarminView Frontend

Vue.js 3 frontend for the GarminView fitness data platform.

**Stack:** Vue 3 · Composition API · Pinia · Vue Router · vue-echarts (Apache ECharts) · TypeScript

---

## Development

```bash
npm install
npm run dev        # → http://localhost:5173
```

The dev server proxies API requests to `http://localhost:8000` by default. To override:

```bash
echo "VITE_API_URL=http://localhost:8000" > .env.local
```

The backend must be running — see [../docs/SETUP.md](../docs/SETUP.md).

---

## Build

```bash
npm run build      # output → dist/
npm run preview    # preview the production build locally
```

---

## Tests

```bash
npm run test:unit  # Vitest unit tests
```

---

## Project structure

```
src/
├── assets/          — global CSS (base.css, main.css)
├── components/
│   ├── charts/      — ECharts wrappers (TimeSeriesChart, StackedBarChart,
│   │                  ScatterTrendChart, PMCChart, …)
│   └── ui/          — MetricCard, DateRangePicker, …
├── router/          — Vue Router config (index.ts)
├── stores/          — Pinia stores (dateRange, sync, …)
└── views/           — One component per dashboard route
    ├── DailyOverview.vue
    ├── SleepDashboard.vue
    ├── CardiovascularDashboard.vue
    ├── WeightBodyComp.vue
    ├── ActivitySummary.vue
    ├── RunningDashboard.vue
    ├── RecoveryStress.vue
    ├── NutritionDashboard.vue
    ├── MaxHRAgingDashboard.vue
    └── Admin.vue            — sync controls, schedule, config, MFP upload
```

---

## IDE setup

[VS Code](https://code.visualstudio.com/) + [Vue - Official](https://marketplace.visualstudio.com/items?itemName=Vue.volar) extension (disable Vetur if installed). Enable "Custom Object Formatters" in DevTools for better Pinia/Vue debugging.

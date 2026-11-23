// Navigation model: five task sections, each with its pages (decision 2026-11-22, option 1).
// Routes are generated from this list, so the nav and the router cannot drift apart.
//
// Page paths must never match the backend's API prefixes (see API_PREFIX_RE in vite.config.ts
// and frontend/Caddyfile): a reload on such a path would be proxied to the API instead of
// serving the app. The routes test enforces this.

export type SectionId = "today" | "training" | "body" | "analysis" | "system"

export interface PageDef {
  /** Route name, unique */
  name: string
  /** URL path */
  path: string
  title: string
  /** One line shown under the page title */
  summary: string
  /** False until the v2 screen exists; unbuilt pages render a placeholder */
  built: boolean
}

export interface SectionDef {
  id: SectionId
  title: string
  /** SVG path data for a 20x20 stroke icon */
  icon: string[]
  pages: PageDef[]
}

export const SECTIONS: SectionDef[] = [
  {
    id: "today",
    title: "Today",
    // calendar
    icon: ["M3.5 5.5h13v11h-13z", "M3.5 8.5h13", "M7 3.5v3", "M13 3.5v3", "M7 12h2"],
    pages: [
      { name: "overview", path: "/", title: "Overview", summary: "Calendar of days: steps, total and workout calories.", built: false },
      { name: "recovery", path: "/recovery", title: "Recovery and stress", summary: "Body battery, stress and resting heart rate.", built: false },
    ],
  },
  {
    id: "training",
    title: "Training",
    // pulse trace
    icon: ["M2.5 10.5h3.5l2-5 3.5 9 2-4h4"],
    pages: [
      { name: "training-load", path: "/training-load", title: "Training load", summary: "Acute and chronic load, form.", built: false },
      { name: "activity-log", path: "/activity-log", title: "Activities", summary: "Every logged activity.", built: false },
      { name: "running", path: "/running", title: "Running", summary: "Pace, distance and cadence.", built: false },
      { name: "intensity", path: "/intensity", title: "Intensity minutes", summary: "Moderate and vigorous minutes per week.", built: false },
      { name: "cardio", path: "/cardio", title: "Cardiovascular", summary: "Heart rate, HRV and VO2max.", built: false },
      { name: "max-hr", path: "/max-hr", title: "Max HR aging", summary: "Maximum heart rate over the years.", built: false },
    ],
  },
  {
    id: "body",
    title: "Body",
    // crescent moon (sleep is the first built page here)
    icon: ["M13.5 3.8a6.5 6.5 0 1 0 2.7 9.9 5.2 5.2 0 0 1-2.7-9.9z"],
    pages: [
      { name: "sleep", path: "/sleep", title: "Sleep", summary: "Duration, stages and score, night by night.", built: true },
      { name: "weight", path: "/weight", title: "Weight and body comp", summary: "Weight, body fat and muscle mass.", built: false },
      { name: "calories", path: "/calories", title: "Calories", summary: "Total, active and resting calories.", built: false },
      { name: "food", path: "/food", title: "Nutrition", summary: "Food log and macros.", built: false },
    ],
  },
  {
    id: "analysis",
    title: "Analysis",
    // axes with trend
    icon: ["M3.5 3.5v13h13", "M6 13l3.5-4 3 2.5 4-6"],
    pages: [
      { name: "trends", path: "/trends", title: "Long-term trends", summary: "Metrics normalized over years.", built: false },
      { name: "correlations", path: "/correlations", title: "Correlations", summary: "How one metric moves with another.", built: false },
      { name: "goals", path: "/goals", title: "Assessments and goals", summary: "Fitness assessments and targets.", built: false },
      { name: "profile", path: "/profile", title: "Athlete profile", summary: "Zones, thresholds and personal data.", built: false },
    ],
  },
  {
    id: "system",
    title: "System",
    // sliders
    icon: ["M4 5.5h12", "M4 10h12", "M4 14.5h12", "M7.5 4v3", "M12.5 8.5v3", "M9 13v3"],
    pages: [
      { name: "data-quality", path: "/data-quality", title: "Data quality", summary: "Gaps and anomalies in the data.", built: false },
      { name: "workouts", path: "/workouts", title: "Actalog workouts", summary: "Workouts imported from Actalog.", built: false },
      { name: "system-admin", path: "/system-admin", title: "Admin", summary: "Sync, jobs and logs.", built: false },
    ],
  },
]

export const ALL_PAGES: (PageDef & { section: SectionId })[] = SECTIONS.flatMap((s) =>
  s.pages.map((p) => ({ ...p, section: s.id })),
)

export function sectionOfPage(name: string | null | undefined): SectionId {
  return ALL_PAGES.find((p) => p.name === name)?.section ?? "today"
}

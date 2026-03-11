<script setup lang="ts">
import { RouterView, RouterLink, useRoute } from 'vue-router'
const route = useRoute()

const nav = [
  { to: '/',            label: 'Overview',      icon: 'M3 12l9-9 9 9M5 10v9a1 1 0 001 1h4v-5h4v5h4a1 1 0 001-1v-9' },
  { to: '/sleep',       label: 'Sleep',         icon: 'M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z' },
  { to: '/body',        label: 'Body',          icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
  { to: '/cardio',      label: 'Cardiovascular',icon: 'M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z' },
  { to: '/training',    label: 'Training Load', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { to: '/activities',  label: 'Activities',    icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
  { to: '/running',     label: 'Running',       icon: 'M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A8 8 0 0117.657 18.657z' },
  { to: '/recovery',    label: 'Recovery',      icon: 'M4.5 10.5L12 3l7.5 7.5M12 3v18' },
  { to: '/trends',      label: 'Long-term',     icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
  { to: '/max-hr-aging',label: 'Max HR Aging',  icon: 'M3 17l4-8 4 4 4-6 4 4M3 21h18' },
  { to: '/calories',    label: 'Calories',      icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z' },
  { to: '/intensity',   label: 'Intensity Mins',icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
  { to: '/nutrition',   label: 'Nutrition',     icon: 'M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 0v10m0 0l-3-3m3 3l3-3' },
  { to: '/correlations',label: 'Correlations',  icon: 'M7 12l5-5 5 5M7 17l5-5 5 5' },
  { to: '/assessments', label: 'Assessments',   icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4' },
  { to: '/data-quality',label: 'Data Quality',  icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  { to: '/profile',     label: 'Athlete Profile',icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
  { to: '/admin',       label: 'Admin',         icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
]
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"/>
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/>
        </svg>
      </div>
      <span class="brand-name">GarminView</span>
    </div>

    <nav>
      <RouterLink
        v-for="item in nav"
        :key="item.to"
        :to="item.to"
        class="nav-item"
        :class="{ active: route.path === item.to }"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
          <path v-for="(d, i) in item.icon.split('M').filter(Boolean)" :key="i" :d="'M' + d" />
        </svg>
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>
  </aside>

  <main class="content">
    <RouterView />
  </main>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-w);
  min-height: 100vh;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  padding: 20px 12px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 20px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 12px;
}

.brand-mark {
  width: 28px;
  height: 28px;
  background: var(--accent);
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}
.brand-mark svg { width: 16px; height: 16px; stroke-width: 1.5; }

.brand-name {
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text);
}

nav {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--muted);
  transition: background 0.12s, color 0.12s;
}
.nav-item svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}
.nav-item:hover {
  background: var(--bg);
  color: var(--text);
}
.nav-item.active {
  background: var(--accent-light);
  color: var(--accent);
  font-weight: 600;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 32px 36px;
}
</style>

import "@fontsource/archivo/400.css"
import "@fontsource/archivo/500.css"
import "@fontsource/archivo/600.css"
import "@fontsource/jetbrains-mono/400.css"
import "@fontsource/jetbrains-mono/500.css"
import "./styles/tokens.css"
import "./styles/base.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import App from "./App.vue"
import router from "./router"

// Charts draw text on a canvas, which cannot swap fonts after drawing. Load the faces the
// charts use before mounting; fall through after a short wait so a font failure never blocks the app.
async function fontsReady() {
  const loads = Promise.all([
    document.fonts.load('400 11px "JetBrains Mono"'),
    document.fonts.load('400 14px "Archivo"'),
  ])
  await Promise.race([loads, new Promise((r) => setTimeout(r, 1500))]).catch(() => undefined)
}

fontsReady().then(() => {
  createApp(App).use(createPinia()).use(router).mount("#app")
})

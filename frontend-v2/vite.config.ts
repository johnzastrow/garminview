import { fileURLToPath, URL } from "node:url"
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import { API_PREFIX_RE } from "./src/nav/apiPrefixes.ts"

// The app calls the API with relative URLs; the dev proxy forwards API paths, so no CORS
// change is needed for port 5174.

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: "localhost",
    port: 5174,
    strictPort: true,
    proxy: {
      [API_PREFIX_RE]: { target: "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
})

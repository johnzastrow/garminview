import axios from "axios"

// Relative URLs by default: the Vite dev proxy (dev) and Caddy (production) forward API
// paths to the backend, so the browser never makes a cross-origin call.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "",
  withCredentials: true,
  timeout: 20000,
})

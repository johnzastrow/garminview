import { describe, it, expect } from "vitest"
import { ALL_PAGES, SECTIONS } from "../sections"
import { API_PREFIX_RE } from "../apiPrefixes"

describe("navigation model", () => {
  it("never uses a page path that the API proxy would capture", () => {
    const re = new RegExp(API_PREFIX_RE)
    const clashes = ALL_PAGES.filter((p) => re.test(p.path)).map((p) => p.path)
    expect(clashes).toEqual([])
  })
  it("has unique route names and paths", () => {
    expect(new Set(ALL_PAGES.map((p) => p.name)).size).toBe(ALL_PAGES.length)
    expect(new Set(ALL_PAGES.map((p) => p.path)).size).toBe(ALL_PAGES.length)
  })
  it("keeps the five sections and the 19 pages of the current app", () => {
    expect(SECTIONS.map((s) => s.id)).toEqual(["today", "training", "body", "analysis", "system"])
    expect(ALL_PAGES).toHaveLength(19)
  })
  it("the regex really matches API paths (guards against a broken pattern)", () => {
    const re = new RegExp(API_PREFIX_RE)
    expect(re.test("/health/sleep")).toBe(true)
    expect(re.test("/training")).toBe(true)
    expect(re.test("/training-load")).toBe(false)
  })
})

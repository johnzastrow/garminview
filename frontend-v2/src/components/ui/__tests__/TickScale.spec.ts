import { describe, it, expect } from "vitest"
import { mount } from "@vue/test-utils"
import TickScale from "../TickScale.vue"

describe("TickScale", () => {
  it("places the marker by value and clamps it to the scale", () => {
    const at = (value: number | null) =>
      mount(TickScale, { props: { min: 4, max: 10, value } }).find(".marker")
    expect(at(7).attributes("style")).toContain("left: 50%")
    expect(at(12).attributes("style")).toContain("left: 100%")
    expect(at(null).exists()).toBe(false)
  })
  it("draws the target band between its bounds", () => {
    const w = mount(TickScale, { props: { min: 0, max: 40, value: 18, band: [15, 25] as [number, number] } })
    const style = w.find(".band").attributes("style")
    expect(style).toContain("left: 37.5%")
    expect(style).toContain("width: 25%")
  })
  it("renders divisions + 1 ticks", () => {
    const w = mount(TickScale, { props: { min: 0, max: 1, value: 0.5, divisions: 8 } })
    expect(w.findAll(".tick")).toHaveLength(9)
  })
})

import { describe, it, expect } from 'vitest'
import {
  mToMi, kmToMi, kgToLbs, mToFt, paceKmToMi, msToMph, fmtPace,
  DIST_UNIT, WEIGHT_UNIT, ELEV_UNIT, PACE_UNIT, SPEED_UNIT,
} from '../units'

describe('units conversions', () => {
  describe('null / undefined handling (every numeric helper)', () => {
    for (const fn of [mToMi, kmToMi, kgToLbs, mToFt, paceKmToMi, msToMph]) {
      it(`${fn.name} returns null for null/undefined`, () => {
        expect(fn(null)).toBeNull()
        expect(fn(undefined)).toBeNull()
      })
    }
  })

  it('mToMi: metres → miles', () => {
    expect(mToMi(1609.34)).toBe(1)        // exactly one mile
    expect(mToMi(0)).toBe(0)
    expect(mToMi(5000)).toBeCloseTo(3.11, 2)
    expect(mToMi(1609.34, 4)).toBeCloseTo(1, 4)
  })

  it('kmToMi: km → miles', () => {
    expect(kmToMi(1.60934)).toBe(1)
    expect(kmToMi(10)).toBeCloseTo(6.21, 2)
  })

  it('kgToLbs: kg → lbs (1dp default)', () => {
    expect(kgToLbs(1)).toBe(2.2)
    expect(kgToLbs(100)).toBe(220.5)
    expect(kgToLbs(0)).toBe(0)
  })

  it('mToFt: metres → feet (0dp default)', () => {
    expect(mToFt(1)).toBe(3)
    expect(mToFt(100)).toBe(328)
    expect(mToFt(100, 1)).toBeCloseTo(328.1, 1)
  })

  it('paceKmToMi: min/km → min/mi', () => {
    expect(paceKmToMi(1)).toBe(1.61)
    expect(paceKmToMi(5)).toBeCloseTo(8.05, 2)
  })

  it('msToMph: m/s → mph', () => {
    expect(msToMph(1)).toBe(2.2)
    expect(msToMph(10)).toBe(22.4)
  })

  describe('fmtPace: decimal minutes → "M:SS"', () => {
    it('formats whole and fractional minutes', () => {
      expect(fmtPace(9.25)).toBe('9:15')
      expect(fmtPace(5)).toBe('5:00')
      expect(fmtPace(9.5)).toBe('9:30')
      expect(fmtPace(0)).toBe('0:00')
    })
    it('zero-pads seconds < 10', () => {
      expect(fmtPace(8 + 5 / 60)).toBe('8:05')
    })
    it('returns em-dash for null/undefined', () => {
      expect(fmtPace(null)).toBe('—')
      expect(fmtPace(undefined)).toBe('—')
    })
  })

  it('exposes stable unit-label constants', () => {
    expect([DIST_UNIT, WEIGHT_UNIT, ELEV_UNIT, PACE_UNIT, SPEED_UNIT])
      .toEqual(['mi', 'lbs', 'ft', 'min/mi', 'mph'])
  })
})

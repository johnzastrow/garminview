import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useCounterStore } from '../counter'

describe('counter store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('starts at zero', () => {
    const s = useCounterStore()
    expect(s.count).toBe(0)
    expect(s.doubleCount).toBe(0)
  })

  it('increment() bumps the count and doubleCount tracks it', () => {
    const s = useCounterStore()
    s.increment()
    expect(s.count).toBe(1)
    expect(s.doubleCount).toBe(2)
    s.increment()
    expect(s.count).toBe(2)
    expect(s.doubleCount).toBe(4)
  })
})

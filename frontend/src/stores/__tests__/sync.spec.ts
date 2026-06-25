import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSyncStore } from '../sync'

// Minimal EventSource stub (jsdom has none). Captures the latest instance so the
// test can drive onmessage as the server SSE stream would.
class MockEventSource {
  static last: MockEventSource | null = null
  url: string
  onmessage: ((e: { data: string }) => void) | null = null
  constructor(url: string) { this.url = url; MockEventSource.last = this }
  emit(payload: unknown) { this.onmessage?.({ data: JSON.stringify(payload) }) }
}

describe('sync store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    MockEventSource.last = null
    vi.stubGlobal('EventSource', MockEventSource)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('starts idle', () => {
    const s = useSyncStore()
    expect(s.status).toBe('idle')
    expect(s.lastSync).toBeNull()
    expect(s.progress).toBe('')
  })

  it('connectSSE subscribes to the sync stream', () => {
    const s = useSyncStore()
    s.connectSSE()
    expect(MockEventSource.last?.url).toBe('/sync/stream')
  })

  it('applies streamed status + message updates', () => {
    const s = useSyncStore()
    s.connectSSE()
    MockEventSource.last!.emit({ status: 'running', message: 'syncing activities' })
    expect(s.status).toBe('running')
    expect(s.progress).toBe('syncing activities')
  })

  it('defaults progress to empty string when message omitted', () => {
    const s = useSyncStore()
    s.connectSSE()
    MockEventSource.last!.emit({ status: 'error' })
    expect(s.status).toBe('error')
    expect(s.progress).toBe('')
  })
})

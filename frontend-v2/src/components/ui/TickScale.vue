<template>
  <div class="scale" role="img" :aria-label="ariaLabel">
    <span v-if="bandStyle" class="band" :style="bandStyle"></span>
    <span v-for="t in ticks" :key="t.pos" class="tick" :class="{ major: t.major }" :style="{ left: `${t.pos}%` }"></span>
    <span v-if="markerPos != null" class="marker" :style="{ left: `${markerPos}%`, background: color }"></span>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"

// Signature element of Direction A: a gauge-style tick scale along the bottom edge of a tile.
const props = withDefaults(
  defineProps<{
    min: number
    max: number
    value: number | null
    /** Optional target band [low, high], drawn as a faint fill */
    band?: [number, number]
    /** Number of minor divisions */
    divisions?: number
    color?: string
    ariaLabel?: string
  }>(),
  { divisions: 10, color: "var(--accent)", ariaLabel: "" },
)

const pct = (v: number) => Math.min(100, Math.max(0, ((v - props.min) / (props.max - props.min)) * 100))

const ticks = computed(() =>
  Array.from({ length: props.divisions + 1 }, (_, i) => ({
    pos: (i / props.divisions) * 100,
    major: i === 0 || i === props.divisions || i * 2 === props.divisions,
  })),
)
const markerPos = computed(() => (props.value == null ? null : pct(props.value)))
const bandStyle = computed(() => {
  if (!props.band) return null
  const a = pct(props.band[0])
  const b = pct(props.band[1])
  return { left: `${a}%`, width: `${b - a}%` }
})
</script>

<style scoped>
.scale {
  position: relative;
  height: 16px;
  border-top: 1px solid var(--border);
}
.band {
  position: absolute;
  top: 0;
  bottom: 0;
  background: rgba(212, 228, 245, 0.07);
}
.tick {
  position: absolute;
  bottom: 0;
  width: 1px;
  height: 5px;
  background: var(--border-strong);
}
.tick.major {
  height: 9px;
  background: var(--faint);
}
.marker {
  position: absolute;
  bottom: 0;
  width: 2px;
  height: 14px;
  margin-left: -1px;
}
</style>

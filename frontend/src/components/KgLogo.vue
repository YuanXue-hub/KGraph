<template>
  <svg :width="size" :height="size" viewBox="0 0 48 48" fill="none" class="kg-logo">
    <defs>
      <!-- 中心节点品牌渐变 -->
      <linearGradient id="kgCore" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#6366f1" />
        <stop offset="100%" stop-color="#8b5cf6" />
      </linearGradient>
      <!-- 外围节点渐变 -->
      <linearGradient id="kgNode" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#a5b4fc" />
        <stop offset="100%" stop-color="#c4b5fd" />
      </linearGradient>
      <!-- 中心光晕滤镜 -->
      <filter id="kgGlow" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="1.2" result="blur" />
        <feMerge>
          <feMergeNode in="blur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>

    <!-- 六边形关系骨架（外围节点间连线） -->
    <g class="kg-edges" stroke="#cbd5e1" stroke-width="1" fill="none" stroke-linecap="round">
      <line x1="24" y1="8" x2="37.86" y2="16" />
      <line x1="37.86" y1="16" x2="37.86" y2="32" />
      <line x1="37.86" y1="32" x2="24" y2="40" />
      <line x1="24" y1="40" x2="10.14" y2="32" />
      <line x1="10.14" y1="32" x2="10.14" y2="16" />
      <line x1="10.14" y1="16" x2="24" y2="8" />
    </g>

    <!-- 中心放射连线（中心节点 → 外围节点） -->
    <g class="kg-rays" stroke="#a5b4fc" stroke-width="1" fill="none" stroke-linecap="round" opacity="0.7">
      <line x1="24" y1="24" x2="24" y2="8" />
      <line x1="24" y1="24" x2="37.86" y2="16" />
      <line x1="24" y1="24" x2="37.86" y2="32" />
      <line x1="24" y1="24" x2="24" y2="40" />
      <line x1="24" y1="24" x2="10.14" y2="32" />
      <line x1="24" y1="24" x2="10.14" y2="16" />
    </g>

    <!-- 外围 6 个知识节点 -->
    <g class="kg-nodes">
      <circle cx="24" cy="8" r="2.6" fill="url(#kgNode)" class="kg-node n1" />
      <circle cx="37.86" cy="16" r="2.6" fill="url(#kgNode)" class="kg-node n2" />
      <circle cx="37.86" cy="32" r="2.6" fill="url(#kgNode)" class="kg-node n3" />
      <circle cx="24" cy="40" r="2.6" fill="url(#kgNode)" class="kg-node n4" />
      <circle cx="10.14" cy="32" r="2.6" fill="url(#kgNode)" class="kg-node n5" />
      <circle cx="10.14" cy="16" r="2.6" fill="url(#kgNode)" class="kg-node n6" />
    </g>

    <!-- 中心核心节点（认知中枢） -->
    <circle cx="24" cy="24" r="5.5" fill="url(#kgCore)" filter="url(#kgGlow)" class="kg-core" />
    <circle cx="24" cy="24" r="2.2" fill="#ffffff" opacity="0.85" class="kg-core-inner" />
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  size?: number
}>(), {
  size: 48
})
</script>

<style scoped>
.kg-logo {
  display: inline-block;
}

/* 中心节点呼吸脉冲 */
.kg-core {
  transform-origin: 24px 24px;
  transform-box: fill-box;
  animation: corePulse 3s ease-in-out infinite;
}
.kg-core-inner {
  animation: innerBlink 3s ease-in-out infinite;
}
@keyframes corePulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.12); opacity: 0.92; }
}
@keyframes innerBlink {
  0%, 100% { opacity: 0.85; }
  50% { opacity: 0.55; }
}

/* 外围节点错位闪烁（数据流动感） */
.kg-node {
  transform-box: fill-box;
  transform-origin: center;
}
.n1 { animation: nodeBlink 3s ease-in-out 0s infinite; }
.n2 { animation: nodeBlink 3s ease-in-out 0.5s infinite; }
.n3 { animation: nodeBlink 3s ease-in-out 1s infinite; }
.n4 { animation: nodeBlink 3s ease-in-out 1.5s infinite; }
.n5 { animation: nodeBlink 3s ease-in-out 2s infinite; }
.n6 { animation: nodeBlink 3s ease-in-out 2.5s infinite; }
@keyframes nodeBlink {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.85); }
}

/* 中心放射线流动 */
.kg-rays line {
  animation: rayFlow 4s ease-in-out infinite;
}
.kg-rays line:nth-child(1) { animation-delay: 0s; }
.kg-rays line:nth-child(2) { animation-delay: 0.4s; }
.kg-rays line:nth-child(3) { animation-delay: 0.8s; }
.kg-rays line:nth-child(4) { animation-delay: 1.2s; }
.kg-rays line:nth-child(5) { animation-delay: 1.6s; }
.kg-rays line:nth-child(6) { animation-delay: 2s; }
@keyframes rayFlow {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 0.85; }
}
</style>

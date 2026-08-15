<template>
  <div class="landing-page" ref="pageRef" @mousemove="onMouseMove">
    <!-- 3D 粒子网络 Canvas -->
    <canvas ref="canvasRef" class="particle-canvas"></canvas>

    <!-- 渐变遮罩 -->
    <div class="overlay-gradient"></div>

    <!-- 顶部品牌 -->
    <div class="brand-top" :class="{ 'fade-in': entered }">
      <KgLogo :size="32" />
      <span class="brand-text">KGraph</span>
    </div>

    <!-- 中心内容 -->
    <div class="hero-content" :class="{ 'fade-in': entered }">
      <h1 class="hero-title">
        <span class="title-line">知识图谱</span>
        <span class="title-line gradient-text">智能认知引擎</span>
      </h1>
      <p class="hero-subtitle">
        一站式知识图谱构建、管理与可视化探索平台，驱动数据智能生产力
      </p>

      <!-- 特性标签 -->
      <div class="feature-tags">
        <div class="tag" v-for="(tag, i) in tags" :key="i" :style="{ animationDelay: `${0.8 + i * 0.15}s` }">
          <span class="tag-icon">{{ tag.icon }}</span>
          <span class="tag-label">{{ tag.label }}</span>
        </div>
      </div>

      <!-- CTA 按钮 -->
      <button class="cta-button" @click="enterSystem">
        <span class="cta-text">进入系统</span>
        <span class="cta-arrow">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </span>
        <div class="cta-glow"></div>
      </button>

      <!-- 底部提示 -->
      <p class="scroll-hint">点击按钮进入管理系统</p>
    </div>

    <!-- 底部信息 -->
    <div class="footer-info" :class="{ 'fade-in': entered }">
      <span>Powered by LangGraph · Vue3 · Spring Boot</span>
    </div>

    <!-- 过渡遮罩 -->
    <Transition name="curtain">
      <div v-if="leaving" class="curtain-overlay"></div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import KgLogo from '@/components/KgLogo.vue'

const router = useRouter()
const canvasRef = ref<HTMLCanvasElement>()
const pageRef = ref<HTMLDivElement>()
const entered = ref(false)
const leaving = ref(false)

const tags = [
  { icon: '◆', label: '知识抽取' },
  { icon: '◇', label: '图谱探索' },
  { icon: '◈', label: '智能问答' },
  { icon: '◉', label: '模型训练' }
]

// === 3D 粒子系统 ===
interface Particle3D {
  x: number; y: number; z: number
  vx: number; vy: number; vz: number
  size: number; color: string
}

let particles: Particle3D[] = []
let animId = 0
let mouseX = 0, mouseY = 0
let targetRotX = 0, targetRotY = 0
let rotX = 0, rotY = 0
let cw = 0, ch = 0
const FOCAL = 600 // 透视焦距
const NUM_PARTICLES = 120

const COLORS = ['#4F6BFF', '#8B5CF6', '#3B82F6', '#06B6D4', '#A78BFA', '#60A5FA']

function initParticles() {
  particles = []
  for (let i = 0; i < NUM_PARTICLES; i++) {
    const r = 200 + Math.random() * 250
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)
    particles.push({
      x: r * Math.sin(phi) * Math.cos(theta),
      y: r * Math.sin(phi) * Math.sin(theta),
      z: r * Math.cos(phi),
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      vz: (Math.random() - 0.5) * 0.3,
      size: 1.5 + Math.random() * 3,
      color: COLORS[Math.floor(Math.random() * COLORS.length)]
    })
  }
}

function project(p: Particle3D, rotX: number, rotY: number) {
  // 绕 Y 轴旋转
  let x = p.x * Math.cos(rotY) - p.z * Math.sin(rotY)
  let z = p.x * Math.sin(rotY) + p.z * Math.cos(rotY)
  let y = p.y
  // 绕 X 轴旋转
  const y2 = y * Math.cos(rotX) - z * Math.sin(rotX)
  const z2 = y * Math.sin(rotX) + z * Math.cos(rotX)
  // 透视投影
  const scale = FOCAL / (FOCAL + z2 + 400)
  return {
    sx: cw / 2 + x * scale,
    sy: ch / 2 + y2 * scale,
    scale,
    z: z2
  }
}

function animate() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')!

  // 平滑追踪鼠标
  rotX += (targetRotX - rotX) * 0.05
  rotY += (targetRotY - rotY) * 0.05
  // 自动旋转
  targetRotY += 0.002

  // 拖尾效果
  ctx.fillStyle = 'rgba(8, 10, 20, 0.15)'
  ctx.fillRect(0, 0, cw, ch)

  // 更新粒子
  for (const p of particles) {
    p.x += p.vx
    p.y += p.vy
    p.z += p.vz
    // 边界回弹
    const d = Math.sqrt(p.x * p.x + p.y * p.y + p.z * p.z)
    if (d > 500 || d < 150) {
      p.vx *= -1; p.vy *= -1; p.vz *= -1
    }
  }

  // 投影
  const projected = particles.map(p => ({ ...project(p, rotX, rotY), color: p.color, size: p.size }))

  // 绘制连线（近粒子之间）
  ctx.lineWidth = 0.5
  for (let i = 0; i < projected.length; i++) {
    for (let j = i + 1; j < projected.length; j++) {
      const dx = projected[i].sx - projected[j].sx
      const dy = projected[i].sy - projected[j].sy
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist < 120) {
        const alpha = (1 - dist / 120) * 0.15 * Math.min(projected[i].scale, projected[j].scale)
        ctx.strokeStyle = `rgba(79, 107, 255, ${alpha})`
        ctx.beginPath()
        ctx.moveTo(projected[i].sx, projected[i].sy)
        ctx.lineTo(projected[j].sx, projected[j].sy)
        ctx.stroke()
      }
    }
  }

  // 绘制粒子
  for (const p of projected) {
    const r = p.size * p.scale
    if (r < 0.3) continue
    // 光晕
    const grad = ctx.createRadialGradient(p.sx, p.sy, 0, p.sx, p.sy, r * 4)
    grad.addColorStop(0, p.color)
    grad.addColorStop(0.3, p.color + '80')
    grad.addColorStop(1, 'transparent')
    ctx.fillStyle = grad
    ctx.globalAlpha = Math.min(p.scale * 0.8, 1)
    ctx.beginPath()
    ctx.arc(p.sx, p.sy, r * 4, 0, Math.PI * 2)
    ctx.fill()
    // 核心
    ctx.globalAlpha = 1
    ctx.fillStyle = p.color
    ctx.beginPath()
    ctx.arc(p.sx, p.sy, r, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.globalAlpha = 1

  animId = requestAnimationFrame(animate)
}

function resizeCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  cw = canvas.width = window.innerWidth
  ch = canvas.height = window.innerHeight
}

function onMouseMove(e: MouseEvent) {
  const cx = window.innerWidth / 2
  const cy = window.innerHeight / 2
  targetRotY = (e.clientX - cx) / cx * 0.3
  targetRotX = -(e.clientY - cy) / cy * 0.2
}

function enterSystem() {
  leaving.value = true
  setTimeout(() => {
    router.push('/login')
  }, 800)
}

onMounted(() => {
  resizeCanvas()
  initParticles()
  animate()
  // 触发入场动画
  requestAnimationFrame(() => {
    entered.value = true
  })
  window.addEventListener('resize', resizeCanvas)
})

onUnmounted(() => {
  cancelAnimationFrame(animId)
  window.removeEventListener('resize', resizeCanvas)
})
</script>

<style scoped>
.landing-page {
  position: fixed;
  inset: 0;
  background: radial-gradient(ellipse at center, #0a0e1a 0%, #050708 100%);
  overflow: hidden;
  cursor: default;
}

.particle-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
}

.overlay-gradient {
  position: absolute;
  inset: 0;
  z-index: 1;
  background:
    radial-gradient(ellipse at 50% 40%, transparent 0%, rgba(5, 7, 8, 0.6) 70%),
    linear-gradient(to bottom, rgba(5, 7, 8, 0.3) 0%, transparent 30%, transparent 70%, rgba(5, 7, 8, 0.8) 100%);
  pointer-events: none;
}

/* === 品牌顶部 === */
.brand-top {
  position: absolute;
  top: 32px;
  left: 40px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 10px;
  opacity: 0;
  transform: translateY(-20px);
  transition: opacity 0.8s ease 0.2s, transform 0.8s ease 0.2s;
}
.brand-top.fade-in {
  opacity: 1;
  transform: translateY(0);
}
.brand-icon {
  filter: drop-shadow(0 0 8px rgba(79, 107, 255, 0.5));
}
.brand-text {
  font-size: 18px;
  font-weight: 600;
  color: #e2e8f0;
  letter-spacing: 1px;
}

/* === 中心内容 === */
.hero-content {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
  text-align: center;
  width: 90%;
  max-width: 640px;
  opacity: 0;
  transition: opacity 1s ease 0.4s;
}
.hero-content.fade-in {
  opacity: 1;
}

.hero-title {
  margin: 0 0 16px;
  line-height: 1.15;
}
.title-line {
  display: block;
  font-size: clamp(36px, 6vw, 64px);
  font-weight: 800;
  letter-spacing: 2px;
  animation: titleSlideIn 0.8s ease both;
}
.title-line:first-child {
  color: #e2e8f0;
  animation-delay: 0.5s;
}
.gradient-text {
  background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 50%, #06b6d4 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation-delay: 0.7s;
}

@keyframes titleSlideIn {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

.hero-subtitle {
  font-size: clamp(14px, 1.8vw, 17px);
  color: #94a3b8;
  margin: 0 auto 32px;
  max-width: 500px;
  line-height: 1.6;
  opacity: 0;
  animation: fadeInUp 0.8s ease 1s both;
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

/* === 特性标签 === */
.feature-tags {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 36px;
  flex-wrap: wrap;
}
.tag {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(10px);
  opacity: 0;
  animation: fadeInUp 0.6s ease both;
  transition: border-color 0.3s, background 0.3s;
}
.tag:hover {
  border-color: rgba(79, 107, 255, 0.4);
  background: rgba(79, 107, 255, 0.08);
}
.tag-icon {
  font-size: 12px;
  color: #60a5fa;
}
.tag-label {
  font-size: 13px;
  color: #cbd5e1;
  font-weight: 500;
}

/* === CTA 按钮 === */
.cta-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 14px 40px;
  border: none;
  border-radius: 30px;
  background: linear-gradient(135deg, #4F6BFF 0%, #8B5CF6 100%);
  color: white;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  overflow: hidden;
  opacity: 0;
  animation: fadeInUp 0.8s ease 1.4s both;
  transition: transform 0.3s, box-shadow 0.3s;
  box-shadow: 0 0 20px rgba(79, 107, 255, 0.3);
}
.cta-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(79, 107, 255, 0.5);
}
.cta-button:active {
  transform: translateY(0);
}
.cta-arrow {
  display: flex;
  transition: transform 0.3s;
}
.cta-button:hover .cta-arrow {
  transform: translateX(4px);
}
.cta-glow {
  position: absolute;
  top: 0;
  left: -100%;
  width: 60%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  animation: glowSlide 3s ease-in-out infinite;
}
@keyframes glowSlide {
  0%, 100% { left: -100%; }
  50% { left: 200%; }
}

.scroll-hint {
  margin-top: 20px;
  font-size: 12px;
  color: #475569;
  opacity: 0;
  animation: fadeInUp 0.8s ease 1.8s both;
}

/* === 底部 === */
.footer-info {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  font-size: 12px;
  color: #334155;
  white-space: nowrap;
  opacity: 0;
  transition: opacity 1s ease 1s;
}
.footer-info.fade-in {
  opacity: 1;
}

/* === 过渡遮罩 === */
.curtain-overlay {
  position: absolute;
  inset: 0;
  z-index: 100;
  background: radial-gradient(ellipse at center, #4F6BFF 0%, #0a0e1a 100%);
  pointer-events: none;
}
.curtain-enter-active {
  transition: opacity 0.8s ease;
}
.curtain-enter-from {
  opacity: 0;
}
.curtain-enter-to {
  opacity: 1;
}

/* === 响应式 === */
@media (max-width: 768px) {
  .brand-top {
    top: 20px;
    left: 20px;
  }
  .feature-tags {
    gap: 8px;
  }
  .tag {
    padding: 5px 12px;
    font-size: 12px;
  }
}
</style>

<template>
  <div class="entry-page" ref="pageRef" @mousemove="onMouseMove">
    <!-- 3D 粒子网络 Canvas -->
    <canvas ref="canvasRef" class="particle-canvas"></canvas>

    <!-- 顶部品牌 -->
    <div class="brand-top" :class="{ 'fade-in': entered }">
      <KgLogo :size="32" />
      <span class="brand-text">KGraph</span>
    </div>

    <!-- 英雄文案（State 1） -->
    <Transition name="hero-fade">
      <div v-if="!showLogin" class="hero-content" :class="{ 'fade-in': entered }">
        <h1 class="hero-title">
          <span class="title-line">知识图谱</span>
          <span class="title-line gradient-text">智能认知引擎</span>
        </h1>
        <p class="hero-subtitle">
          一站式知识图谱构建、管理与可视化探索平台，驱动数据智能生产力
        </p>
        <div class="feature-tags">
          <div class="tag" v-for="(tag, i) in tags" :key="i" :style="{ animationDelay: `${0.8 + i * 0.15}s` }">
            <span class="tag-icon">{{ tag.icon }}</span>
            <span class="tag-label">{{ tag.label }}</span>
          </div>
        </div>
        <button class="cta-button" @click="showLogin = true">
          <span class="cta-text">进入探索</span>
          <span class="cta-arrow">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
          <div class="cta-glow"></div>
        </button>
      </div>
    </Transition>

    <!-- 登录卡片（State 2） -->
    <Transition name="login-fade">
      <div v-if="showLogin" class="login-wrapper">
        <div class="login-card">
          <div class="login-header">
            <KgLogo :size="56" class="login-logo" />
            <h2 class="login-title">欢迎回来</h2>
            <p class="login-subtitle">登录以继续使用 KGraph</p>
          </div>
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            class="login-form"
            @keyup.enter="handleLogin"
          >
            <el-form-item prop="userAccount">
              <el-input v-model="form.userAccount" placeholder="请输入账号" size="large" :prefix-icon="User" />
            </el-form-item>
            <el-form-item prop="userPassword">
              <el-input v-model="form.userPassword" type="password" placeholder="请输入密码" size="large" :prefix-icon="Lock" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" size="large" :loading="userStore.loading" class="login-btn" @click="handleLogin">
                登 录
              </el-button>
            </el-form-item>
            <div class="login-footer">
              <span>还没有账号？</span>
              <el-button type="primary" link @click="openRegister">立即注册</el-button>
            </div>
          </el-form>
          <!-- 返回按钮 -->
          <div class="back-hint" @click="showLogin = false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M19 12H5M11 18l-6-6 6-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>返回首页</span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 底部信息 -->
    <div class="footer-info" :class="{ 'fade-in': entered }">
      <span>Powered by LangGraph · Vue3 · Spring Boot</span>
    </div>

    <!-- 注册弹窗 -->
    <el-dialog v-model="registerVisible" title="用户注册" width="440px" :close-on-click-modal="false" align-center>
      <el-form ref="registerFormRef" :model="registerForm" :rules="registerRules" label-width="90px">
        <el-form-item label="用户名" prop="userName" required>
          <el-input v-model="registerForm.userName" placeholder="请输入用户名" maxlength="30" />
        </el-form-item>
        <el-form-item label="账号" prop="userAccount" required>
          <el-input v-model="registerForm.userAccount" placeholder="账号至少4位" maxlength="30" />
        </el-form-item>
        <el-form-item label="密码" prop="userPassword" required>
          <el-input v-model="registerForm.userPassword" type="password" placeholder="密码至少8位" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="checkPassword" required>
          <el-input v-model="registerForm.checkPassword" type="password" placeholder="请再次输入密码" show-password />
        </el-form-item>
        <el-form-item label="个人简介" prop="userProfile">
          <el-input v-model="registerForm.userProfile" type="textarea" :rows="3" placeholder="选填，介绍一下自己" maxlength="200" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="registerVisible = false">取消</el-button>
        <el-button type="primary" :loading="registerLoading" @click="handleRegister">注 册</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { userApi } from '@/api'
import KgLogo from '@/components/KgLogo.vue'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref<FormInstance>()
const showLogin = ref(false)

// === 3D 粒子系统（浅色适配）===
const canvasRef = ref<HTMLCanvasElement>()
const pageRef = ref<HTMLDivElement>()
const entered = ref(false)

const tags = [
  { icon: '◆', label: '知识抽取' },
  { icon: '◇', label: '图谱探索' },
  { icon: '◈', label: '智能问答' },
  { icon: '◉', label: '模型训练' }
]

interface Particle3D {
  x: number; y: number; z: number
  vx: number; vy: number; vz: number
  size: number; color: string
}

let particles: Particle3D[] = []
let animId = 0
let targetRotX = 0, targetRotY = 0
let rotX = 0, rotY = 0
let cw = 0, ch = 0
const FOCAL = 600
const NUM_PARTICLES = 80
// 浅色背景下的粒子配色：柔和蓝紫
const COLORS = ['#4F6BFF', '#818CF8', '#A78BFA', '#6366F1', '#7C3AED', '#8B5CF6']

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
  let x = p.x * Math.cos(rotY) - p.z * Math.sin(rotY)
  let z = p.x * Math.sin(rotY) + p.z * Math.cos(rotY)
  const y2 = p.y * Math.cos(rotX) - z * Math.sin(rotX)
  const z2 = p.y * Math.sin(rotX) + z * Math.cos(rotX)
  const scale = FOCAL / (FOCAL + z2 + 400)
  return { sx: cw / 2 + x * scale, sy: ch / 2 + y2 * scale, scale, z: z2 }
}

function animate() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')!
  rotX += (targetRotX - rotX) * 0.05
  rotY += (targetRotY - rotY) * 0.05
  targetRotY += 0.002
  // 浅色背景拖尾
  ctx.fillStyle = 'rgba(248, 250, 252, 0.12)'
  ctx.fillRect(0, 0, cw, ch)
  for (const p of particles) {
    p.x += p.vx; p.y += p.vy; p.z += p.vz
    const d = Math.sqrt(p.x * p.x + p.y * p.y + p.z * p.z)
    if (d > 500 || d < 150) { p.vx *= -1; p.vy *= -1; p.vz *= -1 }
  }
  const projected = particles.map(p => ({ ...project(p, rotX, rotY), color: p.color, size: p.size }))
  // 连线
  ctx.lineWidth = 0.5
  for (let i = 0; i < projected.length; i++) {
    for (let j = i + 1; j < projected.length; j++) {
      const dx = projected[i].sx - projected[j].sx
      const dy = projected[i].sy - projected[j].sy
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist < 120) {
        const alpha = (1 - dist / 120) * 0.12 * Math.min(projected[i].scale, projected[j].scale)
        ctx.strokeStyle = `rgba(99, 102, 241, ${alpha})`
        ctx.beginPath()
        ctx.moveTo(projected[i].sx, projected[i].sy)
        ctx.lineTo(projected[j].sx, projected[j].sy)
        ctx.stroke()
      }
    }
  }
  // 粒子
  for (const p of projected) {
    const r = p.size * p.scale
    if (r < 0.3) continue
    const grad = ctx.createRadialGradient(p.sx, p.sy, 0, p.sx, p.sy, r * 4)
    grad.addColorStop(0, p.color)
    grad.addColorStop(0.3, p.color + '60')
    grad.addColorStop(1, 'transparent')
    ctx.fillStyle = grad
    ctx.globalAlpha = Math.min(p.scale * 0.7, 0.9)
    ctx.beginPath()
    ctx.arc(p.sx, p.sy, r * 4, 0, Math.PI * 2)
    ctx.fill()
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

onMounted(() => {
  resizeCanvas()
  initParticles()
  animate()
  nextTick(() => { entered.value = true })
  window.addEventListener('resize', resizeCanvas)
})

onUnmounted(() => {
  cancelAnimationFrame(animId)
  window.removeEventListener('resize', resizeCanvas)
})

// === 登录逻辑 ===
const form = reactive({ userAccount: '', userPassword: '' })
const rules: FormRules = {
  userAccount: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  userPassword: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ]
}

async function handleLogin() {
  if (!formRef.value) return
  try { await formRef.value.validate() } catch { return }
  const ok = await userStore.login(form.userAccount, form.userPassword)
  if (ok) {
    ElMessage.success('登录成功')
    router.push('/home')
  } else {
    ElMessage.error('登录失败，请检查账号密码')
  }
}

// === 注册逻辑 ===
const registerVisible = ref(false)
const registerLoading = ref(false)
const registerFormRef = ref<FormInstance>()
const registerForm = reactive({ userName: '', userAccount: '', userPassword: '', checkPassword: '', userProfile: '' })
const registerRules: FormRules = {
  userName: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  userAccount: [
    { required: true, message: '请输入账号', trigger: 'blur' },
    { min: 4, message: '账号至少4位', trigger: 'blur' }
  ],
  userPassword: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少8位', trigger: 'blur' }
  ],
  checkPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (value !== registerForm.userPassword) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur'
    }
  ]
}

function openRegister() {
  registerForm.userName = ''
  registerForm.userAccount = ''
  registerForm.userPassword = ''
  registerForm.checkPassword = ''
  registerForm.userProfile = ''
  registerVisible.value = true
}

async function handleRegister() {
  if (!registerFormRef.value) return
  try { await registerFormRef.value.validate() } catch { return }
  registerLoading.value = true
  try {
    await userApi.register({
      userAccount: registerForm.userAccount,
      userPassword: registerForm.userPassword,
      checkPassword: registerForm.checkPassword,
      userName: registerForm.userName,
      userProfile: registerForm.userProfile || undefined
    })
    ElMessage.success('注册成功，请登录')
    registerVisible.value = false
    form.userAccount = registerForm.userAccount
    form.userPassword = ''
  } finally {
    registerLoading.value = false
  }
}
</script>

<style scoped>
.entry-page {
  position: fixed;
  inset: 0;
  background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 50%, #f1f5f9 100%);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.particle-canvas {
  position: absolute;
  inset: 0;
  z-index: 0;
}

/* === 顶部品牌 === */
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
.brand-text {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  letter-spacing: 1px;
}

/* === 英雄文案 === */
.hero-content {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
  text-align: center;
  width: 90%;
  max-width: 640px;
}
.hero-title {
  margin: 0 0 16px;
  line-height: 1.15;
}
.title-line {
  display: block;
  font-size: clamp(36px, 6vw, 60px);
  font-weight: 800;
  letter-spacing: 2px;
  animation: titleSlideIn 0.8s ease both;
}
.title-line:first-child {
  color: #1e293b;
  animation-delay: 0.5s;
}
.gradient-text {
  background: linear-gradient(135deg, #4F6BFF 0%, #818CF8 50%, #06B6D4 100%);
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
  color: #64748b;
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
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(99, 102, 241, 0.12);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  opacity: 0;
  animation: fadeInUp 0.6s ease both;
  transition: border-color 0.3s, box-shadow 0.3s;
}
.tag:hover {
  border-color: rgba(79, 107, 255, 0.3);
  box-shadow: 0 4px 12px rgba(79, 107, 255, 0.1);
}
.tag-icon {
  font-size: 12px;
  color: #6366f1;
}
.tag-label {
  font-size: 13px;
  color: #475569;
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
  background: linear-gradient(135deg, #4F6BFF 0%, #818CF8 100%);
  color: white;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  overflow: hidden;
  opacity: 0;
  animation: fadeInUp 0.8s ease 1.4s both;
  transition: transform 0.3s, box-shadow 0.3s;
  box-shadow: 0 4px 20px rgba(79, 107, 255, 0.25);
}
.cta-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(79, 107, 255, 0.35);
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

/* === 登录卡片 === */
.login-wrapper {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
}
.login-card {
  width: 400px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(99, 102, 241, 0.12);
  border-radius: 16px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.08);
}
.login-header {
  text-align: center;
  margin-bottom: 28px;
}
.login-logo {
  display: block;
  margin: 0 auto 12px;
  filter: drop-shadow(0 0 12px rgba(99, 102, 241, 0.25));
}
.login-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
}
.login-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #94a3b8;
}
.login-form {
  width: 100%;
}

/* Element Plus 浅色覆盖 */
.login-card :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid #e2e8f0;
  box-shadow: none;
  transition: border-color 0.3s, box-shadow 0.3s;
}
.login-card :deep(.el-input__wrapper:hover) {
  border-color: rgba(99, 102, 241, 0.4);
}
.login-card :deep(.el-input__wrapper.is-focus) {
  border-color: #6366f1;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1);
}
.login-card :deep(.el-input__inner) {
  color: #1e293b;
}
.login-card :deep(.el-input__inner::placeholder) {
  color: #94a3b8;
}
.login-card :deep(.el-input__prefix-inner .el-icon) {
  color: #94a3b8;
}

.login-btn {
  width: 100%;
  background: linear-gradient(135deg, #4F6BFF 0%, #818CF8 100%);
  border: none;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 2px;
  transition: transform 0.2s, box-shadow 0.2s;
}
.login-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(79, 107, 255, 0.3);
}

.login-footer {
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 13px;
  color: #94a3b8;
}

.back-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 20px;
  font-size: 12px;
  color: #94a3b8;
  cursor: pointer;
  transition: color 0.3s;
}
.back-hint:hover {
  color: #6366f1;
}

/* === 底部 === */
.footer-info {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
  opacity: 0;
  transition: opacity 1s ease 1s;
}
.footer-info.fade-in {
  opacity: 1;
}

/* === 过渡动画 === */
.hero-fade-leave-active {
  transition: opacity 0.4s ease, transform 0.4s ease;
}
.hero-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -50%) scale(0.95);
}
.login-fade-enter-active {
  transition: opacity 0.5s ease 0.2s, transform 0.5s ease 0.2s;
}
.login-fade-enter-from {
  opacity: 0;
  transform: translate(-50%, -50%) scale(0.95) translateY(10px);
}

/* === 响应式 === */
@media (max-width: 480px) {
  .login-card {
    width: 100%;
    padding: 28px 24px;
  }
  .brand-top {
    top: 20px;
    left: 20px;
  }
}
</style>

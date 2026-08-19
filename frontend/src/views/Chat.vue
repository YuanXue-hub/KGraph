<template>
  <div class="chat-page">
    <!-- 左侧会话列表（极简深灰风格） -->
    <aside class="chat-sidebar">
      <div class="sidebar-header">
        <el-button class="new-chat-btn" @click="newChat">
          <el-icon class="btn-icon"><Plus /></el-icon>
          <span>新建对话</span>
        </el-button>
      </div>

      <div class="sidebar-list">
        <div
          v-for="(s, i) in sessions"
          :key="s.sessionId"
          class="session-item"
          :class="{ current: i === currentSessionIndex }"
          @click="switchSession(i)"
        >
          <div class="session-dot"></div>
          <span class="session-title">{{ s.title }}</span>
          <span class="session-delete" @click.stop="deleteSession(i)" title="删除会话">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14zM10 11v6M14 11v6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
        </div>
        <div v-if="sessions.length === 0" class="empty-sessions">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M8 10h8M8 14h5M6 3h9l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>暂无历史对话</span>
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="footer-brand">
          <div class="brand-dot"></div>
          <span>KGraph · 图谱问答</span>
        </div>
      </div>
    </aside>

    <!-- 右侧主对话区（纯白极简） -->
    <main class="chat-main">
      <!-- 顶部模型选择栏（极简无边框） -->
      <header class="chat-header">
        <div class="header-inner">
          <div class="model-select-wrapper">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" class="model-icon">
              <circle cx="12" cy="6" r="3"/>
              <circle cx="6" cy="18" r="3"/>
              <circle cx="18" cy="18" r="3"/>
              <path d="M12 9v3m0 3 4.5 4.5M12 12l-4.5 4.5" stroke-linecap="round"/>
            </svg>
            <el-select
              v-model="selectedModelId"
              placeholder="请选择图谱模型"
              filterable
              class="model-select"
              @change="onModelChange"
            >
              <el-option
                v-for="m in modelOptions"
                :key="m.value"
                :label="m.label"
                :value="m.value"
              />
            </el-select>
          </div>
          <span v-if="!selectedModelId" class="header-hint">选择模型后即可开始提问</span>
        </div>
      </header>

      <!-- 消息流区域 -->
      <div class="chat-messages" ref="messagesRef">
        <!-- 空态：欢迎页 -->
        <div v-if="messages.length === 0" class="chat-empty">
          <div class="empty-logo">
            <KgLogo :size="56" />
          </div>
          <h1 class="empty-title">你好，我是 KGraph 助手</h1>
          <p class="empty-subtitle">我可以基于选定的知识图谱，帮你查询实体、关系及统计信息。</p>

          <div class="quick-grid">
            <div
              v-for="(q, i) in quickQuestions"
              :key="i"
              class="quick-card"
              @click="sendMessage(q)"
            >
              <div class="quick-icon">
                <svg v-if="i===0" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path d="M4 6h16M4 12h10M4 18h16" stroke-linecap="round"/>
                </svg>
                <svg v-else-if="i===1" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path d="M3 3v18h18" stroke-linecap="round"/>
                  <path d="M7 15l4-5 3 3 5-7" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7">
                  <circle cx="11" cy="11" r="7"/>
                  <path d="m20 20-3.5-3.5" stroke-linecap="round"/>
                </svg>
              </div>
              <div class="quick-text">
                <div class="quick-title">{{ q.split('？')[0] }}？</div>
                <div class="quick-desc">{{ quickDescs[i] }}</div>
              </div>
              <div class="quick-arrow">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <div v-else class="messages-flow">
          <div
            v-for="(msg, idx) in messages"
            :key="msg.id"
            class="msg-row"
            :class="msg.role"
          >
            <!-- 用户消息（浅色底，无头像） -->
            <template v-if="msg.role === 'user'">
              <div class="user-bubble">
                <div class="user-text">{{ msg.content }}</div>
              </div>
            </template>

            <!-- AI 消息（无气泡，无头像，纯文字布局） -->
            <template v-else>
              <div class="ai-body">
                <!-- 思考过程卡片（DeepSeek风格） -->
                <div
                  v-if="msg.displayThinking || msg.thinkingBuffer || msg.thinking"
                  class="think-card"
                  :class="{ collapsed: msg.thinkCollapsed, active: !msg.thinkCollapsed }"
                >
                  <button
                    type="button"
                    class="think-trigger"
                    @click.stop="msg.thinkCollapsed = !msg.thinkCollapsed"
                  >
                    <span class="think-indicator">
                      <span class="think-dot" :class="{ pulse: msg.streaming }"></span>
                    </span>
                    <span class="think-label">
                      已深度思考
                      <b v-if="!msg.streaming && msg.thinkSeconds > 0">{{ msg.thinkSeconds }} 秒</b>
                      <b v-else>中…</b>
                    </span>
                    <svg
                      viewBox="0 0 24 24"
                      width="14"
                      height="14"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      class="think-chevron"
                      :class="{ flip: !msg.thinkCollapsed }"
                    >
                      <path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </button>
                  <div class="think-panel" v-show="!msg.thinkCollapsed">
                    <div class="think-content">{{ msg.displayThinking || '' }}</div>
                    <!-- 打字机流还在继续时显示的光标 -->
                    <span v-if="msg.streaming && !msg.thinkDone" class="caret think-caret"></span>
                  </div>
                </div>

                <!-- 工具调用列表（紧凑卡片） -->
                <div class="toolcall-list">
                  <div
                    v-for="(tc, ti) in msg.toolCalls"
                    :key="'tc-' + ti"
                    class="tc-item"
                    :class="[tc.status, { open: !tc.collapsed }]"
                  >
                    <button type="button" class="tc-head" @click.stop="tc.collapsed = !tc.collapsed">
                      <span class="tc-status-icon">
                        <svg v-if="tc.status === 'running'" viewBox="0 0 24 24" width="12" height="12" class="spin">
                          <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2.4" stroke-dasharray="40 60" stroke-linecap="round"/>
                        </svg>
                        <svg v-else viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.6">
                          <path d="M5 12l4 4 10-10" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                      </span>
                      <span class="tc-name">调用 {{ tc.tool || '工具' }}</span>
                      <span v-if="tc.status === 'done' && tc.durationMs > 0" class="tc-meta">{{ (tc.durationMs / 1000).toFixed(1) }}s</span>
                      <svg
                        viewBox="0 0 24 24" width="14" height="14" fill="none"
                        stroke="currentColor" stroke-width="2"
                        class="tc-chevron" :class="{ open: !tc.collapsed }"
                      >
                        <path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                    </button>
                    <div class="tc-panel" v-show="!tc.collapsed">
                      <div class="tc-section">
                        <div class="tc-section-title">参数</div>
                        <pre class="tc-pre">{{ formatJson(tc.input) }}</pre>
                      </div>
                      <div class="tc-section" v-if="tc.output">
                        <div class="tc-section-title">结果</div>
                        <pre class="tc-pre">{{ formatJson(tc.output) }}</pre>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 正式回答（Markdown渲染） -->
                <div
                  class="answer-content"
                  v-if="msg.displayContent || msg.contentBuffer || msg.content"
                >
                  <div v-html="renderMarkdown(msg.displayContent || '')"></div>
                  <!-- 流式过程中的闪烁光标 -->
                  <span v-if="msg.streaming && !msg.answerDone" class="caret"></span>
                </div>

                <!-- 初始加载小圆点 -->
                <div v-if="msg.streaming && isTotallyEmpty(msg)" class="first-dots">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- 底部输入区（DeepSeek风格） -->
      <footer class="chat-footer">
        <div class="footer-inner">
          <div class="input-shell" :class="{ focused: inputFocused, sending: sending }">
            <el-input
              v-model="inputText"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 6 }"
              placeholder="给 KGraph 发送消息… （Enter 发送 / Shift+Enter 换行）"
              :disabled="sending"
              @keydown.enter.exact.prevent="sendMessage()"
              @focus="inputFocused = true"
              @blur="inputFocused = false"
              class="chat-input"
            />
            <button
              class="send-btn"
              :disabled="!canSend || sending"
              @click="sendMessage()"
              :title="sending ? '正在发送…' : '发送'"
            >
              <svg v-if="!sending" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 19V5M5 12l7-7 7 7" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <svg v-else viewBox="0 0 24 24" width="18" height="18" class="spin-slow">
                <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2.4" stroke-dasharray="40 60" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
          <p class="disclaimer">内容由 AI 结合图谱数据生成，重要信息建议自行核实</p>
        </div>
      </footer>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { projectApi, modelApi } from '@/api'
import { marked } from 'marked'
import KgLogo from '@/components/KgLogo.vue'

// ========== 类型定义 ==========
interface ToolCall {
  tool: string
  input: string
  output: string
  status: 'running' | 'done'
  collapsed: boolean
  startedAt: number
  durationMs: number
}

interface Message {
  id: string
  role: 'user' | 'ai'
  /** 完整最终内容（SSE收全后） */
  content: string
  /** 完整思考内容 */
  thinking: string
  toolCalls: ToolCall[]
  thinkCollapsed: boolean
  streaming: boolean

  /** 待消费的缓冲内容（打字机队列） */
  contentBuffer: string
  thinkingBuffer: string
  /** 当前已显示内容（打字机推进） */
  displayContent: string
  displayThinking: string

  thinkDone: boolean
  answerDone: boolean
  thinkSeconds: number
  thinkStartAt: number
}

// ========== 快速问题 ==========
const quickQuestions = [
  '当前图谱中有哪些实体类型',
  '帮我统计图谱的节点和关系数量',
  '搜索普京相关的实体和关系',
]
const quickDescs = [
  '查看图谱本体 Schema 概览',
  '用数据概览了解图谱规模',
  '深度探索特定实体的关系网络',
]

// ========== 响应式数据 ==========
interface ChatSession {
  sessionId: string
  title: string
  messages: Message[]
  createdAt: number
}

const sessions = ref<ChatSession[]>([])
const currentSessionIndex = ref(0)
const messages = ref<Message[]>([])
const inputText = ref('')
const sending = ref(false)
const inputFocused = ref(false)
const selectedModelId = ref<number>()
const modelOptions = ref<{ label: string; value: number }[]>([])
const messagesRef = ref<HTMLElement>()
const sessionId = ref<string>()

const currentSession = computed(() => sessions.value[currentSessionIndex.value])

const canSend = computed(() => inputText.value.trim().length > 0 && selectedModelId.value !== undefined)

// ========== 打字机调度器（全局唯一timer，避免重建导致抖动） ==========
let typewriterTimer: number | null = null
const TYPE_SPEED = 12 // 每个tick消费的字符数（中英文自适应，偏大=更快）
const TICK_MS = 16   // ≈ 60fps

function startTypewriter() {
  if (typewriterTimer !== null) return
  const tick = () => {
    let anyBusy = false
    for (const m of messages.value) {
      if (m.role !== 'ai') continue

      // thinking 消费
      if (m.thinkingBuffer.length > 0) {
        const take = Math.min(TYPE_SPEED, m.thinkingBuffer.length)
        const chunk = m.thinkingBuffer.slice(0, take)
        m.thinkingBuffer = m.thinkingBuffer.slice(take)
        m.displayThinking += chunk
        anyBusy = true
      } else if (m.streaming === false && !m.thinkDone && m.displayThinking.length >= (m.thinking || '').length) {
        m.thinkDone = true
        m.thinkSeconds = Math.max(1, Math.round((Date.now() - m.thinkStartAt) / 1000))
      }

      // answer 消费（思考完全结束前不推答案，避免视觉抢跑）
      if (m.contentBuffer.length > 0 && (m.thinkDone || !m.displayThinking)) {
        const take = Math.min(TYPE_SPEED * 2, m.contentBuffer.length)
        const chunk = m.contentBuffer.slice(0, take)
        m.contentBuffer = m.contentBuffer.slice(take)
        m.displayContent += chunk
        anyBusy = true
      } else if (m.streaming === false && !m.answerDone && m.displayContent.length >= (m.content || '').length) {
        m.answerDone = true
      }
    }
    if (anyBusy) {
      scrollToBottom(false)
    }
  }
  typewriterTimer = window.setInterval(tick, TICK_MS)
}

function stopTypewriter() {
  if (typewriterTimer !== null) {
    clearInterval(typewriterTimer)
    typewriterTimer = null
  }
}

function flushTypewriterFor(msg: Message) {
  // 先把缓冲刷到 display（非流式兜底）
  if (msg.thinkingBuffer) {
    msg.displayThinking += msg.thinkingBuffer
    msg.thinkingBuffer = ''
  }
  if (msg.contentBuffer) {
    msg.displayContent += msg.contentBuffer
    msg.contentBuffer = ''
  }
  // 无工具调用的直答场景：模型回答被流式归为 thinking → 迁移到正式回答区显示
  if (msg.role === 'ai' && msg.thinking && !msg.content && msg.toolCalls.length === 0) {
    const thinkText = msg.displayThinking || msg.thinking
    if (thinkText) {
      msg.content = thinkText
      msg.displayContent = thinkText
      msg.thinking = ''
      msg.displayThinking = ''
    }
  }
  // 刷完后立即标记阶段完成，确保UI状态同步
  msg.thinkDone = true
  if (!msg.thinkSeconds) {
    msg.thinkSeconds = Math.max(1, Math.round((Date.now() - (msg.thinkStartAt || Date.now())) / 1000))
  }
  msg.answerDone = true
}

// ========== 工具函数 ==========
let msgIdSeq = 0

function createEmptyMessage(role: 'user' | 'ai', content = ''): Message {
  return {
    id: `msg-${++msgIdSeq}`,
    role,
    content,
    thinking: '',
    toolCalls: [],
    thinkCollapsed: false, // AI首条思考默认展开
    streaming: false,
    contentBuffer: '',
    thinkingBuffer: '',
    displayContent: content,
    displayThinking: '',
    thinkDone: !content,
    answerDone: !content,
    thinkSeconds: 0,
    thinkStartAt: 0,
  }
}

function addMessage(role: 'user' | 'ai', content = ''): Message {
  const msg = createEmptyMessage(role, content)
  messages.value.push(msg)
  scrollToBottom()
  return msg
}

function scrollToBottom(smooth = true) {
  nextTick(() => {
    const el = messagesRef.value
    if (!el) return
    try {
      if (smooth) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' as ScrollBehavior })
      else el.scrollTop = el.scrollHeight
    } catch {
      el.scrollTop = el.scrollHeight
    }
  })
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  try {
    return marked.parse(text, { breaks: true, gfm: true }) as string
  } catch {
    return text.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]!).replace(/\n/g, '<br>')
  }
}

function formatJson(input: string): string {
  if (!input) return ''
  try {
    const obj = JSON.parse(input)
    return JSON.stringify(obj, null, 2)
  } catch {
    return input
  }
}

function isTotallyEmpty(msg: Message): boolean {
  return !msg.displayThinking && !msg.displayContent && msg.toolCalls.length === 0
}

// ========== 业务：加载模型列表 ==========
async function loadModels() {
  try {
    const res = await projectApi.list({ pageNum: 1, pageSize: 50 })
    const records = res.data?.records || res.data?.list || res.data || []
    const projects = Array.isArray(records) ? records : []

    const opts: { label: string; value: number }[] = []
    for (const p of projects) {
      try {
        const mRes = await modelApi.list(p.id)
        const models = mRes.data?.records || mRes.data?.list || mRes.data || []
        const list = Array.isArray(models) ? models : []
        for (const m of list) {
          opts.push({
            label: `${p.projectName} / ${m.modelName}`,
            value: m.id,
          })
        }
      } catch { /* skip */ }
    }
    modelOptions.value = opts
  } catch (e) {
    console.error('加载模型列表失败', e)
  }
}

function onModelChange() { /* no-op 模型切换不丢会话 */ }
// ========== 会话管理 ==========
async function createSession(): Promise<string | undefined> {
  try {
    const res = await fetch('/api/v1/chat/session/create', { method: 'POST', credentials: 'include' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    return data.sessionId
  } catch (e) {
    console.error('创建会话失败', e)
  }
}

// 将当前 messages 浅拷贝保存到当前 session（断开引用，避免互相干扰）
function saveMessagesToSession() {
  const session = sessions.value[currentSessionIndex.value]
  if (session) {
    session.messages = [...messages.value]
  }
}

async function newChat() {
  // 仅当当前会话有消息时才保存（避免把空会话写入列表）
  if (messages.value.length > 0) {
    saveMessagesToSession()
  } else if (sessions.value.length > 0 && currentSessionIndex.value >= 0) {
    // 当前会话无消息（未发送过任何内容），直接复用，不重复创建
    const cur = sessions.value[currentSessionIndex.value]
    if (cur && cur.messages.length === 0 && cur.title === '新的对话') return
  }
  const sid = await createSession()
  if (sid === undefined) return
  // 新建会话项并插入列表顶部
  const newSession: ChatSession = {
    sessionId: sid,
    title: '新的对话',
    messages: [],
    createdAt: Date.now(),
  }
  sessions.value.unshift(newSession)
  currentSessionIndex.value = 0
  // 直接赋值新数组（Vue 能正确检测引用变化并触发渲染）
  messages.value = []
  sessionId.value = sid
}

async function switchSession(index: number) {
  if (index === currentSessionIndex.value || sending.value) return
  // 保存当前会话消息（浅拷贝）
  saveMessagesToSession()
  // 切换到目标会话
  currentSessionIndex.value = index
  const target = sessions.value[index]
  sessionId.value = target.sessionId
  // 若本地已有消息缓存则直接展示，否则从后端加载历史消息
  if (target.messages && target.messages.length > 0) {
    messages.value = [...target.messages]
  } else {
    await loadSessionMessages(target)
  }
  await nextTick()
  scrollToBottom()
}

// 从后端加载会话的完整历史消息（切换页面后恢复对话）
async function loadSessionMessages(session: ChatSession) {
  try {
    const res = await fetch(`/api/v1/chat/session/${session.sessionId}/messages`, { credentials: 'include' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    const list: { role: string; content: string }[] = data.messages || []
    session.messages = list.map(m => createEmptyMessage(m.role === 'user' ? 'user' : 'ai', m.content))
    messages.value = [...session.messages]
  } catch (e) {
    console.error('加载会话消息失败', e)
  }
}

// 加载当前用户的历史会话列表（进入智能问答页面时自动调用）
async function loadHistorySessions() {
  try {
    const res = await fetch('/api/v1/chat/session/list', { credentials: 'include' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    const list: any[] = data.sessions || []
    // 按最近活跃时间倒序转为会话项（标题取首条消息）
    sessions.value = list.map(s => ({
      sessionId: s.sessionId,
      title: (s.firstMessage || '新的对话').length > 24 ? (s.firstMessage || '').slice(0, 24) + '…' : (s.firstMessage || '新的对话'),
      messages: [],
      createdAt: s.createdAt ? new Date(s.createdAt).getTime() : Date.now(),
    }))
    // 默认选中最近的一个会话并加载其消息
    if (sessions.value.length > 0) {
      currentSessionIndex.value = 0
      sessionId.value = sessions.value[0].sessionId
      await loadSessionMessages(sessions.value[0])
    } else {
      // 无历史会话则新建
      await newChat()
    }
  } catch (e) {
    console.error('加载历史会话失败', e)
    await newChat()
  }
}

// 删除会话（清除 Redis + MySQL 逻辑删除）
async function deleteSession(index: number) {
  const target = sessions.value[index]
  if (!target) return
  try {
    const res = await fetch(`/api/v1/chat/session/${target.sessionId}`, { method: 'DELETE', credentials: 'include' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  } catch (e) {
    console.error('删除会话失败', e)
    ElMessage.error('删除会话失败')
    return
  }
  // 从列表移除
  sessions.value.splice(index, 1)
  // 若删除的是当前会话，则切换到其他会话或新建
  if (index === currentSessionIndex.value) {
    if (sessions.value.length > 0) {
      currentSessionIndex.value = 0
      sessionId.value = sessions.value[0].sessionId
      if (sessions.value[0].messages?.length) {
        messages.value = [...sessions.value[0].messages]
      } else {
        await loadSessionMessages(sessions.value[0])
      }
    } else {
      await newChat()
    }
  } else if (index < currentSessionIndex.value) {
    currentSessionIndex.value--
  }
  ElMessage.success('会话已删除')
}

// ========== 业务：发送消息 + SSE 流式解析 ==========
async function sendMessage(text?: string) {
  const msg = (text ?? inputText.value).trim()
  if (!msg) return
  if (!selectedModelId.value) {
    ElMessage.warning('请先选择知识图谱模型')
    return
  }

  inputText.value = ''
  sending.value = true
  startTypewriter()

  // 用户消息
  addMessage('user', msg)
  // 第一条消息更新会话标题
  if (currentSession.value && currentSession.value.title === '新的对话') {
    currentSession.value.title = msg.length > 24 ? msg.slice(0, 24) + '…' : msg
  }

  // AI 占位消息
  const aiMsg = addMessage('ai')
  aiMsg.streaming = true
  aiMsg.thinkStartAt = Date.now()

  try {
    const response = await fetch('/api/v1/chat/agent/stream', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({ message: msg, modelId: selectedModelId.value, sessionId: sessionId.value }),
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body?.getReader()
    if (!reader) throw new Error('浏览器不支持流式读取')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const rawLine of lines) {
        const line = rawLine.trimEnd()
        // 空行是 SSE 事件分隔符，跳过
        if (!line) continue
        // 兼容标准 SSE：data: {...}  以及 有些代理会原样透传 event: ...
        if (!line.startsWith('data:')) continue

        const payload = line.slice(5).trimStart()
        if (!payload || payload === '[DONE]') continue

        let event: any
        try { event = JSON.parse(payload) } catch { continue }

        switch (event.type) {
          case 'thinking': {
            const delta = event.content || ''
            if (delta) {
              aiMsg.thinking += delta
              aiMsg.thinkingBuffer += delta
            }
            scrollToBottom(false)
            break
          }
          case 'tool_call': {
            if (event.status === 'running') {
              aiMsg.toolCalls.push({
                tool: event.tool || '',
                input: event.input || '',
                output: '',
                status: 'running',
                collapsed: true, // 默认收起参数面板，更干净
                startedAt: Date.now(),
                durationMs: 0,
              })
            } else if (event.status === 'done') {
              const last = [...aiMsg.toolCalls].reverse().find(tc => tc.status === 'running')
              if (last) {
                last.output = event.output || ''
                last.status = 'done'
                last.durationMs = Math.max(80, Date.now() - last.startedAt)
              }
            }
            scrollToBottom(false)
            break
          }
          case 'answer': {
            const delta = event.content || ''
            if (delta) {
              aiMsg.content += delta
              aiMsg.contentBuffer += delta
            }
            scrollToBottom(false)
            break
          }
          case 'error': {
            const errMsg = `\n\n⚠️ 请求出错：${event.message || '未知错误'}`
            aiMsg.content += errMsg
            aiMsg.contentBuffer += errMsg
            break
          }
          case 'done': {
            // ✅ 关键：Python后端明确发了done事件 → 主动退出循环，触发finally里的收尾
            // 先把剩余 buffer 收尾逻辑让 finally 执行
            buffer = '' // 丢弃未完成数据
            lines.length = 0
            // 立即跳出 reader.read 的解析循环
            // 标记流结束，break 外层 while
            try { reader.releaseLock?.() } catch { /* noop */ }
            scrollToBottom(false)
            return  // 从 sendMessage 内部提前退出到 finally
          }
          default:
            break
        }
      }
    }
  } catch (e: any) {
    const err = `网络错误：${e?.message || String(e)}`
    aiMsg.content += err
    aiMsg.contentBuffer += err
  } finally {
    aiMsg.streaming = false
    // 立即启动 thinkDone/answerDone 倒计时 + 最多 1.5s 强制收尾
    const safeTimeout = window.setTimeout(() => {
      flushTypewriterFor(aiMsg)
      sending.value = false
      scrollToBottom()
    }, 1500)
    const startedAt = Date.now()
    const flushWait = window.setInterval(() => {
      const noBuffer = !aiMsg.contentBuffer && !aiMsg.thinkingBuffer
      if (noBuffer) {
        clearTimeout(safeTimeout)
        clearInterval(flushWait)
        flushTypewriterFor(aiMsg)
        sending.value = false
        scrollToBottom()
      } else if (Date.now() - startedAt > 1200) {
        // 已等 1.2s 还有残余缓冲 → 强制flush等safeTimeout兜底
      }
    }, 60)
  }
}

// ========== 生命周期 ==========
onMounted(() => {
  loadModels()
  // 进入页面自动加载当前用户的历史会话（用户间隔离）
  loadHistorySessions()
  startTypewriter()
})

onBeforeUnmount(() => {
  stopTypewriter()
})

// 监听消息流，只要有新消息或缓冲内容变化就一直跑着typewriter
watch(
  () => messages.value.map(m => `${m.id}:${m.streaming ? 's' : 'e'}:${m.thinkingBuffer.length}:${m.contentBuffer.length}`).join('|'),
  () => {
    startTypewriter()
  },
)
</script>

<!-- ==================== 样式：DeepSeek 极简风格 ==================== -->
<style scoped>
.chat-page {
  display: flex;
  height: calc(100vh - 60px);
  background: #FFFFFF;
  color: #1f2937;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
    "Hiragino Sans GB", "Microsoft YaHei", Helvetica, Arial, sans-serif;
}

/* ============ 左侧边栏（浅色系） ============ */
.chat-sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #f7f8fa;
  color: #4b5563;
  border-right: 1px solid #ebecef;
}

.sidebar-header { padding: 16px; }
.new-chat-btn {
  display: flex !important;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  width: 100%;
  height: 38px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid #e3e5ea;
  color: #1f2937;
  font-size: 14px;
  font-weight: 500;
  transition: all .15s ease;
}
.new-chat-btn:hover {
  background: #f0f3f9;
  border-color: #d6dbe6;
}
.btn-icon { opacity: .92; }

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px 10px;
}
.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 9px;
  margin-bottom: 2px;
  cursor: pointer;
  color: #4b5563;
  transition: background .15s;
}
.session-item:hover { background: #eef0f3; color: #1f2937; }
.session-item.current {
  background: #e8edff;
  color: #1e3a8a;
  font-weight: 500;
}
.session-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #4F6BFF;
  flex-shrink: 0;
  box-shadow: 0 0 0 3px rgba(79,107,255,0.14);
}
.session-title {
  flex: 1;
  font-size: 13.5px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.session-delete {
  display: none;
  align-items: center;
  justify-content: center;
  width: 20px; height: 20px;
  border-radius: 5px;
  color: #9ca3af;
  flex-shrink: 0;
  transition: background .15s, color .15s;
}
.session-item:hover .session-delete { display: flex; }
.session-delete:hover { background: #fee2e2; color: #ef4444; }

.empty-sessions {
  margin-top: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: #9ca3af;
  font-size: 13px;
  opacity: .9;
}

.sidebar-footer { padding: 14px 16px 18px; border-top: 1px solid #ebecef; }
.footer-brand {
  display: flex; align-items: center; gap: 8px;
  font-size: 12.5px; color: #6b7280;
}
.brand-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: linear-gradient(135deg, #4F6BFF, #8B5CF6);
}

/* ============ 主对话区 ============ */
.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  position: relative;
}

/* 顶部模型栏 */
.chat-header {
  height: 56px;
  border-bottom: 1px solid #f0f1f3;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.header-inner {
  width: 100%;
  max-width: 860px;
  margin: 0 auto;
  padding: 0 28px;
  display: flex;
  align-items: center;
  gap: 14px;
}
.model-select-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px 5px 12px;
  border-radius: 10px;
  transition: background .15s;
}
.model-select-wrapper:hover { background: #f7f8fa; }
.model-icon { color: #4F6BFF; flex-shrink: 0; }
.model-select {
  width: 280px;
  --el-select-input-font-size: 14px;
}
.model-select :deep(.el-select__wrapper) {
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
}
.model-select :deep(.el-select__placeholder) { color: #9ca3af; }
.model-select :deep(.el-select__selection) { font-weight: 500; color: #1f2937; }
.header-hint { color: #9ca3af; font-size: 13px; }

/* 消息区 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
}

/* ====== 空态欢迎页 ====== */
.chat-empty {
  max-width: 760px;
  margin: 0 auto;
  padding: 72px 28px 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.empty-logo { margin-bottom: 20px; filter: drop-shadow(0 6px 18px rgba(79,107,255,0.22)); }
.empty-title {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin: 0 0 10px;
  color: #0f172a;
  text-align: center;
}
.empty-subtitle {
  margin: 0 0 32px;
  color: #6b7280;
  font-size: 14.5px;
  line-height: 1.7;
  text-align: center;
}
.quick-grid {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.quick-card {
  border: 1px solid #eceef1;
  background: #fafbfc;
  border-radius: 14px;
  padding: 15px 16px 15px 14px;
  cursor: pointer;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  transition: all .18s ease;
}
.quick-card:hover {
  border-color: #d8dcff;
  background: #fff;
  transform: translateY(-1px);
  box-shadow: 0 8px 24px -10px rgba(79,107,255,0.28);
}
.quick-icon {
  width: 32px; height: 32px;
  border-radius: 9px;
  flex-shrink: 0;
  background: linear-gradient(135deg, #eef1ff, #f4efff);
  color: #4F6BFF;
  display: flex; align-items: center; justify-content: center;
}
.quick-text { flex: 1; min-width: 0; }
.quick-title {
  font-size: 13.5px; font-weight: 600; color: #111827;
  margin-bottom: 4px; line-height: 1.5;
}
.quick-desc { font-size: 12px; color: #6b7280; line-height: 1.5; }
.quick-arrow {
  color: #c4c9d1; flex-shrink: 0;
  transition: all .18s;
  display: flex; align-items: center; justify-content: center;
  margin-top: 4px;
}
.quick-card:hover .quick-arrow { color: #4F6BFF; transform: translateX(2px); }

/* ====== 消息流 ====== */
.messages-flow {
  padding: 28px 0 12px;
  max-width: 860px;
  margin: 0 auto;
}
.msg-row {
  display: flex;
  gap: 14px;
  padding: 18px 28px;
  max-width: 100%;
  position: relative;
}
.msg-row.user {
  justify-content: flex-end;
  align-items: flex-start;
}
.msg-row.ai {
  justify-content: flex-start;
  align-items: flex-start;
}

/* 用户气泡（浅色底，DeepSeek 风格） */
.user-bubble { max-width: 72%; }
.user-text {
  background: #f3f4f6;
  color: #1f2937;
  padding: 10px 16px;
  border-radius: 12px;
  font-size: 14.5px;
  line-height: 1.65;
  word-break: break-word;
  white-space: pre-wrap;
}

/* AI 消息主体 */
.ai-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 2px;
}

/* ============ 思考卡片 ============ */
.think-card {
  border: 1px solid #eceef1;
  background: #fafbfc;
  border-radius: 12px;
  overflow: hidden;
  transition: all .18s ease;
  max-width: 100%;
}
.think-card.collapsed { border-radius: 10px; }
.think-card.active {
  background: linear-gradient(180deg, #fafbff 0%, #ffffff 100%);
  border-color: #e1e5ff;
}

.think-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: transparent;
  border: none;
  cursor: pointer;
  font: inherit;
  text-align: left;
}
.think-indicator {
  width: 18px; height: 18px;
  display: flex; align-items: center; justify-content: center;
}
.think-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: linear-gradient(135deg, #10b981, #059669);
  box-shadow: 0 0 0 4px rgba(16,185,129,0.12);
  transition: all .2s;
}
.think-dot.pulse {
  background: linear-gradient(135deg, #4F6BFF, #8B5CF6);
  box-shadow: 0 0 0 4px rgba(79,107,255,0.15);
  animation: think-pulse 1.2s ease-in-out infinite;
}
@keyframes think-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(0.85); opacity: .75; }
}
.think-label {
  flex: 1;
  font-size: 13px;
  color: #374151;
  display: flex; align-items: baseline; gap: 6px;
}
.think-label b { color: #111827; font-weight: 600; }
.think-chevron {
  color: #9ca3af;
  transition: transform .2s ease;
}
.think-chevron.flip { transform: rotate(180deg); }

.think-panel {
  padding: 0 14px 14px;
  border-top: 1px dashed #e5e7eb;
  margin-top: -1px;
}
.think-content {
  padding: 12px 0 2px;
  color: #4b5563;
  font-size: 13.5px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: "PingFang SC", "Microsoft YaHei", ui-sans-serif, system-ui, sans-serif;
}

/* ============ 工具调用 ============ */
.toolcall-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tc-item {
  border: 1px solid #eceef1;
  background: #ffffff;
  border-radius: 10px;
  overflow: hidden;
}
.tc-item.running { border-color: #dbeafe; background: #f8faff; }
.tc-item.done { border-color: #e6f5ee; background: #f8fdfa; }

.tc-head {
  width: 100%;
  padding: 9px 12px;
  background: transparent;
  border: none;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font: inherit;
  text-align: left;
}
.tc-status-icon {
  width: 18px; height: 18px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.tc-item.running .tc-status-icon { color: #2563eb; }
.tc-item.done .tc-status-icon { color: #059669; }

.spin { animation: spin 1s linear infinite; }
.spin-slow { animation: spin 1.4s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.tc-name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: #111827;
}
.tc-meta { color: #6b7280; font-size: 12px; font-variant-numeric: tabular-nums; }
.tc-chevron {
  color: #9ca3af;
  transition: transform .2s ease;
}
.tc-chevron.open { transform: rotate(180deg); }

.tc-panel {
  padding: 2px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.tc-section-title {
  font-size: 11.5px;
  color: #9ca3af;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin: 6px 0 4px;
}
.tc-pre {
  margin: 0;
  padding: 10px 12px;
  background: #0b1020;
  color: #d1d5db;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.6;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 180px;
  overflow-y: auto;
}

/* ============ 正式回答内容 ============ */
.answer-content {
  margin-top: 2px;
  font-size: 15px;
  line-height: 1.82;
  color: #0f172a;
  word-break: break-word;
  position: relative;
  padding-right: 6px;
}
.answer-content :deep(p) { margin: 0 0 10px; }
.answer-content :deep(p:last-child) { margin-bottom: 0; }
.answer-content :deep(h1),
.answer-content :deep(h2),
.answer-content :deep(h3) { margin: 16px 0 8px; color: #0f172a; line-height: 1.4; letter-spacing: -0.01em; }
.answer-content :deep(h2) { font-size: 17.5px; font-weight: 700; }
.answer-content :deep(h3) { font-size: 15.5px; font-weight: 600; }

.answer-content :deep(ul),
.answer-content :deep(ol) {
  margin: 0 0 10px;
  padding-left: 22px;
}
.answer-content :deep(li) { margin: 3px 0; line-height: 1.75; }
.answer-content :deep(ul li::marker) { color: #4F6BFF; }

.answer-content :deep(strong) { color: #0f172a; font-weight: 700; }
.answer-content :deep(em) { color: #4F6BFF; font-style: normal; font-weight: 500; }

/* 表格 */
.answer-content :deep(table) {
  border-collapse: separate;
  border-spacing: 0;
  width: 100%;
  margin: 10px 0 14px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #eceef1;
  font-size: 13.5px;
}
.answer-content :deep(th) {
  background: #f7f8fa;
  color: #374151;
  font-weight: 600;
  text-align: left;
  padding: 9px 14px;
  border-bottom: 1px solid #eceef1;
}
.answer-content :deep(td) {
  padding: 8px 14px;
  border-bottom: 1px solid #f3f4f6;
  color: #374151;
}
.answer-content :deep(tr:last-child td) { border-bottom: none; }

/* 内联 code */
.answer-content :deep(code) {
  background: #f3f4f6;
  color: #dc2626;
  padding: 2px 6px;
  border-radius: 5px;
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
/* 代码块 */
.answer-content :deep(pre) {
  background: #0b1020;
  color: #e5e7eb;
  padding: 14px 16px;
  border-radius: 10px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.65;
  margin: 10px 0 14px;
}
.answer-content :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
  font-size: inherit;
}

/* 引用块 */
.answer-content :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 14px;
  border-left: 3px solid #c7d2fe;
  background: #f5f3ff;
  color: #4338ca;
  border-radius: 0 8px 8px 0;
  font-size: 14px;
}

/* 闪烁光标（打字机效果） */
.caret {
  display: inline-block;
  width: 2px;
  height: 1em;
  vertical-align: -2px;
  margin-left: 1px;
  background: linear-gradient(135deg, #4F6BFF, #8B5CF6);
  border-radius: 1px;
  animation: caret-blink 1s step-end infinite;
}
.think-caret { height: 14px; vertical-align: -2px; background: #9ca3af; }
@keyframes caret-blink {
  0%, 50% { opacity: 1; }
  50.01%, 100% { opacity: 0; }
}

/* 初始小圆点 */
.first-dots {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 0;
}
.first-dots span {
  width: 6px; height: 6px; border-radius: 50%;
  background: #d1d5db;
  animation: dot-wave 1.2s infinite ease-in-out;
}
.first-dots span:nth-child(1) { animation-delay: -0.32s; background: #4F6BFF; }
.first-dots span:nth-child(2) { animation-delay: -0.16s; background: #6A5CFF; }
.first-dots span:nth-child(3) { animation-delay: 0s;     background: #8B5CF6; }
@keyframes dot-wave {
  0%, 80%, 100% { transform: translateY(0); opacity: .4; }
  40% { transform: translateY(-4px); opacity: 1; }
}

/* ============ 底部输入区 ============ */
.chat-footer {
  flex-shrink: 0;
  border-top: 1px solid #f0f1f3;
  background: #ffffff;
}
.footer-inner {
  max-width: 860px;
  margin: 0 auto;
  padding: 16px 28px 18px;
}
.input-shell {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 10px 10px 10px 18px;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
  transition: all .18s ease;
}
.input-shell.focused {
  border-color: #c7d2fe;
  box-shadow: 0 0 0 5px rgba(79,107,255,0.08), 0 8px 24px -12px rgba(79,107,255,0.25);
  background: #fff;
}
.input-shell.sending { opacity: .85; }

.chat-input :deep(.el-textarea__inner) {
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  resize: none;
  padding: 6px 0;
  font-size: 14.5px;
  line-height: 1.65;
  color: #111827;
  font-family: inherit;
  max-height: 200px;
}
.chat-input :deep(.el-textarea__inner::placeholder) {
  color: #9ca3af;
}

.send-btn {
  width: 36px; height: 36px;
  flex-shrink: 0;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #4F6BFF 0%, #6A5CFF 60%, #8B5CF6 100%);
  color: #ffffff;
  transition: all .18s ease;
  box-shadow: 0 2px 8px -2px rgba(79,107,255,0.55);
}
.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 5px 14px -3px rgba(79,107,255,0.65);
}
.send-btn:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
  box-shadow: none;
}
.send-btn:active:not(:disabled) { transform: translateY(0); }

.disclaimer {
  text-align: center;
  color: #c4c9d1;
  font-size: 12px;
  margin: 10px 0 0;
}

/* ============ 响应式 ============ */
@media (max-width: 880px) {
  .chat-sidebar { display: none; }
  .quick-grid { grid-template-columns: 1fr; }
  .msg-row { padding-left: 16px; padding-right: 16px; }
  .empty-title { font-size: 22px; }
  .user-bubble { max-width: 82%; }
}
</style>

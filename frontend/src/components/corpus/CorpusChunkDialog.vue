<template>
  <el-dialog
    v-model="visible"
    title="分块设置"
    width="880px"
    :close-on-click-modal="false"
    @closed="handleClosed"
  >
    <!-- 已有分块覆盖提示 -->
    <el-alert
      v-if="existingCount > 0"
      type="warning"
      :closable="false"
      show-icon
      class="cover-alert"
    >
      该语料已有 {{ existingCount }} 块分块结果，本次执行将覆盖重建
    </el-alert>

    <div class="chunk-layout">
      <!-- 左栏：配置 -->
      <div class="config-col">
        <div class="config-section-title">分块策略</div>
        <div class="strategy-list">
          <div
            v-for="s in STRATEGY_LIST"
            :key="s.key"
            class="strategy-card"
            :class="{ active: form.strategy === s.key }"
            @click="selectStrategy(s.key)"
          >
            <div class="strategy-name">{{ s.label }}</div>
            <div class="strategy-desc">{{ s.desc }}</div>
          </div>
        </div>

        <div class="config-section-title">分块参数</div>
        <div class="param-form">
          <div class="param-row">
            <span class="param-label">块大小（字符）</span>
            <el-input-number
              v-model="form.chunkSize"
              :min="100"
              :max="8000"
              :step="100"
              controls-position="right"
              style="width: 150px"
              @change="markStale"
            />
          </div>
          <div class="param-row">
            <span class="param-label">重叠（字符）</span>
            <el-input-number
              v-model="form.overlap"
              :min="0"
              :max="maxOverlap"
              :step="10"
              controls-position="right"
              style="width: 150px"
              @change="markStale"
            />
          </div>
          <div class="param-row" v-if="form.strategy === 'recursive'">
            <span class="param-label">分隔符</span>
            <el-input
              v-model="form.separator"
              placeholder="默认 \n\n，可输入 ###、--- 等"
              maxlength="20"
              style="width: 150px"
              @input="markStale"
            />
          </div>
        </div>

        <el-button class="preview-btn" :loading="previewing" @click="handlePreview">
          预览分块效果
        </el-button>
      </div>

      <!-- 右栏：预览 -->
      <div class="preview-col">
        <div class="preview-head">分块预览</div>
        <div class="preview-body">
          <template v-if="previewError">
            <div class="preview-error">
              <el-icon :size="26" color="#f53f3f"><WarningFilled /></el-icon>
              <p>{{ previewError }}</p>
            </div>
          </template>
          <template v-else-if="previewResult">
            <div class="preview-stats">
              共 <b>{{ previewResult.totalChunks }}</b> 块 · 平均
              <b>{{ previewResult.avgCharCount }}</b> 字
              <span v-if="previewResult.totalChunks > 10" class="preview-note">（仅展示前 10 块）</span>
            </div>
            <div class="preview-list">
              <div v-for="c in previewResult.previewChunks" :key="c.chunkIndex" class="preview-item">
                <div class="preview-item-meta">
                  <span class="idx">#{{ c.chunkIndex }}</span>
                  <span class="chars">{{ c.charCount }} 字</span>
                  <span class="offset">[{{ c.startOffset }}, {{ c.endOffset }}]</span>
                </div>
                <div class="preview-item-content" :class="{ expanded: expandedSet.has(c.chunkIndex) }">
                  {{ c.content }}
                </div>
                <a
                  v-if="c.content.length > 120"
                  class="expand-link"
                  @click="toggleExpand(c.chunkIndex)"
                >{{ expandedSet.has(c.chunkIndex) ? '收起' : '展开' }}</a>
              </div>
            </div>
            <div v-if="stale" class="stale-tip">
              <el-icon><InfoFilled /></el-icon>
              参数已变更，预览结果可能过期
            </div>
          </template>
          <template v-else>
            <div class="preview-empty">
              <el-icon :size="36" color="#c9cdd4"><DataLine /></el-icon>
              <p>选择策略与参数后点击「预览分块效果」</p>
              <p class="sub">预览不落库，可反复调整参数</p>
            </div>
          </template>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="executing" @click="handleExecute">执行分块</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { WarningFilled, InfoFilled, DataLine } from '@element-plus/icons-vue'
import { corpusApi, type CorpusChunkStats } from '@/api'

/* 策略元数据（与 Python splitter 注册表对齐） */
const STRATEGY_LIST = [
  { key: 'fixed', label: '固定长度滑窗', desc: '按窗口滑动，优先在句边界截断', size: 1000, overlap: 100 },
  { key: 'sentence', label: '句子感知合并', desc: '完整句子贪心合并，抽取友好', size: 1000, overlap: 100 },
  { key: 'recursive', label: '递归字符分割', desc: '分隔符层级降级，中文优先标点', size: 1000, overlap: 100 },
  { key: 'structure', label: '结构优先切分', desc: '标题切节 + 滑窗兜底', size: 2000, overlap: 200 }
]
const STRATEGY_MAP: Record<string, (typeof STRATEGY_LIST)[number]> =
  Object.fromEntries(STRATEGY_LIST.map((s) => [s.key, s]))

const props = defineProps<{
  modelValue: boolean
  /** 后端 Long ID 以字符串传输以保精度 */
  corpusId: number | string
  corpusTitle?: string
  /** 已有分块数（>0 显示覆盖提示） */
  existingCount: number
  /** 重新分块时回填的参数快照 */
  prefill?: { strategy: string; chunkSize?: number; overlap?: number; separator?: string } | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'done'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const form = reactive({
  strategy: 'fixed',
  chunkSize: 1000,
  overlap: 100,
  separator: ''
})

const previewing = ref(false)
const executing = ref(false)
const previewResult = ref<CorpusChunkStats | null>(null)
const previewError = ref('')
const stale = ref(false)
const expandedSet = reactive(new Set<number>())

const maxOverlap = computed(() => Math.floor(form.chunkSize / 2))

/* 打开时初始化：回填参数或取策略默认 */
watch(
  () => props.modelValue,
  (v) => {
    if (!v) return
    if (props.prefill) {
      form.strategy = props.prefill.strategy
      form.chunkSize = props.prefill.chunkSize ?? STRATEGY_MAP[props.prefill.strategy]?.size ?? 1000
      form.overlap = props.prefill.overlap ?? STRATEGY_MAP[props.prefill.strategy]?.overlap ?? 100
      form.separator = props.prefill.separator ?? ''
    } else {
      resetToDefaults('fixed')
    }
    previewResult.value = null
    previewError.value = ''
    stale.value = false
    expandedSet.clear()
  }
)

function resetToDefaults(key: string) {
  const meta = STRATEGY_MAP[key]
  form.strategy = key
  form.chunkSize = meta?.size ?? 1000
  form.overlap = meta?.overlap ?? 100
  form.separator = ''
}

function selectStrategy(key: string) {
  if (form.strategy === key) return
  resetToDefaults(key)
  markStale()
}

function markStale() {
  if (form.overlap > Math.floor(form.chunkSize / 2)) {
    form.overlap = Math.floor(form.chunkSize / 2)
  }
  if (previewResult.value || previewError.value) stale.value = true
}

function toggleExpand(idx: number) {
  expandedSet.has(idx) ? expandedSet.delete(idx) : expandedSet.add(idx)
}

async function handlePreview() {
  previewing.value = true
  previewError.value = ''
  try {
    const res = await corpusApi.chunkPreview(props.corpusId, buildParams())
    previewResult.value = res.data as CorpusChunkStats
    stale.value = false
    expandedSet.clear()
  } catch (e: any) {
    previewResult.value = null
    previewError.value = e?.message || '预览失败'
  } finally {
    previewing.value = false
  }
}

async function handleExecute() {
  executing.value = true
  try {
    await corpusApi.chunkCorpus(props.corpusId, buildParams())
    ElMessage.success('分块完成')
    visible.value = false
    emit('done')
  } catch (e: any) {
    ElMessage.error(e?.message || '分块失败')
  } finally {
    executing.value = false
  }
}

function buildParams() {
  return {
    strategy: form.strategy,
    chunkSize: form.chunkSize,
    overlap: form.overlap,
    separator: form.strategy === 'recursive' && form.separator ? form.separator : undefined
  }
}

function handleClosed() {
  previewResult.value = null
  previewError.value = ''
  stale.value = false
}
</script>

<style scoped>
.cover-alert {
  margin-bottom: 14px;
}

.chunk-layout {
  display: flex;
  gap: 18px;
  min-height: 420px;
}

/* 左栏配置 */
.config-col {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.config-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
  margin-bottom: 10px;
}

.strategy-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 18px;
}

.strategy-card {
  border: 1px solid var(--border-2);
  border-radius: 8px;
  padding: 10px 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.strategy-card:hover {
  border-color: var(--brand-primary);
}

.strategy-card.active {
  border-color: var(--brand-primary);
  background: rgba(22, 93, 255, 0.04);
  box-shadow: 0 0 0 1px var(--brand-primary) inset;
}

.strategy-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
}

.strategy-card.active .strategy-name {
  color: var(--brand-primary);
}

.strategy-desc {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 2px;
}

.param-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.param-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.param-label {
  font-size: 13px;
  color: var(--text-2);
}

.preview-btn {
  margin-top: 20px;
  width: 100%;
}

/* 右栏预览 */
.preview-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  background: #fafbfc;
}

.preview-head {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-2);
}

.preview-body {
  flex: 1;
  overflow: auto;
  padding: 12px 16px;
  max-height: 460px;
}

.preview-stats {
  font-size: 13px;
  color: var(--text-2);
  margin-bottom: 10px;
}

.preview-stats b {
  color: var(--brand-primary);
}

.preview-note {
  font-size: 12px;
  color: var(--text-3);
}

.preview-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.preview-item {
  background: #fff;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  padding: 10px 14px;
}

.preview-item-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  margin-bottom: 6px;
}

.preview-item-meta .idx {
  font-weight: 600;
  color: var(--brand-primary);
}

.preview-item-meta .chars {
  color: var(--text-3);
}

.preview-item-meta .offset {
  color: var(--text-3);
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}

.preview-item-content {
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  white-space: pre-wrap;
  word-break: break-all;
}

.preview-item-content.expanded {
  display: block;
  -webkit-line-clamp: unset;
  max-height: 220px;
  overflow: auto;
}

.expand-link {
  font-size: 12px;
  color: var(--brand-primary);
  cursor: pointer;
  margin-top: 4px;
  display: inline-block;
}

.stale-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  background: rgba(255, 125, 0, 0.06);
  color: #ff7d00;
  font-size: 12px;
}

.preview-empty {
  height: 100%;
  min-height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--text-3);
  font-size: 13px;
}

.preview-empty .sub {
  font-size: 12px;
}

.preview-error {
  height: 100%;
  min-height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-2);
  font-size: 13px;
  text-align: center;
  padding: 0 20px;
}
</style>

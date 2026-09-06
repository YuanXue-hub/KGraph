<template>
  <el-drawer
    v-model="visible"
    :title="`分块结果 · ${corpusTitle || ''}`"
    size="620px"
    @open="loadChunks"
  >
    <!-- 统计条 -->
    <div class="stats-bar" v-if="stats">
      <el-tag size="small" effect="plain" type="primary">{{ strategyLabel }}</el-tag>
      <span class="stat-item"><b>{{ stats.total }}</b> 块</span>
      <span class="stat-item">平均 <b>{{ stats.avgCharCount }}</b> 字</span>
      <span class="stat-item">{{ stats.chunkSize }}/{{ stats.overlap }}</span>
      <span class="stat-item" v-if="stats.separator">分隔符 {{ stats.separator }}</span>
      <span class="stat-time">生成于 {{ formatTime(stats.createTime) }}</span>
    </div>

    <!-- 块列表 -->
    <div v-loading="loading" class="chunk-list">
      <div v-for="c in chunks" :key="c.chunkIndex" class="chunk-item">
        <div class="chunk-meta">
          <span class="idx">#{{ c.chunkIndex }}</span>
          <span class="offset">[{{ c.startOffset }}, {{ c.endOffset }}]</span>
          <span class="chars">{{ c.charCount }} 字</span>
          <a
            v-if="c.content.length > 80"
            class="expand-link"
            @click="toggleExpand(c.chunkIndex)"
          >{{ expandedSet.has(c.chunkIndex) ? '收起' : '展开' }}</a>
        </div>
        <div class="chunk-content" :class="{ expanded: expandedSet.has(c.chunkIndex) }">
          {{ c.content }}
        </div>
      </div>
      <div v-if="!loading && chunks.length === 0" class="empty-state">
        <p>暂无分块数据</p>
      </div>
    </div>

    <div class="pagination-wrapper" v-if="total > pageSize">
      <el-pagination
        v-model:current-page="pageNum"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadChunks"
      />
    </div>

    <template #footer>
      <el-button @click="handleRechunk">重新分块</el-button>
      <el-button type="danger" plain :disabled="total === 0" @click="handleClear">清空分块</el-button>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { corpusApi, type CorpusChunkItem } from '@/api'

const STRATEGY_LABELS: Record<string, string> = {
  fixed: '固定长度滑窗',
  sentence: '句子感知合并',
  recursive: '递归字符分割',
  structure: '结构优先切分'
}

const props = defineProps<{
  modelValue: boolean
  /** 后端 Long ID 以字符串传输以保精度 */
  corpusId: number | string
  corpusTitle?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'rechunk', prefill: { strategy: string; chunkSize?: number; overlap?: number; separator?: string }): void
  (e: 'cleared'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const loading = ref(false)
const chunks = ref<CorpusChunkItem[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = 20
const expandedSet = reactive(new Set<number>())
const stats = ref<{
  strategy: string; chunkSize: number; overlap: number
  separator: string; total: number; avgCharCount: number; createTime: string
} | null>(null)

const strategyLabel = computed(() =>
  STRATEGY_LABELS[stats.value?.strategy || ''] || stats.value?.strategy || '-'
)

async function loadChunks() {
  loading.value = true
  try {
    const res = await corpusApi.pageChunks(props.corpusId, { pageNum: pageNum.value, pageSize })
    const records: CorpusChunkItem[] = res.data?.records || []
    total.value = Number(res.data?.total) || records.length
    chunks.value = records
    // 快照字段从任一记录推导（同语料全部分块共享参数快照）
    const first = records[0]
    if (first) {
      stats.value = {
        strategy: first.strategy || '',
        chunkSize: first.chunkSize ?? 0,
        overlap: first.overlap ?? 0,
        separator: first.customSeparator || '',
        total: total.value,
        avgCharCount: records.reduce((s, c) => s + (c.charCount || 0), 0) / records.length,
        createTime: first.createTime || ''
      }
    } else {
      stats.value = null
    }
    expandedSet.clear()
  } finally {
    loading.value = false
  }
}

function toggleExpand(idx: number) {
  expandedSet.has(idx) ? expandedSet.delete(idx) : expandedSet.add(idx)
}

function handleRechunk() {
  const s = stats.value
  emit('rechunk', {
    strategy: s?.strategy || 'fixed',
    chunkSize: s?.chunkSize,
    overlap: s?.overlap,
    separator: s?.separator || undefined
  })
  visible.value = false
}

async function handleClear() {
  try {
    await ElMessageBox.confirm(
      `将删除 ${total.value} 个分块，分块可随时重新生成。`,
      '清空分块',
      { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' }
    )
    await corpusApi.clearChunks(props.corpusId)
    ElMessage.success('分块已清空')
    total.value = 0
    chunks.value = []
    stats.value = null
    emit('cleared')
  } catch {}
}

function formatTime(t?: string) {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}
</script>

<style scoped>
.stats-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid var(--border-2);
  border-radius: 8px;
  background: #fafbfc;
  margin-bottom: 14px;
  font-size: 13px;
  color: var(--text-2);
}

.stats-bar b {
  color: var(--brand-primary);
}

.stat-time {
  font-size: 12px;
  color: var(--text-3);
  margin-left: auto;
}

.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 200px;
}

.chunk-item {
  border: 1px solid var(--border-2);
  border-radius: 8px;
  padding: 10px 14px;
}

.chunk-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  margin-bottom: 6px;
}

.chunk-meta .idx {
  font-weight: 600;
  color: var(--brand-primary);
}

.chunk-meta .offset {
  color: var(--text-3);
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}

.chunk-meta .chars {
  color: var(--text-3);
}

.expand-link {
  color: var(--brand-primary);
  cursor: pointer;
  margin-left: auto;
}

.chunk-content {
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

.chunk-content.expanded {
  display: block;
  -webkit-line-clamp: unset;
  max-height: 300px;
  overflow: auto;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  padding: 12px 0 4px;
}

.empty-state {
  display: flex;
  justify-content: center;
  padding: 60px 0;
  color: var(--text-3);
  font-size: 13px;
}
</style>

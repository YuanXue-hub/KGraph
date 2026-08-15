<template>
  <div class="page-container">
    <!-- Hero 欢迎区 -->
    <div class="hero">
      <div class="hero-bg"></div>
      <div class="hero-content">
        <div class="hero-logo-wrap">
          <KgLogo :size="56" class="hero-logo" />
        </div>
        <div class="hero-text">
          <h1 class="hero-title">知识图谱 · 构建智能认知</h1>
          <p class="hero-desc">一站式知识图谱构建、管理与可视化探索平台，驱动数据智能生产力</p>
        </div>
        <div class="hero-actions">
          <el-button type="primary" size="large" round @click="goTo('/extraction')">
            开始抽取
          </el-button>
          <el-button size="large" round @click="goTo('/explore')">
            探索图谱
          </el-button>
        </div>
      </div>
    </div>

    <!-- 数据指标卡片 -->
    <el-row :gutter="16" class="stat-row" v-loading="loading">
      <el-col :span="6" v-for="(s, i) in stats" :key="i">
        <div class="stat-card">
          <div class="stat-top">
            <div class="stat-icon" :style="{ background: s.bg, color: s.color }">
              <el-icon :size="20"><component :is="s.icon" /></el-icon>
            </div>
            <div class="stat-trend" :style="{ color: s.color }">
              <el-icon :size="12"><Top /></el-icon>
            </div>
          </div>
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-bar" :style="{ background: s.bg }"></div>
        </div>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="14">
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">抽取任务趋势（近 7 天）</span>
            <el-tag size="small" type="info">按日统计</el-tag>
          </div>
          <div class="panel-body">
            <div ref="trendChartRef" class="chart-box"></div>
          </div>
        </div>
      </el-col>
      <el-col :span="10">
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">抽取方式分布</span>
            <el-tag size="small" type="info">占比</el-tag>
          </div>
          <div class="panel-body">
            <div ref="pieChartRef" class="chart-box"></div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 快捷入口 + 最近任务 -->
    <el-row :gutter="16" class="mid-row" align="stretch">
      <el-col :span="12">
        <div class="panel mid-panel">
          <div class="panel-header">
            <span class="panel-title">核心功能</span>
          </div>
          <div class="panel-body">
            <el-row :gutter="12" class="feature-row">
              <el-col :span="12" v-for="(f, i) in features" :key="i">
                <div class="feature-card" @click="goTo(f.path)">
                  <div class="feature-icon" :style="{ background: f.color }">
                    <el-icon :size="22" color="#fff"><component :is="f.icon" /></el-icon>
                  </div>
                  <div class="feature-info">
                    <h3 class="feature-title">{{ f.title }}</h3>
                    <p class="feature-text">{{ f.text }}</p>
                  </div>
                </div>
              </el-col>
            </el-row>
          </div>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="panel mid-panel">
          <div class="panel-header">
            <span class="panel-title">最近抽取任务</span>
            <el-button size="small" link @click="goTo('/extraction')">全部</el-button>
          </div>
          <div class="panel-body">
            <el-table :data="recentTasks" size="small" :max-height="240">
              <el-table-column prop="extractionType" label="类型" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="taskTypeColor(row.extractionType)" size="small">{{ row.extractionType || 'LLM' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="duration" label="耗时(ms)" width="90" align="center" />
              <el-table-column prop="status" label="状态" width="70" align="center">
                <template #default="{ row }">
                  <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="createTime" label="时间" min-width="120">
                <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!recentTasks.length" description="暂无抽取任务" :image-size="60" />
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 抽取能力矩阵 -->
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">知识抽取能力矩阵</span>
        <el-tag size="small" type="info">4 种抽取方式</el-tag>
      </div>
      <div class="panel-body">
        <el-row :gutter="16">
          <el-col :span="6" v-for="(m, i) in extractMatrix" :key="i">
            <div class="matrix-card" @click="goTo(m.path)">
              <div class="matrix-tag" :style="{ background: m.bg, color: m.color }">{{ m.tag }}</div>
              <h3 class="matrix-title">{{ m.title }}</h3>
              <p class="matrix-desc">{{ m.desc }}</p>
              <div class="matrix-foot">
                <el-icon :size="16" :color="m.color"><component :is="m.icon" /></el-icon>
                <span class="matrix-arrow">立即使用</span>
              </div>
            </div>
          </el-col>
        </el-row>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, nextTick, defineComponent, h } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import {
  Folder, Share, MagicStick, DataAnalysis,
  Document, Cpu, Connection, Top,
  Collection, Grid
} from '@element-plus/icons-vue'
import { projectApi, modelApi, corpusApi, exploreApi, extractionApi } from '@/api'
import KgLogo from '@/components/KgLogo.vue'

// 自定义机器人图标组件
const RobotIcon = defineComponent({
  name: 'RobotIcon',
  render() {
    return h('svg', { viewBox: '0 0 24 24', width: '1em', height: '1em', fill: 'currentColor' }, [
      h('path', { d: 'M12 2a2 2 0 0 1 2 2v1h1a3 3 0 0 1 3 3v1h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-1H4a1 1 0 0 1-1-1V10a1 1 0 0 1 1-1h1V8a3 3 0 0 1 3-3h1V4a2 2 0 0 1 2-2zM9 9a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm6 0a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm-3 4a2 2 0 0 0-2 2v1h4v-1a2 2 0 0 0-2-2z' })
    ])
  }
})

const router = useRouter()
const loading = ref(false)

const stats = ref([
  { label: '项目总数', value: 0, icon: Folder, color: '#165dff', bg: '#e8f3ff' },
  { label: '模型总数', value: 0, icon: Share, color: '#00b42c', bg: '#e8ffea' },
  { label: '实体总数', value: 0, icon: Connection, color: '#ff7d00', bg: '#fff7e8' },
  { label: '抽取任务', value: 0, icon: MagicStick, color: '#722ed1', bg: '#f5e8ff' },
])

const features = [
  { title: '知识图谱管理', text: '多项目管理，结构化组织', icon: Folder, color: '#165dff', path: '/project' },
  { title: '图谱模型管理', text: '定义实体、关系及属性', icon: Share, color: '#00b42c', path: '/model' },
  { title: '知识抽取', text: '四种抽取方式', icon: MagicStick, color: '#722ed1', path: '/extraction' },
  { title: '图谱探索', text: '图可视化交互探索', icon: DataAnalysis, color: '#ff7d00', path: '/explore' },
]

const extractMatrix = [
  { tag: 'STRUCT', title: '结构化抽取', desc: '上传 CSV/Excel 文件，通过字段映射转化为图谱实例。', icon: Grid, color: '#ff7d00', bg: '#fff7e8', path: '/extraction/structure' },
  { tag: 'KOS', title: 'KOS 抽取', desc: '基于知识组织体系的术语识别与概念归类，词表驱动。', icon: Collection, color: '#00b42c', bg: '#e8ffea', path: '/extraction/kos' },
  { tag: 'DL', title: '深度学习抽取', desc: 'BiLSTM-CRF 命名实体识别 + 神经网络关系抽取。', icon: Cpu, color: '#722ed1', bg: '#f5e8ff', path: '/extraction/dl' },
  { tag: 'LLM', title: 'LLM 抽取', desc: '基于大语言模型的智能实体关系抽取，支持自然语言理解。', icon: RobotIcon, color: '#165dff', bg: '#e8f3ff', path: '/extraction' },
]

const recentTasks = ref<any[]>([])
const allTasks = ref<any[]>([])

const trendChartRef = ref<HTMLElement>()
const pieChartRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null

function goTo(path: string) {
  router.push(path)
}

async function loadStats() {
  loading.value = true
  try {
    // 并行查询：项目（全量以遍历模型）、语料、全部抽取任务（用于趋势和分布）
    const [projectRes, corpusRes, taskRes] = await Promise.all([
      projectApi.list({ pageNum: 1, pageSize: 1000 }),
      corpusApi.list({ pageNum: 1, pageSize: 1 }),
      extractionApi.list({ pageNum: 1, pageSize: 1000, sortField: 'createTime', sortOrder: 'descend' }),
    ])

    const allProjects = projectRes.data?.records || projectRes.data || []
    stats.value[0].value = projectRes.data?.total || allProjects.length
    const corpusTotal = corpusRes.data?.total || (corpusRes.data?.records || corpusRes.data || []).length
    stats.value[3].value = taskRes.data?.total || (taskRes.data?.records || []).length
    allTasks.value = taskRes.data?.records || taskRes.data || []
    recentTasks.value = allTasks.value.slice(0, 4)

    // 遍历项目获取模型，再聚合实体数
    let modelCount = 0
    let nodeCount = 0
    for (const p of allProjects) {
      try {
        const mRes = await modelApi.list(p.id)
        const models = mRes.data?.records || mRes.data || []
        modelCount += models.length
        for (const m of models) {
          try {
            const sRes = await exploreApi.stats(m.id)
            const sd = sRes.data || {}
            nodeCount += Number(sd.nodeCount) || Number(sd.nodes) || 0
          } catch {
            // 单个模型统计失败忽略
          }
        }
      } catch {
        // 单个项目模型查询失败忽略
      }
    }
    stats.value[1].value = modelCount
    stats.value[2].value = nodeCount
    // 语料数暂存到模型数后展示（避免UI改动）
    // 保留 corpusTotal 备用

    // 渲染图表
    await nextTick()
    renderTrendChart()
    renderPieChart()
  } finally {
    loading.value = false
  }
}

function renderTrendChart() {
  if (!trendChartRef.value) return
  trendChart = echarts.init(trendChartRef.value)
  // 近 7 天任务趋势
  const days: string[] = []
  const counts: number[] = []
  const now = new Date()
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(now.getDate() - i)
    const key = `${d.getMonth() + 1}/${d.getDate()}`
    days.push(key)
    const dayStr = d.toISOString().slice(0, 10)
    const count = allTasks.value.filter(t => {
      const ct = String(t.createTime || '').replace('T', ' ').substring(0, 10)
      return ct === dayStr
    }).length
    counts.push(count)
  }
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: days,
      axisLine: { lineStyle: { color: '#e5e6eb' } },
      axisLabel: { color: '#86909c', fontSize: 12 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#f0f2f5', type: 'dashed' } },
      axisLabel: { color: '#86909c', fontSize: 12 },
    },
    series: [{
      name: '任务数',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      data: counts,
      lineStyle: { width: 3, color: '#165dff' },
      itemStyle: { color: '#165dff' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(22,93,255,0.25)' },
          { offset: 1, color: 'rgba(22,93,255,0.02)' },
        ]),
      },
    }],
  })
}

function renderPieChart() {
  if (!pieChartRef.value) return
  pieChart = echarts.init(pieChartRef.value)
  // 抽取方式分布
  const typeMap: Record<string, number> = {}
  allTasks.value.forEach(t => {
    const tp = t.extractionType || 'LLM'
    typeMap[tp] = (typeMap[tp] || 0) + 1
  })
  const colorMap: Record<string, string> = {
    LLM: '#165dff', KOS: '#00b42c', DL: '#722ed1', STRUCTURE: '#ff7d00',
  }
  const data = Object.entries(typeMap).map(([name, value]) => ({
    name, value, itemStyle: { color: colorMap[name] || '#86909c' },
  }))
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: {
      bottom: 10,
      icon: 'circle',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: '#4e5969', fontSize: 12 },
    },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '42%'],
      avoidLabelOverlap: false,
      label: { show: false },
      labelLine: { show: false },
      data: data.length ? data : [{ name: '暂无数据', value: 1, itemStyle: { color: '#e5e6eb' } }],
    }],
  })
}

function handleResize() {
  trendChart?.resize()
  pieChart?.resize()
}

function taskTypeColor(type: string): any {
  return { DL: 'danger', KOS: 'success', STRUCTURE: 'warning' }[type] || 'primary'
}
function statusType(status: number): any {
  return { 1: 'warning', 2: 'success', 3: 'danger' }[status] || 'info'
}
function statusText(status: number): string {
  return { 1: '进行中', 2: '成功', 3: '失败' }[status] || '未知'
}
function formatTime(t?: string): string {
  if (!t) return '-'
  return String(t).replace('T', ' ').substring(0, 19)
}

onMounted(() => {
  loadStats()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  pieChart?.dispose()
})
</script>

<style scoped>
.page-container {
  padding: 20px 24px;
  height: 100%;
  overflow: auto;
  max-width: 1440px;
  margin: 0 auto;
}

/* Hero 区 */
.hero {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  margin-bottom: 18px;
  background: linear-gradient(135deg, #f7f9fc 0%, #eef2f9 50%, #e8edf7 100%);
}

.hero-bg {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(ellipse 60% 50% at 15% 25%, rgba(77, 107, 254, 0.12) 0%, transparent 55%),
    radial-gradient(ellipse 50% 40% at 85% 75%, rgba(124, 77, 255, 0.1) 0%, transparent 55%),
    radial-gradient(circle at 50% 50%, rgba(99, 102, 241, 0.04) 0%, transparent 70%);
  opacity: 1;
}

.hero-bg::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(22, 93, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(22, 93, 255, 0.04) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: radial-gradient(ellipse 80% 70% at 50% 50%, #000 30%, transparent 80%);
  -webkit-mask-image: radial-gradient(ellipse 80% 70% at 50% 50%, #000 30%, transparent 80%);
}

.hero-content {
  position: relative;
  padding: 36px 40px;
  display: flex;
  align-items: center;
  gap: 20px;
}

.hero-logo-wrap {
  flex-shrink: 0;
  width: 76px;
  height: 76px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(22, 93, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(22, 93, 255, 0.12);
}

.hero-logo {
  filter: drop-shadow(0 2px 6px rgba(99, 102, 241, 0.4));
}

.hero-text {
  flex: 1;
}

.hero-title {
  font-size: 26px;
  font-weight: 700;
  color: #1d2129;
  margin-bottom: 6px;
  letter-spacing: 1px;
}

.hero-desc {
  font-size: 14px;
  color: #4e5969;
}

.hero-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

/* 浅色背景上的按钮 */
.hero-actions :deep(.el-button--primary) {
  background: linear-gradient(135deg, #4d6bfe 0%, #6366f1 100%) !important;
  border-color: transparent !important;
  box-shadow: 0 4px 14px rgba(77, 107, 254, 0.3);
}

.hero-actions :deep(.el-button--primary:hover) {
  box-shadow: 0 6px 20px rgba(77, 107, 254, 0.45);
}

.hero-actions :deep(.el-button:not(.el-button--primary)) {
  background: #fff !important;
  border: 1px solid #e5e6eb !important;
  color: #4e5969 !important;
}

.hero-actions :deep(.el-button:not(.el-button--primary):hover) {
  border-color: #4d6bfe !important;
  color: #4d6bfe !important;
  background: #f0f4ff !important;
}

/* 统计卡片 */
.stat-row {
  margin-bottom: 18px;
}

.stat-card {
  background: #fff;
  border-radius: 14px;
  border: 1px solid #f0f2f5;
  padding: 20px;
  position: relative;
  overflow: hidden;
  transition: all 0.2s;
}

.stat-card:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.stat-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-trend {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
}

.stat-value {
  font-size: 30px;
  font-weight: 700;
  color: #1d2129;
  line-height: 1.1;
}

.stat-label {
  font-size: 13px;
  color: #86909c;
  margin-top: 4px;
}

.stat-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
}

/* 图表区 */
.chart-row {
  margin-bottom: 18px;
}

.chart-box {
  width: 100%;
  height: 280px;
}

/* 通用面板 */
.panel {
  background: #fff;
  border-radius: 14px;
  border: 1px solid #f0f2f5;
  overflow: hidden;
  margin-bottom: 18px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f2f5;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
}

.panel-body {
  padding: 18px 20px;
}

/* 快捷入口卡片 */
.feature-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid #f0f2f5;
  cursor: pointer;
  transition: all 0.2s;
}

.feature-card:hover {
  border-color: #c9cdd4;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}

.feature-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.feature-title {
  font-size: 14px;
  font-weight: 600;
  color: #1d2129;
  margin-bottom: 2px;
}

.feature-text {
  font-size: 12px;
  color: #86909c;
}

/* 抽取能力矩阵 */
.matrix-card {
  padding: 20px;
  border-radius: 12px;
  border: 1px solid #f0f2f5;
  cursor: pointer;
  transition: all 0.2s;
  height: 100%;
}

.matrix-card:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
  border-color: #d9dce0;
}

.matrix-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 12px;
}

.matrix-title {
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
  margin-bottom: 8px;
}

.matrix-desc {
  font-size: 12px;
  color: #86909c;
  line-height: 1.6;
  margin-bottom: 14px;
  min-height: 48px;
}

.matrix-foot {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #4e5969;
}

.matrix-arrow {
  font-weight: 500;
}

.mid-row {
  margin-bottom: 0;
  align-items: stretch;
}

.mid-row :deep(.el-col) {
  display: flex;
}

.mid-panel {
  width: 100%;
  height: 100%;
  margin-bottom: 0;
  display: flex;
  flex-direction: column;
}

.mid-panel .panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.feature-row {
  flex: 1;
  align-items: stretch;
}

.feature-row :deep(.el-col) {
  display: flex;
}

.mid-panel .feature-card {
  width: 100%;
  flex: 1;
}
</style>

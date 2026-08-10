<template>
  <div class="explore-page">
    <!-- 左侧: 控制面板 -->
    <div class="explore-left">
      <div class="left-header">
        <span class="left-title">图谱探索</span>
      </div>
      <div class="left-body">
        <div class="control-group">
          <label class="control-label">选择模型</label>
          <el-select
            v-model="modelId"
            placeholder="选择图谱模型"
            filterable
            style="width: 100%"
            @change="onModelChange"
          >
            <el-option-group
              v-for="g in modelGrouped"
              :key="g.projectId"
              :label="g.projectName"
            >
              <el-option
                v-for="m in g.models"
                :key="m.id"
                :label="m.modelName"
                :value="m.id"
              />
            </el-option-group>
          </el-select>
        </div>

        <div class="control-group">
          <label class="control-label">搜索节点</label>
          <el-input
            v-model="keyword"
            placeholder="输入关键词搜索"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #append>
              <el-button :icon="Search" @click="handleSearch" />
            </template>
          </el-input>
        </div>

        <el-divider content-position="left">统计信息</el-divider>

        <div class="stat-list" v-if="stats">
          <div class="stat-item">
            <el-icon color="#409eff"><Coin /></el-icon>
            <span class="stat-label">节点数</span>
            <span class="stat-value">{{ stats.nodeCount ?? 0 }}</span>
          </div>
          <div class="stat-item">
            <el-icon color="#67c23a"><Connection /></el-icon>
            <span class="stat-label">关系数</span>
            <span class="stat-value">{{ stats.relationCount ?? 0 }}</span>
          </div>
        </div>

        <div ref="pieRef" class="pie-chart" v-if="hasTypeDist"></div>

        <el-empty v-if="!stats" description="选择模型后查看统计" :image-size="60" />

        <el-divider content-position="left">操作提示</el-divider>
        <ul class="tips">
          <li>单击节点/关系：查看属性</li>
          <li>双击节点：展开邻居</li>
          <li>滚轮：缩放图谱</li>
          <li>拖拽：移动画布/节点</li>
        </ul>
      </div>
    </div>

    <!-- 中间: 图谱可视化 -->
    <div class="explore-center">
      <div class="graph-toolbar">
        <span class="graph-title">图谱可视化</span>
        <div>
          <el-button size="small" :icon="Refresh" @click="reloadGraph">重新加载</el-button>
          <el-button size="small" :icon="FullScreen" @click="fitView">适应画布</el-button>
        </div>
      </div>
      <div ref="graphRef" class="graph-canvas" v-loading="graphLoading"></div>
      <el-empty v-if="!modelId" description="请先选择模型" class="graph-empty" />
    </div>

    <!-- 右侧: 属性详情面板 -->
    <div class="explore-detail" :class="{ 'detail-collapsed': !selectedItem }">
      <div class="detail-header">
        <span class="detail-title">{{ detailTitle }}</span>
        <el-button
          v-if="selectedItem"
          size="small"
          :icon="Close"
          link
          @click="clearSelection"
        />
      </div>
      <div class="detail-body" v-if="selectedItem">
        <!-- 类型徽章 -->
        <div class="detail-section">
          <div class="detail-section-title">类型</div>
          <el-tag
            :color="selectedItem.color"
            effect="dark"
            size="large"
            class="detail-type-tag"
          >
            {{ selectedItem.type || selectedItem.label || '未知' }}
          </el-tag>
        </div>

        <!-- 名称/标签 -->
        <div class="detail-section" v-if="selectedItem.name">
          <div class="detail-section-title">名称</div>
          <div class="detail-name">{{ selectedItem.name }}</div>
        </div>

        <!-- 属性列表 -->
        <div class="detail-section">
          <div class="detail-section-title">属性</div>
          <div class="detail-props" v-if="detailProps.length">
            <div class="detail-prop-row" v-for="prop in detailProps" :key="prop.key">
              <span class="detail-prop-key">{{ prop.key }}</span>
              <span class="detail-prop-value" :title="prop.value">{{ prop.value }}</span>
            </div>
          </div>
          <el-empty v-else description="无属性" :image-size="40" />
        </div>

        <!-- 关系特有：端点信息 -->
        <template v-if="selectedItem.kind === 'edge'">
          <div class="detail-section">
            <div class="detail-section-title">起点</div>
            <div class="detail-endpoint">{{ selectedItem.sourceName || selectedItem.source }}</div>
          </div>
          <div class="detail-section">
            <div class="detail-section-title">终点</div>
            <div class="detail-endpoint">{{ selectedItem.targetName || selectedItem.target }}</div>
          </div>
        </template>
      </div>
      <div class="detail-empty" v-else>
        <el-empty description="点击节点或关系查看详情" :image-size="80" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, computed, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, FullScreen, Coin, Connection, Close } from '@element-plus/icons-vue'
import G6 from '@antv/g6'
import * as echarts from 'echarts'
import { projectApi, modelApi, exploreApi } from '@/api'

interface Project { id: string; projectName: string }
interface ModelInfo { id: string; modelName: string; projectId?: string }
interface Stats {
  nodeCount?: number
  relationCount?: number
  typeDistribution?: Record<string, number>
}

interface DetailItem {
  kind: 'node' | 'edge'
  id: string
  name?: string
  type?: string
  label?: string
  color?: string
  source?: string
  target?: string
  sourceName?: string
  targetName?: string
  rawData: Record<string, any>
}

const projects = ref<Project[]>([])
const allModels = ref<ModelInfo[]>([])
const modelId = ref<string | undefined>()
const keyword = ref('')
const stats = ref<Stats | null>(null)
const graphLoading = ref(false)
const selectedItem = ref<DetailItem | null>(null)

const graphRef = ref<HTMLElement>()
const pieRef = ref<HTMLElement>()
let graph: any = null
let pieChart: any = null
const nodeSet = new Map<string, any>()
const edgeSet = new Map<string, any>()

const modelGrouped = computed(() => {
  const map: Record<string, ModelInfo[]> = {}
  allModels.value.forEach((m) => {
    const pid = String(m.projectId || 0)
    if (!map[pid]) map[pid] = []
    map[pid].push(m)
  })
  return Object.keys(map).map((pid) => {
    const project = projects.value.find((p) => String(p.id) === pid)
    return {
      projectId: pid,
      projectName: project?.projectName || '未知项目',
      models: map[pid]
    }
  })
})

const hasTypeDist = computed(() => {
  return stats.value?.typeDistribution && Object.keys(stats.value.typeDistribution).length > 0
})

const detailTitle = computed(() => {
  if (!selectedItem.value) return '详情'
  return selectedItem.value.kind === 'node' ? '节点详情' : '关系详情'
})

const detailProps = computed(() => {
  if (!selectedItem.value) return []
  const raw = selectedItem.value.rawData || {}
  // 过滤掉系统字段和已在上方展示的字段（type/name 已在类型/名称区域展示）
  const excludeKeys = new Set([
    'elementId', 'labels', 'startNodeElementId', 'endNodeElementId',
    'relationType', 'modelId', 'createTime', 'type', 'name'
  ])
  return Object.entries(raw)
    .filter(([k]) => !excludeKeys.has(k))
    .map(([k, v]) => ({
      key: k,
      value: formatValue(v)
    }))
})

function formatValue(v: any): string {
  if (v === null || v === undefined) return '-'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

async function loadProjectsAndModels() {
  const pRes = await projectApi.list({ pageNum: 1, pageSize: 100 })
  projects.value = pRes.data?.records || pRes.data || []
  const mRes = await Promise.all(
    projects.value.map((p) => modelApi.list(p.id).then((r) => r.data?.records || r.data || []).catch(() => []))
  )
  allModels.value = mRes.flat().map((m: any) => ({
    id: m.id,
    modelName: m.modelName,
    projectId: m.projectId
  }))
}

async function onModelChange() {
  if (!modelId.value) return
  selectedItem.value = null
  await loadStats()
  await loadInitialNodes()
}

async function loadStats() {
  if (!modelId.value) return
  const res = await exploreApi.stats(modelId.value)
  stats.value = res.data
  nextTick(() => renderPie())
}

function renderPie() {
  if (!pieRef.value || !hasTypeDist.value) return
  if (pieChart) pieChart.dispose()
  pieChart = echarts.init(pieRef.value)
  const dist = stats.value?.typeDistribution || {}
  const data = Object.entries(dist).map(([name, value]) => ({ name, value }))
  pieChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { type: 'scroll', bottom: 0, textStyle: { fontSize: 11 } },
    series: [
      {
        name: '类型分布',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        label: { fontSize: 11 },
        data
      }
    ]
  })
}

async function loadInitialNodes() {
  if (!modelId.value) return
  graphLoading.value = true
  try {
    const res = await exploreApi.nodes(modelId.value, 100)
    const data = res.data || {}
    const nodes = data.nodes || []
    const edges = data.edges || data.relations || []
    nodeSet.clear()
    edgeSet.clear()
    initGraph()
    nodes.forEach((n: any) => {
      const id = String(n.elementId ?? n.id)
      nodeSet.set(id, transformNode(n))
    })
    edges.forEach((e: any) => {
      const key = `${e.source}-${e.target}-${e.label || ''}`
      edgeSet.set(key, transformEdge(e))
    })
    refreshGraph()
  } finally {
    graphLoading.value = false
  }
}

function transformNode(n: any) {
  const id = String(n.elementId ?? n.id)
  const type = n.type || n.group || 'default'
  return {
    id,
    label: n.name || n.label || n.id,
    group: type,
    style: { fill: getColorByType(type) },
    dataType: type,
    rawData: n
  }
}

function transformEdge(e: any) {
  const source = String(e.source)
  const target = String(e.target)
  const label = e.label || e.relation || ''
  return {
    id: `${source}-${target}-${label}-${Math.random().toString(36).slice(2, 6)}`,
    source,
    target,
    label,
    rawData: e
  }
}

const TYPE_COLORS = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#9c27b0', '#00bcd4', '#ff9800', '#795548', '#607d8b']
function getColorByType(type?: string) {
  if (!type) return '#409eff'
  let hash = 0
  for (let i = 0; i < type.length; i++) hash = type.charCodeAt(i) + ((hash << 5) - hash)
  return TYPE_COLORS[Math.abs(hash) % TYPE_COLORS.length]
}

function initGraph() {
  if (graph) {
    graph.destroy()
    graph = null
  }
  if (!graphRef.value) return
  const width = graphRef.value.offsetWidth
  const height = graphRef.value.offsetHeight
  graph = new G6.Graph({
    container: graphRef.value,
    width: width || 800,
    height: height || 600,
    modes: {
      default: ['drag-canvas', 'zoom-canvas', 'drag-node']
    },
    layout: {
      type: 'force',
      preventOverlap: true,
      nodeStrength: -120,
      edgeStrength: 0.7,
      collideStrength: 0.8,
      alpha: 0.3,
      linkDistance: 140
    },
    defaultNode: {
      size: 40,
      style: { fill: '#409eff', stroke: '#fff', lineWidth: 2 },
      labelCfg: { style: { fill: '#303133', fontSize: 11 }, position: 'bottom' }
    },
    defaultEdge: {
      type: 'line',
      style: { stroke: '#c0c4cc', lineWidth: 1.5, endArrow: { path: G6.Arrow.triangle(6, 8, 0), fill: '#c0c4cc' } },
      labelCfg: { style: { fill: '#909399', fontSize: 10 } }
    },
    nodeStateStyles: {
      selected: { stroke: '#409eff', lineWidth: 3, shadowColor: '#409eff', shadowBlur: 10 }
    },
    edgeStateStyles: {
      selected: { stroke: '#409eff', lineWidth: 2.5 }
    }
  })

  // 单击节点：选中并显示详情
  graph.on('node:click', (evt: any) => {
    const node = evt.item
    const model = node.getModel()
    selectNode(model)
  })

  // 单击边：选中并显示详情
  graph.on('edge:click', (evt: any) => {
    const edge = evt.item
    const model = edge.getModel()
    selectEdge(model)
  })

  // 双击节点：展开邻居
  graph.on('node:dblclick', (evt: any) => {
    const node = evt.item
    const model = node.getModel()
    expandNeighbors(model.id)
  })

  // 点击画布空白：取消选中
  graph.on('canvas:click', () => {
    clearSelection()
  })
}

function selectNode(model: any) {
  // 清除之前的选中状态
  clearGraphStates()
  graph.setItemState(model.id, 'selected', true)
  const raw = model.rawData || {}
  selectedItem.value = {
    kind: 'node',
    id: model.id,
    name: raw.name || model.label,
    type: raw.type || model.dataType,
    color: model.style?.fill || getColorByType(raw.type),
    rawData: raw
  }
}

function selectEdge(model: any) {
  clearGraphStates()
  graph.setItemState(model.id, 'selected', true)
  const raw = model.rawData || {}
  const edgeData = raw.data || raw
  // 查找端点节点名称
  const sourceNode = nodeSet.get(String(model.source))
  const targetNode = nodeSet.get(String(model.target))
  selectedItem.value = {
    kind: 'edge',
    id: model.id,
    type: raw.label || model.label || edgeData.type,
    label: model.label,
    source: model.source,
    target: model.target,
    sourceName: sourceNode?.label || model.source,
    targetName: targetNode?.label || model.target,
    color: '#67c23a',
    rawData: edgeData
  }
}

function clearGraphStates() {
  if (!graph) return
  nodeSet.forEach((_, id) => {
    try { graph.setItemState(id, 'selected', false) } catch { /* node may not exist */ }
  })
  edgeSet.forEach((edge) => {
    try { graph.setItemState(edge.id, 'selected', false) } catch { /* edge may not exist */ }
  })
}

function clearSelection() {
  clearGraphStates()
  selectedItem.value = null
}

function refreshGraph() {
  if (!graph) return
  graph.data({
    nodes: Array.from(nodeSet.values()),
    edges: Array.from(edgeSet.values())
  })
  graph.render()
}

async function expandNeighbors(nodeId: string) {
  const res = await exploreApi.neighbors(nodeId)
  const data = res.data || {}
  const nodes = data.nodes || []
  const edges = data.edges || data.relations || []
  let added = 0
  nodes.forEach((n: any) => {
    const id = String(n.elementId ?? n.id)
    if (!nodeSet.has(id)) {
      nodeSet.set(id, transformNode(n))
      added++
    }
  })
  edges.forEach((e: any) => {
    const key = `${e.source}-${e.target}-${e.label || ''}`
    if (!edgeSet.has(key)) {
      edgeSet.set(key, transformEdge(e))
    }
  })
  if (added > 0) {
    ElMessage.success(`展开 ${added} 个邻居节点`)
    refreshGraph()
  } else {
    ElMessage.info('无新增邻居节点')
  }
}

async function handleSearch() {
  if (!modelId.value || !keyword.value.trim()) {
    ElMessage.warning('请选择模型并输入关键词')
    return
  }
  graphLoading.value = true
  try {
    const res = await exploreApi.search(modelId.value, keyword.value.trim())
    const data = res.data || {}
    const nodes = data.nodes || []
    const edges = data.edges || data.relations || []
    if (!nodes.length) {
      ElMessage.info('未找到匹配节点')
      return
    }
    nodeSet.clear()
    edgeSet.clear()
    selectedItem.value = null
    nodes.forEach((n: any) => {
      const id = String(n.elementId ?? n.id)
      nodeSet.set(id, transformNode(n))
    })
    edges.forEach((e: any) => {
      const key = `${e.source}-${e.target}-${e.label || ''}`
      edgeSet.set(key, transformEdge(e))
    })
    refreshGraph()
    ElMessage.success(`找到 ${nodes.length} 个相关节点`)
  } finally {
    graphLoading.value = false
  }
}

async function reloadGraph() {
  selectedItem.value = null
  await loadInitialNodes()
}

function fitView() {
  if (graph) graph.fitView(20)
}

function handleResize() {
  if (graph && graphRef.value) {
    graph.changeSize(graphRef.value.offsetWidth, graphRef.value.offsetHeight)
  }
  if (pieChart) pieChart.resize()
}

// 节点详情面板展开/收起时，立即调整图谱画布尺寸（无 CSS 过渡，无需延迟）
watch(selectedItem, () => {
  if (!graph || !graphRef.value) return
  nextTick(() => {
    if (graph && graphRef.value) {
      graph.changeSize(graphRef.value.offsetWidth, graphRef.value.offsetHeight)
    }
  })
})

onMounted(async () => {
  await loadProjectsAndModels()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (graph) {
    graph.destroy()
    graph = null
  }
  if (pieChart) {
    pieChart.dispose()
    pieChart = null
  }
})
</script>

<style scoped>
.explore-page {
  display: flex;
  height: 100%;
}

/* 左侧控制面板 */
.explore-left {
  width: 280px;
  background: #fff;
  border-right: 1px solid #e6e8eb;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  z-index: 2;
}

.left-header {
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.left-title {
  font-weight: 600;
  font-size: 15px;
}

.left-body {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.control-group {
  margin-bottom: 16px;
}

.control-label {
  display: block;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  margin-bottom: 6px;
  font-weight: 500;
}

.stat-list {
  margin-bottom: 12px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  font-size: 14px;
}

.stat-label {
  flex: 1;
  color: rgba(0, 0, 0, 0.65);
}

.stat-value {
  font-weight: 700;
  color: rgba(0, 0, 0, 0.88);
  font-size: 16px;
}

.pie-chart {
  width: 100%;
  height: 220px;
}

.tips {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  line-height: 1.8;
  padding-left: 16px;
}

/* 中间图谱区域 */
.explore-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  background: #fafafa;
  min-width: 0;
  overflow: hidden;
}

.graph-toolbar {
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.graph-title {
  font-weight: 600;
  color: rgba(0, 0, 0, 0.88);
}

.graph-canvas {
  flex: 1;
  width: 100%;
  height: 100%;
}

.graph-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

/* 右侧详情面板 —— flex 挤压布局，展开时压缩中间画布 */
.explore-detail {
  width: 320px;
  flex-shrink: 0;
  background: #fff;
  border-left: 1px solid #e6e8eb;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-collapsed {
  width: 0;
  border-left: none;
  display: none;
}

.detail-header {
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.detail-title {
  font-weight: 600;
  font-size: 15px;
  color: rgba(0, 0, 0, 0.88);
}

.detail-body {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.detail-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section-title {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
  font-weight: 600;
}

.detail-type-tag {
  border: none;
  font-size: 14px;
  padding: 6px 16px;
  height: auto;
}

.detail-name {
  font-size: 18px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.88);
  word-break: break-all;
}

.detail-props {
  background: #fafafa;
  border-radius: 6px;
  overflow: hidden;
}

.detail-prop-row {
  display: flex;
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
  align-items: flex-start;
  gap: 12px;
}

.detail-prop-row:last-child {
  border-bottom: none;
}

.detail-prop-key {
  color: rgba(0, 0, 0, 0.45);
  min-width: 80px;
  flex-shrink: 0;
  font-weight: 500;
}

.detail-prop-value {
  color: rgba(0, 0, 0, 0.88);
  word-break: break-all;
  flex: 1;
}

.detail-endpoint {
  font-size: 14px;
  color: rgba(0, 0, 0, 0.88);
  font-weight: 500;
  background: #fafafa;
  padding: 8px 12px;
  border-radius: 6px;
  word-break: break-all;
}
</style>

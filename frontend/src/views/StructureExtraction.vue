<template>
  <div class="structure-page">
  <ExtractionLayout
    theme-color="#e6a23c"
    config-title="抽取配置"
    result-title="数据预览与结果"
    history-title="抽取历史记录"
  >
    <!-- 抽取配置面板头部右侧：上传文件按钮 -->
    <template #config-extra>
      <el-upload
        ref="uploadRef"
        :auto-upload="true"
        :show-file-list="false"
        :http-request="handleUpload"
        accept=".csv,.xlsx,.xls"
        :disabled="!modelId"
      >
        <el-button :icon="Upload" :disabled="!modelId" :loading="uploading">
          上传文件
        </el-button>
      </el-upload>
    </template>

    <template #config>
      <el-form label-width="100px" class="ext-form">
        <el-form-item label="所属项目">
          <el-select
            v-model="projectId"
            placeholder="选择项目"
            filterable
            style="width: 100%"
            @change="onProjectChange"
          >
            <el-option v-for="p in projects" :key="p.id" :label="p.projectName" :value="p.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="图谱模型">
          <el-select
            v-model="modelId"
            placeholder="请先选择项目"
            filterable
            style="width: 100%"
            @change="onModelChange"
          >
            <el-option v-for="m in models" :key="m.id" :label="m.modelName" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>

      <template v-if="fileInfo && modelSchema">
        <el-divider content-position="left">字段映射配置</el-divider>

        <!-- 实体映射 -->
        <div class="mapping-section">
          <div class="section-header">
            <h4 class="ext-section-title">实体映射</h4>
            <el-button :icon="Plus" @click="addEntityMapping">
              添加实体映射
            </el-button>
          </div>

          <div v-for="(em, idx) in entityMappings" :key="'e' + idx" class="mapping-block">
            <div class="mapping-block-header">
              <span class="mapping-index">实体映射 {{ idx + 1 }}</span>
              <el-button text type="danger" :icon="Delete" @click="entityMappings.splice(idx, 1)" />
            </div>
            <el-row :gutter="8">
              <el-col :span="12">
                <el-form-item label="实体类型" label-width="80px">
                  <el-select
                    v-model="em.entityTypeName"
                    placeholder="选择或输入实体类型"
                    filterable
                    allow-create
                    default-first-option
                    style="width: 100%"
                    @change="onEntityTypeChange(idx)"
                  >
                    <el-option
                      v-for="et in modelSchema.entityTypes"
                      :key="et.id"
                      :label="et.entityName"
                      :value="et.entityName"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="名称列" label-width="80px">
                  <el-select v-model="em.nameColumn" placeholder="选择名称列" filterable style="width: 100%">
                    <el-option v-for="col in fileInfo.columns" :key="col" :label="col" :value="col" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <div v-if="em.propertyMappings && em.propertyMappings.length" class="prop-mappings">
              <div v-for="(pm, pidx) in em.propertyMappings" :key="'ep' + pidx" class="prop-row">
                <el-select v-model="pm.sourceColumn" placeholder="源列" filterable style="width: 42%">
                  <el-option v-for="col in fileInfo.columns" :key="col" :label="col" :value="col" />
                </el-select>
                <el-icon class="arrow-icon"><Right /></el-icon>
                <el-select
                  v-model="pm.targetProperty"
                  placeholder="选择或输入目标属性"
                  filterable
                  allow-create
                  default-first-option
                  style="width: 42%"
                >
                  <el-option
                    v-for="prop in getEntityProperties(em.entityTypeName)"
                    :key="prop.propertyName"
                    :label="prop.propertyName"
                    :value="prop.propertyName"
                  />
                </el-select>
                <el-button text type="danger" :icon="Delete" @click="em.propertyMappings.splice(pidx, 1)" />
              </div>
            </div>
            <el-button :icon="Plus" @click="addPropertyMapping(em)">
              添加属性映射
            </el-button>
          </div>
        </div>

        <el-divider />

        <!-- 关系映射 -->
        <div class="mapping-section">
          <div class="section-header">
            <h4 class="ext-section-title">关系映射</h4>
            <el-button :icon="Plus" @click="addRelationMapping">
              添加关系映射
            </el-button>
          </div>

          <div v-for="(rm, idx) in relationMappings" :key="'r' + idx" class="mapping-block">
            <div class="mapping-block-header">
              <span class="mapping-index">关系映射 {{ idx + 1 }}</span>
              <el-button text type="danger" :icon="Delete" @click="relationMappings.splice(idx, 1)" />
            </div>
            <el-form-item label="关系类型" label-width="80px">
              <el-select
                v-model="rm.relationTypeName"
                placeholder="选择或输入关系类型"
                filterable
                allow-create
                default-first-option
                style="width: 100%"
                @change="onRelationTypeSelect(idx, $event)"
              >
                <el-option
                  v-for="rt in modelSchema.relationTypes"
                  :key="rt.id"
                  :label="`${rt.relationName} (${rt.sourceEntityName} → ${rt.targetEntityName})`"
                  :value="rt.relationName"
                />
              </el-select>
            </el-form-item>
            <el-row :gutter="8">
              <el-col :span="12">
                <el-form-item label="头实体列" label-width="80px">
                  <el-select v-model="rm.headNameColumn" placeholder="头实体名称列" filterable style="width: 100%">
                    <el-option v-for="col in fileInfo.columns" :key="col" :label="col" :value="col" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="尾实体列" label-width="80px">
                  <el-select v-model="rm.tailNameColumn" placeholder="尾实体名称列" filterable style="width: 100%">
                    <el-option v-for="col in fileInfo.columns" :key="col" :label="col" :value="col" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <div v-if="rm.propertyMappings && rm.propertyMappings.length" class="prop-mappings">
              <div v-for="(pm, pidx) in rm.propertyMappings" :key="'rp' + pidx" class="prop-row">
                <el-select v-model="pm.sourceColumn" placeholder="源列" filterable style="width: 42%">
                  <el-option v-for="col in fileInfo.columns" :key="col" :label="col" :value="col" />
                </el-select>
                <el-icon class="arrow-icon"><Right /></el-icon>
                <el-select
                  v-model="pm.targetProperty"
                  placeholder="选择或输入目标属性"
                  filterable
                  allow-create
                  default-first-option
                  style="width: 42%"
                >
                  <el-option
                    v-for="prop in getRelationProperties(rm.relationTypeName)"
                    :key="prop.propertyName"
                    :label="prop.propertyName"
                    :value="prop.propertyName"
                  />
                </el-select>
                <el-button text type="danger" :icon="Delete" @click="rm.propertyMappings.splice(pidx, 1)" />
              </div>
            </div>
            <el-button :icon="Plus" @click="addPropertyMapping(rm)">
              添加属性映射
            </el-button>
          </div>
        </div>

        <el-divider />

        <el-button
          type="primary"
          :loading="extracting"
          :disabled="!canExtract"
          @click="handleExtract"
          class="ext-btn-action"
        >
          开始抽取
        </el-button>
      </template>
    </template>

    <!-- 数据预览与结果头部右侧：抽取结束后显示统计标签 -->
    <template #result-extra>
      <div v-if="result" class="ext-stat-tags">
        <el-tag type="primary" effect="plain">实体 {{ result.entities }}</el-tag>
        <el-tag type="success" effect="plain">关系 {{ result.relations }}</el-tag>
        <el-tag type="danger" effect="plain" v-if="result.failed">失败 {{ result.failed }}</el-tag>
        <el-tag type="warning" effect="plain" v-if="result.costTime">耗时 {{ result.costTime }}ms</el-tag>
      </div>
    </template>

    <template #result>
      <el-empty v-if="!fileInfo && !result" description="请上传文件开始抽取" />

      <div v-else class="ext-result">
        <div v-if="fileInfo" class="ext-preview-box">
          <h4 class="ext-section-title">数据预览（前 {{ fileInfo.previewRows.length }} 行 / 共 {{ fileInfo.totalRows }} 行）</h4>
          <el-table :data="fileInfo.previewRows" border size="small" max-height="260" style="width: 100%">
            <el-table-column
              v-for="col in fileInfo.columns"
              :key="col"
              :prop="col"
              :label="col"
              min-width="100"
              show-overflow-tooltip
            />
          </el-table>
        </div>

        <div v-if="result" class="ext-result-box">
          <el-tabs>
            <el-tab-pane :label="`实体列表 (${extractResultEntities.length})`">
              <el-table :data="extractResultEntities" border size="small" max-height="360">
                <el-table-column type="index" width="50" align="center" />
                <el-table-column prop="name" label="实体名称" min-width="130" />
                <el-table-column prop="type" label="类型" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag type="warning" size="small">{{ row.type }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="属性" min-width="220">
                  <template #default="{ row }">
                    <span v-if="!row.properties || !Object.keys(row.properties).length">-</span>
                    <el-tag v-for="(v, k) in row.properties" :key="k" size="small" class="ext-entity-tag">{{ k }}: {{ v }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <el-tab-pane :label="`关系列表 (${extractResultRelations.length})`">
              <el-table :data="extractResultRelations" border size="small" max-height="360">
                <el-table-column type="index" width="50" align="center" />
                <el-table-column prop="head" label="头实体" min-width="120">
                  <template #default="{ row }">
                    <span>{{ row.head }}</span>
                    <span v-if="row.headType" class="ext-node-type">（{{ row.headType }}）</span>
                  </template>
                </el-table-column>
                <el-table-column prop="relationType" label="关系" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag type="success" size="small">{{ row.relationType }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="tail" label="尾实体" min-width="120">
                  <template #default="{ row }">
                    <span>{{ row.tail }}</span>
                    <span v-if="row.tailType" class="ext-node-type">（{{ row.tailType }}）</span>
                  </template>
                </el-table-column>
                <el-table-column label="属性" min-width="180">
                  <template #default="{ row }">
                    <span v-if="!row.properties || !Object.keys(row.properties).length">-</span>
                    <el-tag v-for="(v, k) in row.properties" :key="k" size="small" class="ext-entity-tag">{{ k }}: {{ v }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>
    </template>

    <template #history-extra>
      <el-button :icon="Refresh" @click="loadHistory">刷新</el-button>
    </template>

    <template #history>
      <el-table :data="history" border v-loading="historyLoading" size="small">
        <el-table-column type="index" min-width="50" align="center" />
        <el-table-column prop="extractionType" label="类型" min-width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="extractionTypeColor(row.extractionType)" size="small">{{ row.extractionType || 'STRUCTURE' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="modelId" label="模型ID" min-width="110" align="center" />
        <el-table-column prop="duration" label="耗时(ms)" min-width="90" align="center" />
        <el-table-column prop="status" label="状态" min-width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="抽取时间" min-width="150">
          <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="180" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="viewHistory(row)">查看</el-button>
            <el-button size="small" @click="exportExtractionTask(row)">导出</el-button>
            <el-button size="small" type="danger" @click="deleteHistory(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="ext-pagination">
        <el-pagination v-model:current-page="histPage" v-model:page-size="histSize" :total="histTotal" layout="total, prev, pager, next" @current-change="loadHistory" />
      </div>
    </template>
  </ExtractionLayout>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'
import { Upload, Plus, Delete, Right, Refresh } from '@element-plus/icons-vue'
import { projectApi, modelApi, extractionApi } from '@/api'
import { exportExtractionTask } from '@/utils/export'
import ExtractionLayout from '@/components/ExtractionLayout.vue'

interface Project { id: number | string; projectName: string }
interface ModelInfo { id: number | string; modelName: string }
interface EntityProperty { propertyName: string; propertyType: string }
interface EntityType { id: number | string; entityName: string; properties?: EntityProperty[] }
interface RelationType {
  id: number | string
  relationName: string
  sourceEntityName?: string
  targetEntityName?: string
  properties?: EntityProperty[]
}
interface ModelSchema {
  entityTypes: EntityType[]
  relationTypes: RelationType[]
}
interface FileInfo {
  fileKey: string
  fileName: string
  columns: string[]
  previewRows: Record<string, string>[]
  totalRows: number
}
interface PropertyMapping { sourceColumn: string; targetProperty: string }
interface EntityMapping {
  entityTypeName: string
  nameColumn: string
  propertyMappings: PropertyMapping[]
}
interface RelationMapping {
  relationTypeName: string
  headNameColumn: string
  tailNameColumn: string
  headEntityTypeName?: string
  tailEntityTypeName?: string
  propertyMappings: PropertyMapping[]
}

interface ResultEntity {
  name: string
  type: string
  properties: Record<string, any>
}
interface ResultRelation {
  relationType: string
  head: string
  headType?: string
  tail: string
  tailType?: string
  properties: Record<string, any>
}
interface ExtractResultData {
  summary: { entities: number; relations: number; failed: number; costTime?: number }
  entities: ResultEntity[]
  relations: ResultRelation[]
}

const projects = ref<Project[]>([])
const models = ref<ModelInfo[]>([])
const projectId = ref<number | string | undefined>()
const modelId = ref<number | string | undefined>()
const modelSchema = ref<ModelSchema | null>(null)
const uploading = ref(false)
const fileInfo = ref<FileInfo | null>(null)
const extracting = ref(false)
const result = ref<{ entities: number; relations: number; failed: number; costTime?: number } | null>(null)

const entityMappings = ref<EntityMapping[]>([])
const relationMappings = ref<RelationMapping[]>([])

const history = ref<any[]>([])
const historyLoading = ref(false)
const histPage = ref(1)
const histSize = ref(10)
const histTotal = ref(0)

const extractResultData = ref<ExtractResultData | null>(null)

const canExtract = computed(() => {
  if (!fileInfo.value || !modelId.value) return false
  return entityMappings.value.length > 0 || relationMappings.value.length > 0
})

const extractResultEntities = computed<ResultEntity[]>(() => extractResultData.value?.entities || [])
const extractResultRelations = computed<ResultRelation[]>(() => extractResultData.value?.relations || [])

async function loadProjects() {
  const res = await projectApi.list({ pageNum: 1, pageSize: 100 })
  projects.value = res.data?.records || res.data || []
}

async function onProjectChange() {
  models.value = []
  modelId.value = undefined
  modelSchema.value = null
  if (!projectId.value) return
  const res = await modelApi.list(projectId.value)
  models.value = res.data?.records || res.data || []
}

async function onModelChange() {
  modelSchema.value = null
  clearFile()
  if (!modelId.value) return
  try {
    const res = await modelApi.detail(modelId.value as number)
    const data = res.data
    modelSchema.value = {
      entityTypes: data?.entityTypes || [],
      relationTypes: (data?.relationTypes || []).map((rt: any) => ({
        ...rt,
        sourceEntityName: rt.sourceEntityName || rt.sourceEntity,
        targetEntityName: rt.targetEntityName || rt.targetEntity,
      })),
    }
  } catch {
    ElMessage.warning('获取模型详情失败')
  }
}

async function handleUpload(options: UploadRequestOptions) {
  const file = options.file as File
  if (!file) return
  uploading.value = true
  result.value = null
  extractResultData.value = null
  try {
    const res = await extractionApi.structureParse(file)
    fileInfo.value = res.data
    ElMessage.success(`文件解析成功，共 ${res.data.totalRows} 行`)
  } catch {
    ElMessage.error('文件上传解析失败')
  } finally {
    uploading.value = false
  }
}

function clearFile() {
  fileInfo.value = null
  result.value = null
  extractResultData.value = null
  entityMappings.value = []
  relationMappings.value = []
}

function getEntityProperties(entityTypeName: string): EntityProperty[] {
  const et = modelSchema.value?.entityTypes.find(e => e.entityName === entityTypeName)
  return et?.properties || []
}

function getRelationProperties(relationTypeName: string): EntityProperty[] {
  const rt = modelSchema.value?.relationTypes.find(r => r.relationName === relationTypeName)
  return rt?.properties || []
}

function addEntityMapping() {
  entityMappings.value.push({
    entityTypeName: '',
    nameColumn: '',
    propertyMappings: [],
  })
}

function addRelationMapping() {
  relationMappings.value.push({
    relationTypeName: '',
    headNameColumn: '',
    tailNameColumn: '',
    propertyMappings: [],
  })
}

function addPropertyMapping(target: EntityMapping | RelationMapping) {
  target.propertyMappings.push({ sourceColumn: '', targetProperty: '' })
}

function onEntityTypeChange(idx: number) {
  entityMappings.value[idx].propertyMappings = []
}

function onRelationTypeSelect(idx: number, value: string) {
  const rt = modelSchema.value?.relationTypes.find(r => r.relationName === value)
  if (rt) {
    relationMappings.value[idx].headEntityTypeName = rt.sourceEntityName
    relationMappings.value[idx].tailEntityTypeName = rt.targetEntityName
  }
  relationMappings.value[idx].propertyMappings = []
}

/** 解析后端任务 result，提取统计与实体/关系明细（后端已收集去重明细） */
function parseTaskResult(task: any): ExtractResultData {
  const resultData = task.result
    ? (typeof task.result === 'string' ? JSON.parse(task.result) : task.result)
    : {}
  return {
    summary: {
      entities: resultData.entities || 0,
      relations: resultData.relations || 0,
      failed: resultData.writeCount?.failed || 0,
      costTime: task.duration,
    },
    entities: resultData.extractedEntities || [],
    relations: resultData.extractedRelations || [],
  }
}

async function handleExtract() {
  if (!fileInfo.value || !modelId.value) return
  extracting.value = true
  try {
    const res = await extractionApi.structure({
      projectId: projectId.value,
      modelId: modelId.value,
      fileKey: fileInfo.value.fileKey,
      entityMappings: entityMappings.value.filter(em => em.entityTypeName && em.nameColumn),
      relationMappings: relationMappings.value.filter(rm => rm.relationTypeName && rm.headNameColumn && rm.tailNameColumn),
    })
    const task = res.data
    extractResultData.value = parseTaskResult(task)
    result.value = extractResultData.value.summary
    ElMessage.success('抽取完成')
    fileInfo.value = null
    await loadHistory()
  } catch {
    ElMessage.error('抽取失败')
  } finally {
    extracting.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await extractionApi.list({
      extractionType: 'STRUCTURE',
      pageNum: histPage.value,
      pageSize: histSize.value,
      sortField: 'createTime',
      sortOrder: 'descend',
    })
    history.value = res.data?.records || res.data || []
    histTotal.value = Number(res.data?.total) || history.value.length
  } finally {
    historyLoading.value = false
  }
}

async function viewHistory(row: any) {
  const res = await extractionApi.get(row.id)
  const task = res.data
  extractResultData.value = parseTaskResult(task)
  result.value = extractResultData.value.summary
  currentHistoryId.value = row.id
}

const currentHistoryId = ref<number | null>(null)

async function deleteHistory(row: any) {
  try {
    await ElMessageBox.confirm('确定删除该条抽取记录吗？删除后不可恢复。', '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await extractionApi.delete(row.id)
    ElMessage.success('删除成功')
    // 若删除的正是当前展示的结果，清空结果
    if (currentHistoryId.value === row.id) {
      extractResultData.value = null
      result.value = null
      currentHistoryId.value = null
    }
    loadHistory()
  } catch {
    // request 层已提示
  }
}

function statusType(status: number): string {
  return { 1: 'warning', 2: 'success', 3: 'danger' }[status] || 'info'
}
function statusText(status: number): string {
  return { 1: '进行中', 2: '成功', 3: '失败' }[status] || '未知'
}
function extractionTypeColor(type: string): string {
  if (type === 'DL') return 'danger'
  if (type === 'KOS') return 'success'
  if (type === 'STRUCTURE') return 'warning'
  return 'primary'
}
function formatTime(t?: string): string {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

onMounted(() => {
  loadProjects()
  loadHistory()
})
</script>

<style scoped>
/* ============ Ant Design 风格统一 ============ */
.structure-page :deep(.el-button) {
  height: 32px;
  padding: 4px 15px;
  font-size: 14px;
  line-height: 22px;
  font-weight: 400;
  border-radius: 6px;
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
  box-shadow: none;
}
.structure-page :deep(.el-button--default) {
  color: rgba(0, 0, 0, 0.88);
  background: #ffffff;
  border-color: #d9d9d9;
}
.structure-page :deep(.el-button--default:hover) {
  color: #4096ff;
  border-color: #4096ff;
  background: #ffffff;
}
.structure-page :deep(.el-button--default:active) {
  color: #0958d9;
  border-color: #0958d9;
}
.structure-page :deep(.el-button--primary) {
  color: #fff;
  background: #1677ff;
  border-color: #1677ff;
}
.structure-page :deep(.el-button--primary:hover) {
  background: #4096ff;
  border-color: #4096ff;
}
.structure-page :deep(.el-button--primary:active) {
  background: #0958d9;
  border-color: #0958d9;
}
.structure-page :deep(.el-button--primary.is-disabled),
.structure-page :deep(.el-button--default.is-disabled) {
  color: rgba(0, 0, 0, 0.25);
  background: rgba(0, 0, 0, 0.04);
  border-color: #d9d9d9;
}
.structure-page :deep(.el-button.is-text.el-button--danger) {
  padding: 4px 8px;
  height: 28px;
  color: #ff4d4f;
}
.structure-page :deep(.el-button.is-text.el-button--danger:hover) {
  color: #ff7875;
  background: rgba(255, 77, 79, 0.06);
}
.structure-page .ext-btn-action {
  width: 100%;
  height: 40px !important;
  font-size: 15px !important;
  font-weight: 500;
}

/* ============ 结果区与配置区精修 ============ */
.ext-form :deep(.el-divider--horizontal) {
  margin: 18px 0;
}

.ext-form :deep(.el-divider__text) {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
  background: var(--bg-card);
}

.ext-stat-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ext-result {
  max-height: 560px;
  overflow: auto;
}

.ext-section-title {
  font-size: 14px;
  color: var(--text-1);
  margin-bottom: 10px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ext-section-title::before {
  content: '';
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--brand-primary), var(--brand-accent));
}

.ext-preview-box {
  margin-bottom: 18px;
}

.ext-result-box {
  margin-top: 8px;
}

.ext-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.mapping-section {
  margin-bottom: 8px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.mapping-block {
  padding: 16px;
  background: var(--bg-soft);
  border: 1px solid var(--border-2);
  border-radius: var(--r-md);
  margin-bottom: 12px;
  transition: border-color var(--t-fast), box-shadow var(--t-fast);
}

.mapping-block:hover {
  border-color: var(--border-1);
  box-shadow: var(--shadow-1);
}

.mapping-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.mapping-index {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
}

.prop-mappings {
  margin: 10px 0;
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1px dashed var(--border-1);
  border-radius: var(--r-sm);
}

.prop-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.prop-row:last-child {
  margin-bottom: 0;
}

.arrow-icon {
  color: var(--text-4);
  flex-shrink: 0;
}

.ext-entity-tag {
  margin: 2px 4px 2px 0;
}

.ext-node-type {
  font-size: 12px;
  color: var(--text-3);
}
</style>

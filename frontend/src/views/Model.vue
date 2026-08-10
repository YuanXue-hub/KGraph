<template>
  <div class="model-page">
    <!-- 顶部：项目选择 + 操作页签 -->
    <div class="model-topbar">
      <div class="topbar-left">
        <el-select
          v-model="currentProjectId"
          placeholder="选择项目"
          filterable
          style="width: 220px"
          @change="loadModels"
        >
          <el-option v-for="p in projects" :key="p.id" :label="p.projectName" :value="p.id" />
        </el-select>
      </div>
      <div class="topbar-tabs">
        <div
          v-for="tab in tabs"
          :key="tab.name"
          class="tab-btn"
          :class="{ active: !tab.action && activeView === tab.name }"
          @click="onTabClick(tab)"
        >
          <el-icon><component :is="tab.icon" /></el-icon>
          <span>{{ tab.label }}</span>
        </div>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="model-content">
      <!-- 模型列表 -->
      <div v-show="activeView === 'list'" class="view-list" v-loading="modelLoading">
        <el-table
          :data="models"
          border
          style="width: 100%"
          highlight-current-row
          @current-change="onModelRowChange"
        >
          <el-table-column prop="modelName" label="本体名称" min-width="160" />
          <el-table-column prop="modelDescription" label="模型描述" min-width="200" show-overflow-tooltip />
          <el-table-column label="版本号" width="90" align="center">
            <template #default="{ row }">v{{ row.version ?? 1 }}</template>
          </el-table-column>
          <el-table-column label="实体数量" width="90" align="center">
            <template #default="{ row }">
              <el-tag type="success" size="small">{{ row.entityCount ?? 0 }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="关系数量" width="90" align="center">
            <template #default="{ row }">
              <el-tag type="warning" size="small">{{ row.relationCount ?? 0 }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="createByName" label="创建人" width="100" align="center" />
          <el-table-column label="创建时间" width="170" align="center">
            <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="170" align="center">
            <template #default="{ row }">{{ formatTime(row.updateTime) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="220" align="center" fixed="right">
            <template #default="{ row }">
              <el-button size="small" link type="primary" @click="selectModelForManage(row)">管理</el-button>
              <el-button size="small" link type="primary" @click="openCopyDialog(row)">复制</el-button>
              <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!modelLoading && models.length === 0" description="暂无模型，请点击「新建模型」创建" />
      </div>

      <!-- 实体管理 -->
      <div v-show="activeView === 'object'" class="view-object">
        <div v-if="!selectedModel" class="empty-hint">
          <el-empty description="请先在模型列表中选择一个模型进行管理" />
        </div>
        <div v-else>
          <div class="view-back-bar">
            <el-button size="small" :icon="Back" @click="backToList">返回模型列表</el-button>
            <span class="view-back-title">实体管理 — {{ selectedModel.modelName }}</span>
          </div>
          <div class="object-layout">
            <!-- 左侧：实体列表（Neo4j） -->
            <div class="entity-panel">
              <div class="panel-header">
                <span class="panel-title">实体列表</span>
                <el-button type="primary" size="small" :icon="Plus" @click="openAddNeoEntity">新增实体</el-button>
              </div>
              <div class="panel-search">
                <el-input
                  v-model="neoSearchKeyword"
                  placeholder="搜索实体名称"
                  clearable
                  size="small"
                  @keyup.enter="loadNeoEntities(1)"
                  @clear="loadNeoEntities(1)"
                >
                  <template #append>
                    <el-button :icon="Search" @click="loadNeoEntities(1)" />
                  </template>
                </el-input>
              </div>
              <div class="entity-list" v-loading="neoEntityLoading">
                <el-table
                  :data="neoEntities"
                  row-key="elementId"
                  highlight-current-row
                  size="small"
                  :current-row-key="selectedNeoEntityId"
                  style="width: 100%"
                  @current-change="onNeoEntityRowChange"
                >
                  <el-table-column prop="name" label="名称" min-width="100" show-overflow-tooltip />
                  <el-table-column label="类型" width="90" align="center">
                    <template #default="{ row }">
                      <el-tag size="small" type="info">{{ row.type || '未分类' }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="80" align="center">
                    <template #default="{ row }">
                      <el-button size="small" link type="primary" :icon="Edit" @click.stop="openEditNeoEntity(row)" />
                      <el-button size="small" link type="danger" :icon="Delete" @click.stop="deleteNeoEntity(row)" />
                    </template>
                  </el-table-column>
                </el-table>
                <el-empty v-if="!neoEntityLoading && neoEntities.length === 0" description="暂无实体" :image-size="50" />
              </div>
              <div class="panel-pagination" v-if="neoEntityTotal > 0">
                <el-pagination
                  v-model:current-page="neoEntityPage"
                  :page-size="neoEntityPageSize"
                  :total="neoEntityTotal"
                  layout="prev, pager, next"
                  small
                  @current-change="loadNeoEntities()"
                />
              </div>
            </div>

            <!-- 右侧：属性列表（Neo4j） -->
            <div class="property-panel">
              <div class="panel-header">
                <span class="panel-title">
                  属性列表
                  <span v-if="selectedNeoEntity" class="panel-subtitle-inline">— {{ selectedNeoEntity.name }}</span>
                </span>
                <el-button
                  type="primary"
                  size="small"
                  :icon="Plus"
                  :disabled="!selectedNeoEntity"
                  @click="openAddNeoProp"
                >新增属性</el-button>
              </div>
              <div v-if="selectedNeoEntity" class="entity-info-bar">
                <el-tag size="small">名称：{{ selectedNeoEntity.name }}</el-tag>
                <el-tag size="small" type="info">类型：{{ selectedNeoEntity.type || '未分类' }}</el-tag>
                <el-button size="small" link type="primary" @click="openEditNeoEntity(selectedNeoEntity)">编辑实体</el-button>
              </div>
              <div class="property-table-wrap" v-if="selectedNeoEntity">
                <el-table
                  :data="neoEntityProps"
                  size="small"
                  v-loading="neoPropLoading"
                  style="width: 100%"
                >
                  <el-table-column prop="key" label="属性名" min-width="140" />
                  <el-table-column prop="valueDisplay" label="值" min-width="200" show-overflow-tooltip />
                  <el-table-column label="类型" width="100" align="center">
                    <template #default="{ row }">
                      <el-tag size="small" type="info">{{ row.valueType }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="130" align="center">
                    <template #default="{ row }">
                      <el-button size="small" link type="primary" @click="openEditNeoProp(row)">编辑</el-button>
                      <el-button size="small" link type="danger" @click="deleteNeoProp(row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <el-empty v-else description="请从左侧选择一个实体" />
            </div>
          </div>
        </div>
      </div>

      <!-- 关系管理 -->
      <div v-show="activeView === 'relation'" class="view-relation">
        <div v-if="!selectedModel" class="empty-hint">
          <el-empty description="请先在模型列表中选择一个模型进行管理" />
        </div>
        <div v-else>
          <div class="view-back-bar">
            <el-button size="small" :icon="Back" @click="backToList">返回模型列表</el-button>
            <span class="view-back-title">关系管理 — {{ selectedModel.modelName }}</span>
          </div>
          <div class="object-layout">
            <!-- 左侧：关系列表（Neo4j） -->
            <div class="entity-panel">
              <div class="panel-header">
                <span class="panel-title">关系列表</span>
              </div>
              <div class="panel-search">
                <el-input
                  v-model="neoRelationKeyword"
                  placeholder="搜索关系名称"
                  clearable
                  size="small"
                  @keyup.enter="loadNeoRelations(1)"
                  @clear="loadNeoRelations(1)"
                >
                  <template #append>
                    <el-button :icon="Search" @click="loadNeoRelations(1)" />
                  </template>
                </el-input>
              </div>
              <div class="entity-list" v-loading="neoRelationLoading">
                <el-table
                  :data="neoRelations"
                  row-key="elementId"
                  highlight-current-row
                  size="small"
                  :current-row-key="selectedNeoRelationId"
                  style="width: 100%"
                  @current-change="onNeoRelationRowChange"
                >
                  <el-table-column prop="type" label="关系名称" min-width="100" show-overflow-tooltip />
                  <el-table-column label="起点 → 终点" min-width="120">
                    <template #default="{ row }">
                      <span>{{ row.sourceName }}</span>
                      <el-icon style="margin: 0 2px"><Right /></el-icon>
                      <span>{{ row.targetName }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="60" align="center">
                    <template #default="{ row }">
                      <el-button size="small" link type="danger" :icon="Delete" @click.stop="deleteNeoRelation(row)" />
                    </template>
                  </el-table-column>
                </el-table>
                <el-empty v-if="!neoRelationLoading && neoRelations.length === 0" description="暂无关系" :image-size="50" />
              </div>
              <div class="panel-pagination" v-if="neoRelationTotal > 0">
                <el-pagination
                  v-model:current-page="neoRelationPage"
                  :page-size="neoRelationPageSize"
                  :total="neoRelationTotal"
                  layout="prev, pager, next"
                  small
                  @current-change="loadNeoRelations()"
                />
              </div>
            </div>

            <!-- 右侧：关系属性列表（Neo4j） -->
            <div class="property-panel">
              <div class="panel-header">
                <span class="panel-title">
                  属性列表
                  <span v-if="selectedNeoRelation" class="panel-subtitle-inline">— {{ selectedNeoRelation.type }}</span>
                </span>
                <el-button
                  type="primary"
                  size="small"
                  :icon="Plus"
                  :disabled="!selectedNeoRelation"
                  @click="openAddNeoRelationProp"
                >新增属性</el-button>
              </div>
              <div v-if="selectedNeoRelation" class="entity-info-bar">
                <el-tag size="small">关系：{{ selectedNeoRelation.type }}</el-tag>
                <el-tag size="small" type="info">{{ selectedNeoRelation.sourceName }} → {{ selectedNeoRelation.targetName }}</el-tag>
              </div>
              <div class="property-table-wrap" v-if="selectedNeoRelation">
                <el-table
                  :data="neoRelationProps"
                  size="small"
                  v-loading="neoRelationPropLoading"
                  style="width: 100%"
                >
                  <el-table-column prop="key" label="属性名" min-width="140" />
                  <el-table-column prop="valueDisplay" label="值" min-width="200" show-overflow-tooltip />
                  <el-table-column label="类型" width="100" align="center">
                    <template #default="{ row }">
                      <el-tag size="small" type="info">{{ row.valueType }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="130" align="center">
                    <template #default="{ row }">
                      <el-button size="small" link type="primary" @click="openEditNeoRelationProp(row)">编辑</el-button>
                      <el-button size="small" link type="danger" @click="deleteNeoRelationProp(row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <el-empty v-else description="请从左侧选择一个关系" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建模型对话框 -->
    <el-dialog v-model="addDialog" title="新建模型" width="480px">
      <el-form ref="addFormRef" :model="addForm" :rules="addRules" label-width="90px">
        <el-form-item label="模型名称" prop="modelName">
          <el-input v-model="addForm.modelName" placeholder="请输入模型名称" />
        </el-form-item>
        <el-form-item label="模型版本" prop="version">
          <el-input-number v-model="addForm.version" :min="1" :max="999" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="模型描述">
          <el-input v-model="addForm.modelDescription" type="textarea" :rows="3" placeholder="请输入模型描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialog = false">取消</el-button>
        <el-button type="primary" :loading="addSubmitting" @click="submitAdd">确定</el-button>
      </template>
    </el-dialog>

    <!-- 复制模型对话框 -->
    <el-dialog v-model="copyDialog" title="复制模型" width="640px">
      <div class="copy-layout">
        <!-- 左侧：原模型信息 -->
        <div class="copy-left">
          <div class="copy-section-title">原模型信息</div>
          <el-form label-width="80px" class="copy-form">
            <el-form-item label="模型名称">
              <el-input :model-value="copySource.modelName" disabled />
            </el-form-item>
            <el-form-item label="模型描述">
              <el-input :model-value="copySource.modelDescription" type="textarea" :rows="3" disabled />
            </el-form-item>
          </el-form>
        </div>
        <!-- 右侧：复制信息 -->
        <div class="copy-right">
          <div class="copy-section-title">复制信息</div>
          <el-form ref="copyFormRef" :model="copyForm" :rules="copyRules" label-width="80px">
            <el-form-item label="模型名称" prop="newModelName">
              <el-input v-model="copyForm.newModelName" placeholder="请输入复制的模型名称" />
            </el-form-item>
            <el-form-item label="模型版本" prop="newVersion">
              <el-input-number v-model="copyForm.newVersion" :min="1" :max="999" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-form>
        </div>
      </div>
      <template #footer>
        <el-button @click="copyDialog = false">取消</el-button>
        <el-button type="primary" :loading="copySubmitting" @click="submitCopy">复制</el-button>
      </template>
    </el-dialog>

    <!-- 实体新增/编辑对话框（Neo4j） -->
    <el-dialog v-model="neoEntityDialog" :title="isEditNeoEntity ? '编辑实体' : '新增实体'" width="460px">
      <el-form ref="neoEntityFormRef" :model="neoEntityForm" :rules="neoEntityRules" label-width="80px">
        <el-form-item label="实体名称" prop="name">
          <el-input v-model="neoEntityForm.name" placeholder="如：刘备、诸葛亮" />
        </el-form-item>
        <el-form-item label="实体类型" prop="type">
          <el-input v-model="neoEntityForm.type" placeholder="如：人物、地点" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="neoEntityDialog = false">取消</el-button>
        <el-button type="primary" :loading="neoEntitySubmitting" @click="submitNeoEntity">确定</el-button>
      </template>
    </el-dialog>

    <!-- 属性新增/编辑对话框（Neo4j） -->
    <el-dialog v-model="neoPropDialog" :title="isEditNeoProp ? '编辑属性' : '新增属性'" width="460px">
      <el-form ref="neoPropFormRef" :model="neoPropForm" :rules="neoPropRules" label-width="80px">
        <el-form-item label="属性名" prop="key">
          <el-input v-model="neoPropForm.key" :disabled="isEditNeoProp" placeholder="只能包含字母、数字和下划线" />
        </el-form-item>
        <el-form-item label="属性值" prop="value">
          <el-input v-model="neoPropForm.value" placeholder="请输入属性值" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="neoPropDialog = false">取消</el-button>
        <el-button type="primary" :loading="neoPropSubmitting" @click="submitNeoProp">确定</el-button>
      </template>
    </el-dialog>

    <!-- 关系类型对话框 -->
    <el-dialog v-model="relationDialog" :title="isEditRelation ? '编辑关系类型' : '新增关系类型'" width="500px">
      <el-form ref="relationFormRef" :model="relationForm" :rules="relationRules" label-width="90px">
        <el-form-item label="关系名称" prop="relationName">
          <el-input v-model="relationForm.relationName" placeholder="如：出生于、属于" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="relationForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="起点实体" prop="sourceEntityTypeId">
          <el-select v-model="relationForm.sourceEntityTypeId" placeholder="选择起点实体类型" style="width: 100%">
            <el-option v-for="e in entityTypes" :key="e.id" :label="e.entityName" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="终点实体" prop="targetEntityTypeId">
          <el-select v-model="relationForm.targetEntityTypeId" placeholder="选择终点实体类型" style="width: 100%">
            <el-option v-for="e in entityTypes" :key="e.id" :label="e.entityName" :value="e.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="relationDialog = false">取消</el-button>
        <el-button type="primary" :loading="relationSubmitting" @click="submitRelation">确定</el-button>
      </template>
    </el-dialog>

    <!-- 关系属性对话框 -->
    <el-dialog v-model="relationPropDialog" :title="isEditRelationProp ? '编辑关系属性' : '新增关系属性'" width="460px">
      <el-form ref="relationPropFormRef" :model="relationPropForm" :rules="propRules" label-width="80px">
        <el-form-item label="属性名" prop="propertyName">
          <el-input v-model="relationPropForm.propertyName" />
        </el-form-item>
        <el-form-item label="属性类型" prop="propertyType">
          <el-select v-model="relationPropForm.propertyType" placeholder="选择类型" style="width: 100%">
            <el-option label="String" value="String" />
            <el-option label="Integer" value="Integer" />
            <el-option label="Long" value="Long" />
            <el-option label="Double" value="Double" />
            <el-option label="Boolean" value="Boolean" />
            <el-option label="Date" value="Date" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="relationPropForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="是否必填">
          <el-switch v-model="relationPropForm.isRequired" />
        </el-form-item>
        <el-form-item label="默认值">
          <el-input v-model="relationPropForm.defaultValue" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="relationPropDialog = false">取消</el-button>
        <el-button type="primary" :loading="propSubmitting" @click="submitRelationProp">确定</el-button>
      </template>
    </el-dialog>

    <!-- Neo4j 关系属性对话框 -->
    <el-dialog v-model="neoRelationPropDialog" :title="isEditNeoRelationProp ? '编辑关系属性' : '新增关系属性'" width="460px">
      <el-form ref="neoRelationPropFormRef" :model="neoRelationPropForm" :rules="neoPropRules" label-width="80px">
        <el-form-item label="属性名" prop="key">
          <el-input v-model="neoRelationPropForm.key" :disabled="isEditNeoRelationProp" placeholder="字母、数字、下划线" />
        </el-form-item>
        <el-form-item label="属性值" prop="value">
          <el-input v-model="neoRelationPropForm.value" placeholder="请输入属性值" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="neoRelationPropDialog = false">取消</el-button>
        <el-button type="primary" :loading="neoRelationPropSubmitting" @click="submitNeoRelationProp">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Edit, Delete, DocumentCopy, Right, Back, Setting, Connection, Search } from '@element-plus/icons-vue'
import { projectApi, modelApi, relationTypeApi, relationPropertyApi, entityNeo4jApi, relationNeo4jApi } from '@/api'

interface Project { id: number | string; projectName: string }
interface ModelInfo {
  id: number | string
  modelName: string
  modelDescription: string
  version?: number
  entityCount?: number
  relationCount?: number
  createBy?: number
  createByName?: string
  createTime?: string
  updateTime?: string
}
interface EntityType { id: number | string; entityName: string; description?: string; color?: string; icon?: string }
interface RelationType { id: number | string; relationName: string; description?: string; sourceEntityTypeId: number | string; targetEntityTypeId: number | string }
interface Property { id: number | string; propertyName: string; propertyType: string; isRequired: number | boolean; defaultValue?: string; description?: string }

const route = useRoute()
const projects = ref<Project[]>([])
const currentProjectId = ref<number | string | undefined>(undefined)
const models = ref<ModelInfo[]>([])
const modelLoading = ref(false)
const selectedModel = ref<ModelInfo | null>(null)
const activeView = ref<'list' | 'object' | 'relation'>('list')

const tabs = [
  { name: 'add' as const, label: '新建模型', icon: Plus, action: true },
  { name: 'copy' as const, label: '复制模型', icon: DocumentCopy, action: true },
  { name: 'object' as const, label: '实体管理', icon: Setting, action: false },
  { name: 'relation' as const, label: '关系管理', icon: Connection, action: false },
]

// ===== 实体类型（schema，供关系管理使用） =====
const entityTypes = ref<EntityType[]>([])
const entityLoading = ref(false)

// ===== Neo4j 实体管理（对象及属性管理视图） =====
const NEO_SYSTEM_FIELDS = new Set(['name', 'type', 'modelId', 'createTime', 'elementId', 'labels'])
interface NeoEntity { elementId: string; name: string; type?: string; [key: string]: any }
interface NeoProp { key: string; value: any; valueDisplay: string; valueType: string }
const neoEntities = ref<NeoEntity[]>([])
const neoEntityLoading = ref(false)
const neoEntityTotal = ref(0)
const neoEntityPage = ref(1)
const neoEntityPageSize = 10
const neoSearchKeyword = ref('')
const selectedNeoEntityId = ref<string | undefined>(undefined)
const selectedNeoEntity = computed(() => neoEntities.value.find((e) => e.elementId === selectedNeoEntityId.value))
const neoEntityProps = ref<NeoProp[]>([])
const neoPropLoading = ref(false)

// ===== 关系类型 =====
const relationTypes = ref<RelationType[]>([])
const relationLoading = ref(false)
const relationPropMap = ref<Record<string, Property[]>>({})
const expandedRelationRows = ref<string[]>([])

const entityNameMap = computed(() => {
  const map: Record<string, string> = {}
  entityTypes.value.forEach((e) => (map[e.id] = e.entityName))
  return map
})

// ===== Neo4j 关系管理 =====
const NEO_RELATION_SYSTEM_FIELDS = new Set([
  'type', 'modelId', 'createTime', 'elementId', 'relationType',
  'startNodeElementId', 'endNodeElementId', 'sourceName', 'targetName'
])
interface NeoRelation { elementId: string; type: string; sourceName?: string; targetName?: string; [key: string]: any }
const neoRelations = ref<NeoRelation[]>([])
const neoRelationLoading = ref(false)
const neoRelationTotal = ref(0)
const neoRelationPage = ref(1)
const neoRelationPageSize = 10
const neoRelationKeyword = ref('')
const selectedNeoRelationId = ref<string | undefined>(undefined)
const selectedNeoRelation = computed(() => neoRelations.value.find((r) => r.elementId === selectedNeoRelationId.value))
const neoRelationProps = ref<NeoProp[]>([])
const neoRelationPropLoading = ref(false)
// 关系属性对话框
const neoRelationPropDialog = ref(false)
const isEditNeoRelationProp = ref(false)
const neoRelationPropSubmitting = ref(false)
const neoRelationPropFormRef = ref<FormInstance>()
const neoRelationPropForm = ref({ key: '', value: '' })

// ===== 新建模型对话框 =====
const addDialog = ref(false)
const addSubmitting = ref(false)
const addFormRef = ref<FormInstance>()
const addForm = ref({ modelName: '', version: 1, modelDescription: '' })
const addRules: FormRules = {
  modelName: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  version: [{ required: true, message: '请输入模型版本', trigger: 'blur' }]
}

// ===== 复制模型对话框 =====
const copyDialog = ref(false)
const copySubmitting = ref(false)
const copyFormRef = ref<FormInstance>()
const copySource = ref<ModelInfo>({ id: 0, modelName: '', modelDescription: '' })
const copyForm = ref({ newModelName: '', newVersion: 1 })
const copyRules: FormRules = {
  newModelName: [{ required: true, message: '请输入复制的模型名称', trigger: 'blur' }],
  newVersion: [{ required: true, message: '请输入模型版本', trigger: 'blur' }]
}

// ===== Neo4j 实体对话框 =====
const neoEntityDialog = ref(false)
const isEditNeoEntity = ref(false)
const neoEntitySubmitting = ref(false)
const neoEntityFormRef = ref<FormInstance>()
const neoEntityForm = ref({ elementId: '', name: '', type: '' })
const neoEntityRules: FormRules = {
  name: [{ required: true, message: '请输入实体名称', trigger: 'blur' }],
  type: [{ required: true, message: '请输入实体类型', trigger: 'blur' }]
}

// ===== Neo4j 属性对话框 =====
const neoPropDialog = ref(false)
const isEditNeoProp = ref(false)
const neoPropSubmitting = ref(false)
const neoPropFormRef = ref<FormInstance>()
const neoPropForm = ref({ key: '', value: '' })
const neoPropRules: FormRules = {
  key: [
    { required: true, message: '请输入属性名', trigger: 'blur' },
    { pattern: /^[a-zA-Z_][a-zA-Z0-9_]*$/, message: '只能包含字母、数字和下划线', trigger: 'blur' }
  ],
  value: [{ required: true, message: '请输入属性值', trigger: 'blur' }]
}

// ===== 关系属性对话框复用的校验规则和加载状态 =====
const propRules: FormRules = {
  propertyName: [{ required: true, message: '请输入属性名', trigger: 'blur' }],
  propertyType: [{ required: true, message: '请选择属性类型', trigger: 'change' }]
}
const propSubmitting = ref(false)

// ===== 关系类型对话框 =====
const relationDialog = ref(false)
const isEditRelation = ref(false)
const relationSubmitting = ref(false)
const relationFormRef = ref<FormInstance>()
const relationForm = ref({
  id: '' as string | number,
  relationName: '',
  description: '',
  sourceEntityTypeId: undefined as string | number | undefined,
  targetEntityTypeId: undefined as string | number | undefined
})
const relationRules: FormRules = {
  relationName: [{ required: true, message: '请输入关系名称', trigger: 'blur' }],
  sourceEntityTypeId: [{ required: true, message: '请选择起点实体', trigger: 'change' }],
  targetEntityTypeId: [{ required: true, message: '请选择终点实体', trigger: 'change' }]
}

// ===== 关系属性对话框 =====
const relationPropDialog = ref(false)
const isEditRelationProp = ref(false)
const currentRelationTypeId = ref<string | number>('')
const relationPropFormRef = ref<FormInstance>()
const relationPropForm = ref({
  id: '' as string | number,
  propertyName: '',
  propertyType: 'String',
  description: '',
  isRequired: false,
  defaultValue: ''
})

// ===== 数据加载 =====
async function loadProjects() {
  const res = await projectApi.list({ pageNum: 1, pageSize: 100 })
  projects.value = (res.data?.records || res.data || []).slice().reverse()
  const q = route.query.projectId
  if (q) {
    currentProjectId.value = q as string
  } else if (projects.value.length > 0) {
    currentProjectId.value = projects.value[0].id
  }
  if (currentProjectId.value) {
    loadModels()
  }
}

async function loadModels() {
  if (!currentProjectId.value) return
  modelLoading.value = true
  try {
    const res = await modelApi.list(currentProjectId.value)
    models.value = res.data?.records || res.data || []
  } finally {
    modelLoading.value = false
  }
}

async function loadModelDetail() {
  if (!selectedModel.value) return
  entityLoading.value = true
  relationLoading.value = true
  try {
    const res = await modelApi.detail(selectedModel.value.id)
    const data = res.data || {}
    entityTypes.value = data.entityTypes || []
    relationTypes.value = data.relationTypes || []
    relationPropMap.value = {}
  } finally {
    entityLoading.value = false
    relationLoading.value = false
  }
}

// ===== Neo4j 实体加载 =====
async function loadNeoEntities(page?: number) {
  if (!selectedModel.value) return
  if (page) neoEntityPage.value = page
  neoEntityLoading.value = true
  try {
    const res = await entityNeo4jApi.list({
      modelId: selectedModel.value.id,
      keyword: neoSearchKeyword.value.trim() || undefined,
      pageNum: neoEntityPage.value,
      pageSize: neoEntityPageSize
    })
    const data = res.data || {}
    neoEntities.value = data.records || []
    neoEntityTotal.value = Number(data.total) || 0
  } finally {
    neoEntityLoading.value = false
  }
}

async function loadNeoEntityDetail(elementId: string) {
  neoPropLoading.value = true
  try {
    const res = await entityNeo4jApi.detail(elementId)
    const node = res.data || {}
    // 将节点属性转为属性列表（排除系统字段）
    const props: NeoProp[] = []
    for (const [key, value] of Object.entries(node)) {
      if (NEO_SYSTEM_FIELDS.has(key)) continue
      props.push({
        key,
        value,
        valueDisplay: formatNeoValue(value),
        valueType: getNeoValueType(value)
      })
    }
    neoEntityProps.value = props
  } finally {
    neoPropLoading.value = false
  }
}

function formatNeoValue(val: any): string {
  if (val === null || val === undefined) return ''
  if (Array.isArray(val)) return JSON.stringify(val)
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}

function getNeoValueType(val: any): string {
  if (val === null || val === undefined) return 'null'
  if (Array.isArray(val)) return 'list'
  return typeof val
}

// ===== Tab 切换 =====
function onTabClick(tab: { name: string; action: boolean }) {
  // 新建模型、复制模型 为动作型页签，点击打开弹窗
  if (tab.name === 'add') {
    openAddModel()
    return
  }
  if (tab.name === 'copy') {
    if (!selectedModel.value) {
      // 未选中模型时尝试用列表第一行
      if (models.value.length === 0) {
        ElMessage.warning('暂无模型可复制，请先新建模型')
        return
      }
      openCopyDialog(models.value[0])
    } else {
      openCopyDialog(selectedModel.value)
    }
    return
  }
  // 视图型页签
  if (tab.name === 'object') {
    if (!selectedModel.value) {
      ElMessage.warning('请先在模型列表中选择一个模型')
      return
    }
    activeView.value = 'object'
    loadNeoEntities(1)
  } else if (tab.name === 'relation') {
    if (!selectedModel.value) {
      ElMessage.warning('请先在模型列表中选择一个模型')
      return
    }
    activeView.value = 'relation'
    loadNeoRelations(1)
  }
}

function selectModelForManage(row: ModelInfo) {
  selectedModel.value = row
  activeView.value = 'object'
  // 加载关系管理所需的 schema + Neo4j 实体列表
  loadModelDetail()
  loadNeoEntities(1)
}

function backToList() {
  activeView.value = 'list'
  loadModels()
}

function onModelRowChange(row: ModelInfo | null) {
  if (row) {
    selectedModel.value = row
  }
}

// ===== 新建模型 =====
function openAddModel() {
  addForm.value = { modelName: '', version: 1, modelDescription: '' }
  addDialog.value = true
}

async function submitAdd() {
  if (!addFormRef.value) return
  try { await addFormRef.value.validate() } catch { return }
  addSubmitting.value = true
  try {
    await modelApi.add({
      projectId: currentProjectId.value!,
      modelName: addForm.value.modelName,
      version: addForm.value.version,
      modelDescription: addForm.value.modelDescription
    })
    ElMessage.success('创建成功')
    addDialog.value = false
    loadModels()
  } finally {
    addSubmitting.value = false
  }
}

// ===== 复制模型 =====
function openCopyDialog(row: ModelInfo) {
  copySource.value = { ...row }
  copyForm.value = { newModelName: row.modelName + '_副本', newVersion: (row.version ?? 1) + 1 }
  copyDialog.value = true
}

async function submitCopy() {
  if (!copyFormRef.value) return
  try { await copyFormRef.value.validate() } catch { return }
  copySubmitting.value = true
  try {
    await modelApi.copy({
      id: copySource.value.id,
      newModelName: copyForm.value.newModelName,
      newVersion: copyForm.value.newVersion
    })
    ElMessage.success('复制成功')
    copyDialog.value = false
    loadModels()
  } finally {
    copySubmitting.value = false
  }
}

// ===== 删除模型 =====
async function handleDelete(row: ModelInfo) {
  try {
    await ElMessageBox.confirm(`确定删除模型「${row.modelName}」？删除后不可恢复`, '提示', { type: 'warning' })
    await modelApi.delete(row.id)
    ElMessage.success('删除成功')
    if (selectedModel.value?.id === row.id) {
      selectedModel.value = null
    }
    loadModels()
  } catch {}
}

// ===== Neo4j 实体 CRUD =====
function selectNeoEntity(e: NeoEntity) {
  selectedNeoEntityId.value = e.elementId
  loadNeoEntityDetail(e.elementId)
}

// 表格行选中变化
function onNeoEntityRowChange(row: NeoEntity | null) {
  if (row) {
    selectNeoEntity(row)
  }
}

function openAddNeoEntity() {
  isEditNeoEntity.value = false
  neoEntityForm.value = { elementId: '', name: '', type: '' }
  neoEntityDialog.value = true
}

function openEditNeoEntity(row: NeoEntity) {
  isEditNeoEntity.value = true
  neoEntityForm.value = { elementId: row.elementId, name: row.name, type: row.type || '' }
  neoEntityDialog.value = true
}

async function submitNeoEntity() {
  if (!neoEntityFormRef.value) return
  try { await neoEntityFormRef.value.validate() } catch { return }
  neoEntitySubmitting.value = true
  try {
    if (isEditNeoEntity.value) {
      await entityNeo4jApi.update({
        nodeId: neoEntityForm.value.elementId,
        name: neoEntityForm.value.name,
        type: neoEntityForm.value.type
      })
      ElMessage.success('编辑成功')
    } else {
      await entityNeo4jApi.add({
        modelId: selectedModel.value!.id,
        name: neoEntityForm.value.name,
        type: neoEntityForm.value.type
      })
      ElMessage.success('新增成功')
    }
    neoEntityDialog.value = false
    loadNeoEntities()
  } finally {
    neoEntitySubmitting.value = false
  }
}

async function deleteNeoEntity(row: NeoEntity) {
  try {
    await ElMessageBox.confirm(`确定删除实体「${row.name}」？该实体的关联关系也会被删除`, '提示', { type: 'warning' })
    await entityNeo4jApi.delete(row.elementId)
    ElMessage.success('删除成功')
    if (selectedNeoEntityId.value === row.elementId) {
      selectedNeoEntityId.value = undefined
      neoEntityProps.value = []
    }
    loadNeoEntities()
  } catch {}
}

// ===== Neo4j 属性 CRUD =====
function openAddNeoProp() {
  isEditNeoProp.value = false
  neoPropForm.value = { key: '', value: '' }
  neoPropDialog.value = true
}

function openEditNeoProp(row: NeoProp) {
  isEditNeoProp.value = true
  neoPropForm.value = { key: row.key, value: row.valueDisplay }
  neoPropDialog.value = true
}

async function submitNeoProp() {
  if (!neoPropFormRef.value) return
  try { await neoPropFormRef.value.validate() } catch { return }
  neoPropSubmitting.value = true
  try {
    await entityNeo4jApi.setProperty({
      nodeId: selectedNeoEntityId.value!,
      key: neoPropForm.value.key,
      value: neoPropForm.value.value
    })
    ElMessage.success(isEditNeoProp.value ? '编辑成功' : '新增成功')
    neoPropDialog.value = false
    if (selectedNeoEntityId.value) {
      loadNeoEntityDetail(selectedNeoEntityId.value)
    }
  } finally {
    neoPropSubmitting.value = false
  }
}

async function deleteNeoProp(row: NeoProp) {
  try {
    await ElMessageBox.confirm(`确定删除属性「${row.key}」？`, '提示', { type: 'warning' })
    await entityNeo4jApi.deleteProperty({
      nodeId: selectedNeoEntityId.value!,
      key: row.key
    })
    ElMessage.success('删除成功')
    if (selectedNeoEntityId.value) {
      loadNeoEntityDetail(selectedNeoEntityId.value)
    }
  } catch {}
}

// ===== 关系类型 CRUD =====
function openAddRelation() {
  isEditRelation.value = false
  relationForm.value = { id: '', relationName: '', description: '', sourceEntityTypeId: undefined, targetEntityTypeId: undefined }
  relationDialog.value = true
}

function openEditRelation(row: RelationType) {
  isEditRelation.value = true
  relationForm.value = {
    id: row.id,
    relationName: row.relationName,
    description: row.description || '',
    sourceEntityTypeId: row.sourceEntityTypeId,
    targetEntityTypeId: row.targetEntityTypeId
  }
  relationDialog.value = true
}

async function submitRelation() {
  if (!relationFormRef.value) return
  try { await relationFormRef.value.validate() } catch { return }
  relationSubmitting.value = true
  try {
    if (isEditRelation.value) {
      await relationTypeApi.update({
        id: relationForm.value.id,
        relationName: relationForm.value.relationName,
        description: relationForm.value.description,
        sourceEntityTypeId: relationForm.value.sourceEntityTypeId!,
        targetEntityTypeId: relationForm.value.targetEntityTypeId!
      })
      ElMessage.success('编辑成功')
    } else {
      await relationTypeApi.add({
        modelId: selectedModel.value!.id,
        relationName: relationForm.value.relationName,
        description: relationForm.value.description,
        sourceEntityTypeId: relationForm.value.sourceEntityTypeId!,
        targetEntityTypeId: relationForm.value.targetEntityTypeId!
      })
      ElMessage.success('新增成功')
    }
    relationDialog.value = false
    loadModelDetail()
  } finally {
    relationSubmitting.value = false
  }
}

async function deleteRelation(row: RelationType) {
  try {
    await ElMessageBox.confirm(`确定删除关系类型「${row.relationName}」？`, '提示', { type: 'warning' })
    await relationTypeApi.delete(row.id)
    ElMessage.success('删除成功')
    loadModelDetail()
  } catch {}
}

async function onRelationExpand(row: RelationType, expanded: RelationType[]) {
  if (expanded.includes(row)) {
    const res = await relationTypeApi.properties(row.id as number)
    relationPropMap.value[row.id] = res.data || []
  }
}

// ===== 关系属性 CRUD =====
function openAddRelationProp(row: RelationType) {
  isEditRelationProp.value = false
  currentRelationTypeId.value = row.id
  relationPropForm.value = { id: '', propertyName: '', propertyType: 'String', description: '', isRequired: false, defaultValue: '' }
  relationPropDialog.value = true
}

function openEditRelationProp(p: Property, row: RelationType) {
  isEditRelationProp.value = true
  currentRelationTypeId.value = row.id
  relationPropForm.value = {
    id: p.id,
    propertyName: p.propertyName,
    propertyType: p.propertyType,
    description: p.description || '',
    isRequired: !!p.isRequired,
    defaultValue: p.defaultValue || ''
  }
  relationPropDialog.value = true
}

async function submitRelationProp() {
  if (!relationPropFormRef.value) return
  try { await relationPropFormRef.value.validate() } catch { return }
  propSubmitting.value = true
  try {
    if (isEditRelationProp.value) {
      await relationPropertyApi.update({
        id: relationPropForm.value.id,
        propertyName: relationPropForm.value.propertyName,
        propertyType: relationPropForm.value.propertyType,
        isRequired: relationPropForm.value.isRequired ? 1 : 0,
        defaultValue: relationPropForm.value.defaultValue,
        description: relationPropForm.value.description
      })
      ElMessage.success('编辑成功')
    } else {
      await relationPropertyApi.add({
        relationTypeId: currentRelationTypeId.value,
        propertyName: relationPropForm.value.propertyName,
        propertyType: relationPropForm.value.propertyType,
        isRequired: relationPropForm.value.isRequired ? 1 : 0,
        defaultValue: relationPropForm.value.defaultValue,
        description: relationPropForm.value.description
      })
      ElMessage.success('新增成功')
    }
    relationPropDialog.value = false
    const res = await relationTypeApi.properties(currentRelationTypeId.value as number)
    relationPropMap.value[currentRelationTypeId.value] = res.data || []
  } finally {
    propSubmitting.value = false
  }
}

async function deleteRelationProp(p: Property, row: RelationType) {
  try {
    await ElMessageBox.confirm(`确定删除属性「${p.propertyName}」？`, '提示', { type: 'warning' })
    await relationPropertyApi.delete(p.id)
    ElMessage.success('删除成功')
    const res = await relationTypeApi.properties(row.id as number)
    relationPropMap.value[row.id] = res.data || []
  } catch {}
}

// ===== Neo4j 关系管理 =====
async function loadNeoRelations(page?: number) {
  if (!selectedModel.value) return
  if (page) neoRelationPage.value = page
  neoRelationLoading.value = true
  try {
    const res = await relationNeo4jApi.list({
      modelId: selectedModel.value.id,
      keyword: neoRelationKeyword.value.trim() || undefined,
      pageNum: neoRelationPage.value,
      pageSize: neoRelationPageSize
    })
    const data = res.data || {}
    neoRelations.value = data.records || []
    neoRelationTotal.value = Number(data.total) || 0
  } finally {
    neoRelationLoading.value = false
  }
}

async function loadNeoRelationDetail(elementId: string) {
  neoRelationPropLoading.value = true
  try {
    const res = await relationNeo4jApi.detail(elementId)
    const rel = res.data || {}
    const props: NeoProp[] = []
    for (const [key, value] of Object.entries(rel)) {
      if (NEO_RELATION_SYSTEM_FIELDS.has(key)) continue
      props.push({
        key,
        value,
        valueDisplay: formatNeoValue(value),
        valueType: getNeoValueType(value)
      })
    }
    neoRelationProps.value = props
  } finally {
    neoRelationPropLoading.value = false
  }
}

function onNeoRelationRowChange(row: NeoRelation | null) {
  if (row) {
    selectedNeoRelationId.value = row.elementId
    loadNeoRelationDetail(row.elementId)
  }
}

async function deleteNeoRelation(row: NeoRelation) {
  try {
    await ElMessageBox.confirm(`确定删除关系「${row.type}」？`, '提示', { type: 'warning' })
    await relationNeo4jApi.delete(row.elementId)
    ElMessage.success('删除成功')
    if (selectedNeoRelationId.value === row.elementId) {
      selectedNeoRelationId.value = undefined
      neoRelationProps.value = []
    }
    loadNeoRelations()
  } catch {}
}

function openAddNeoRelationProp() {
  isEditNeoRelationProp.value = false
  neoRelationPropForm.value = { key: '', value: '' }
  neoRelationPropDialog.value = true
}

function openEditNeoRelationProp(row: NeoProp) {
  isEditNeoRelationProp.value = true
  neoRelationPropForm.value = { key: row.key, value: String(row.value) }
  neoRelationPropDialog.value = true
}

async function submitNeoRelationProp() {
  if (!neoRelationPropFormRef.value) return
  try { await neoRelationPropFormRef.value.validate() } catch { return }
  neoRelationPropSubmitting.value = true
  try {
    await relationNeo4jApi.setProperty({
      nodeId: selectedNeoRelationId.value!,
      key: neoRelationPropForm.value.key,
      value: neoRelationPropForm.value.value
    })
    ElMessage.success(isEditNeoRelationProp.value ? '编辑成功' : '新增成功')
    neoRelationPropDialog.value = false
    if (selectedNeoRelationId.value) {
      loadNeoRelationDetail(selectedNeoRelationId.value)
    }
  } finally {
    neoRelationPropSubmitting.value = false
  }
}

async function deleteNeoRelationProp(row: NeoProp) {
  try {
    await ElMessageBox.confirm(`确定删除属性「${row.key}」？`, '提示', { type: 'warning' })
    await relationNeo4jApi.deleteProperty({
      nodeId: selectedNeoRelationId.value!,
      key: row.key
    })
    ElMessage.success('删除成功')
    if (selectedNeoRelationId.value) {
      loadNeoRelationDetail(selectedNeoRelationId.value)
    }
  } catch {}
}

// ===== 工具 =====
function formatTime(t?: string): string {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.model-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
}

/* 顶部栏 */
.model-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid #e6e8eb;
  flex-shrink: 0;
}

.topbar-tabs {
  display: flex;
  gap: 4px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  color: #606266;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: #f5f7fa;
  color: #409eff;
}

.tab-btn.active {
  background: #ecf5ff;
  color: #409eff;
  font-weight: 600;
}

/* 内容区 */
.model-content {
  flex: 1;
  overflow: auto;
  padding: 16px 20px;
}

.view-list {
  width: 100%;
}

/* 返回栏 */
.view-back-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.view-back-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

/* 对象及属性管理 — Ant Design 风格 */
.object-layout {
  display: flex;
  gap: 16px;
  height: calc(100vh - 240px);
}

.entity-panel {
  flex: 1;
  min-width: 0;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.property-panel {
  flex: 1;
  min-width: 0;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
  background: #fafafa;
  border-radius: 8px 8px 0 0;
}

.panel-title {
  font-weight: 600;
  font-size: 14px;
  color: #1f1f1f;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.panel-subtitle-inline {
  font-weight: 400;
  font-size: 13px;
  color: #8c8c8c;
  margin-left: 4px;
}

.panel-search {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.panel-pagination {
  padding: 8px 16px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  flex-shrink: 0;
  background: #fafafa;
}

.entity-info-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.entity-list {
  flex: 1;
  overflow: hidden;
}

.entity-list .el-table {
  cursor: pointer;
  height: 100%;
}

.property-table-wrap {
  flex: 1;
  overflow: hidden;
}

.property-table-wrap .el-table {
  height: 100%;
}

/* Ant Design 风格表格深度覆盖 */
.object-layout :deep(.el-table) {
  --el-table-border-color: #f0f0f0;
  --el-table-header-bg-color: #fafafa;
  --el-table-header-text-color: #1f1f1f;
  --el-table-row-hover-bg-color: #f5f5f5;
  --el-table-current-row-bg-color: #e6f4ff;
  --el-table-text-color: #1f1f1f;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.object-layout :deep(.el-table th.el-table__cell) {
  font-weight: 600;
  font-size: 13px;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
}

.object-layout :deep(.el-table td.el-table__cell) {
  font-size: 13px;
  border-bottom: 1px solid #f0f0f0;
}

.object-layout :deep(.el-table .current-row td.el-table__cell) {
  background: #e6f4ff !important;
}

/* Ant Design 风格按钮 */
.object-layout :deep(.el-button--primary) {
  --el-button-bg-color: #1677ff;
  --el-button-border-color: #1677ff;
  --el-button-hover-bg-color: #4096ff;
  --el-button-hover-border-color: #4096ff;
  --el-button-active-bg-color: #0958d9;
  --el-button-active-border-color: #0958d9;
}

/* Ant Design 风格分页器 */
.object-layout :deep(.el-pagination.is-background .el-pager li.is-active) {
  background: #1677ff;
}

.object-layout :deep(.el-pagination.is-background .btn-prev),
.object-layout :deep(.el-pagination.is-background .btn-next),
.object-layout :deep(.el-pagination.is-background .el-pager li) {
  border-radius: 6px;
}

/* 复制模型弹窗 */
.copy-layout {
  display: flex;
  gap: 24px;
}

.copy-left,
.copy-right {
  flex: 1;
}

.copy-section-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f0f0;
}

/* 关系管理属性展开 */
.props-panel {
  padding: 12px 24px;
  background: #fafafa;
}

.props-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.props-title {
  font-weight: 600;
  color: #606266;
}

/* 空状态 */
.empty-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 400px;
}
</style>

import { request } from './request'
import type { ApiResponse } from './request'

/* ============ 用户 ============ */
export const userApi = {
  login(userAccount: string, userPassword: string) {
    return request({
      url: '/user/login',
      method: 'post',
      data: { userAccount, userPassword }
    })
  },
  register(data: {
    userAccount: string
    userPassword: string
    checkPassword: string
    userName: string
    userAvatar?: string
    userProfile?: string
  }) {
    return request({ url: '/user/register', method: 'post', data })
  },
  logout() {
    return request({ url: '/user/logout', method: 'post' })
  },
  getLoginUser() {
    return request({ url: '/user/get/login', method: 'get' })
  },
  /* ---- 平台管理：用户管理 ---- */
  listPage(data: {
    pageNum: number
    pageSize: number
    userName?: string
    userAccount?: string
    userRole?: string
  }) {
    return request({ url: '/user/list/page/vo', method: 'post', data })
  },
  add(data: {
    userName: string
    userAccount: string
    userAvatar?: string
    userProfile?: string
    userRole: string
  }) {
    return request({ url: '/user/add', method: 'post', data })
  },
  update(data: {
    id: number | string
    userName: string
    userAvatar?: string
    userProfile?: string
    userRole: string
  }) {
    return request({ url: '/user/update', method: 'post', data })
  },
  delete(id: number | string) {
    return request({ url: '/user/delete', method: 'post', data: { id } })
  },
  /* ---- 个人信息 ---- */
  updateMy(data: {
    userName: string
    userAvatar?: string
    userProfile?: string
  }) {
    return request({ url: '/user/update/my', method: 'post', data })
  },
  updatePassword(data: { oldPassword: string; newPassword: string }) {
    return request({ url: '/user/update/password', method: 'post', data })
  }
}

/* ============ 文件上传 ============ */
export const fileApi = {
  upload(file: File, dir?: string) {
    const formData = new FormData()
    formData.append('file', file)
    return request({
      url: '/file/upload',
      method: 'post',
      data: formData,
      params: dir ? { dir } : undefined,
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  uploadAvatar(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return request({
      url: '/file/upload/avatar',
      method: 'post',
      data: formData,
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

/* ============ 项目 ============ */
export const projectApi = {
  add(data: { projectName: string; projectDescription: string }) {
    return request({ url: '/project/add', method: 'post', data })
  },
  update(data: { id: number; projectName: string; projectDescription: string }) {
    return request({ url: '/project/update', method: 'post', data })
  },
  delete(id: number) {
    return request({ url: '/project/delete', method: 'post', data: { id } })
  },
  list(params: { pageNum: number; pageSize: number }) {
    return request({ url: '/project/list', method: 'get', params })
  },
  get(id: number) {
    return request({ url: '/project/get', method: 'get', params: { id } })
  }
}

/* ============ 模型 ============ */
export const modelApi = {
  add(data: { projectId: number | string; modelName: string; modelDescription?: string; version?: number }) {
    return request({ url: '/model/add', method: 'post', data })
  },
  update(data: { id: number | string; modelName: string; modelDescription?: string }) {
    return request({ url: '/model/update', method: 'post', data })
  },
  delete(id: number | string) {
    return request({ url: '/model/delete', method: 'post', data: { id } })
  },
  clear(id: number | string) {
    return request({ url: '/model/clear', method: 'post', data: { id } })
  },
  copy(data: { id: number | string; newModelName: string; newVersion?: number }) {
    return request({ url: '/model/copy', method: 'post', data })
  },
  list(projectId: number | string) {
    return request({ url: '/model/list', method: 'get', params: { projectId, pageNum: 1, pageSize: 100 } })
  },
  detail(modelId: number | string) {
    return request({ url: '/model/detail', method: 'get', params: { modelId } })
  }
}

/* ============ 实体类型 ============ */
export const entityTypeApi = {
  add(data: {
    modelId: number | string
    entityName: string
    description?: string
    color?: string
    icon?: string
  }) {
    return request({ url: '/entityType/add', method: 'post', data })
  },
  update(data: {
    id: number | string
    entityName: string
    description?: string
    color?: string
    icon?: string
  }) {
    return request({ url: '/entityType/update', method: 'post', data })
  },
  delete(id: number | string) {
    return request({ url: '/entityType/delete', method: 'post', data: { id } })
  },
  list(modelId: number | string) {
    return request({ url: '/entityType/list', method: 'get', params: { modelId } })
  },
  properties(entityTypeId: number | string) {
    return request({
      url: '/entityType/properties',
      method: 'get',
      params: { entityTypeId }
    })
  }
}

/* ============ 实体属性 ============ */
export const entityPropertyApi = {
  add(data: {
    entityTypeId: number | string
    propertyName: string
    propertyType: string
    isRequired?: number
    defaultValue?: string
    description?: string
  }) {
    return request({ url: '/entityProperty/add', method: 'post', data })
  },
  update(data: {
    id: number | string
    propertyName: string
    propertyType: string
    isRequired?: number
    defaultValue?: string
    description?: string
  }) {
    return request({ url: '/entityProperty/update', method: 'post', data })
  },
  delete(id: number | string) {
    return request({ url: '/entityProperty/delete', method: 'post', data: { id } })
  }
}

/* ============ 关系类型 ============ */
export const relationTypeApi = {
  add(data: {
    modelId: number | string
    relationName: string
    description?: string
    sourceEntityTypeId: number | string
    targetEntityTypeId: number | string
  }) {
    return request({ url: '/relationType/add', method: 'post', data })
  },
  update(data: {
    id: number | string
    relationName: string
    description?: string
    sourceEntityTypeId: number | string
    targetEntityTypeId: number | string
  }) {
    return request({ url: '/relationType/update', method: 'post', data })
  },
  delete(id: number | string) {
    return request({ url: '/relationType/delete', method: 'post', data: { id } })
  },
  list(modelId: number | string) {
    return request({ url: '/relationType/list', method: 'get', params: { modelId } })
  },
  properties(relationTypeId: number | string) {
    return request({
      url: '/relationType/properties',
      method: 'get',
      params: { relationTypeId }
    })
  }
}

/* ============ 关系属性 ============ */
export const relationPropertyApi = {
  add(data: {
    relationTypeId: number | string
    propertyName: string
    propertyType: string
    isRequired?: number
    defaultValue?: string
    description?: string
  }) {
    return request({ url: '/relationProperty/add', method: 'post', data })
  },
  update(data: {
    id: number | string
    propertyName: string
    propertyType: string
    isRequired?: number
    defaultValue?: string
    description?: string
  }) {
    return request({ url: '/relationProperty/update', method: 'post', data })
  },
  delete(id: number | string) {
    return request({ url: '/relationProperty/delete', method: 'post', data: { id } })
  }
}

/* ============ Neo4j 实体管理（数据层 CRUD） ============ */
export const entityNeo4jApi = {
  list(params: {
    modelId: number | string
    keyword?: string
    pageNum?: number
    pageSize?: number
  }) {
    return request({ url: '/entity/list', method: 'get', params })
  },
  detail(nodeId: string) {
    return request({ url: '/entity/detail', method: 'get', params: { nodeId } })
  },
  add(data: {
    modelId: number | string
    name: string
    type: string
    properties?: Record<string, any>
  }) {
    return request({ url: '/entity/add', method: 'post', data })
  },
  update(data: { nodeId: string; name: string; type: string }) {
    return request({ url: '/entity/update', method: 'post', data })
  },
  delete(nodeId: string) {
    return request({ url: '/entity/delete', method: 'post', data: { nodeId } })
  },
  setProperty(data: { nodeId: string; key: string; value: any }) {
    return request({ url: '/entity/property/set', method: 'post', data })
  },
  deleteProperty(data: { nodeId: string; key: string }) {
    return request({ url: '/entity/property/delete', method: 'post', data })
  }
}

/* ============ Neo4j 关系管理（数据层 CRUD） ============ */
export const relationNeo4jApi = {
  list(params: {
    modelId: number | string
    keyword?: string
    pageNum?: number
    pageSize?: number
  }) {
    return request({ url: '/relation/list', method: 'get', params })
  },
  detail(relId: string) {
    return request({ url: '/relation/detail', method: 'get', params: { relId } })
  },
  delete(relId: string) {
    return request({ url: '/relation/delete', method: 'post', data: { nodeId: relId } })
  },
  setProperty(data: { nodeId: string; key: string; value: any }) {
    return request({ url: '/relation/property/set', method: 'post', data })
  },
  deleteProperty(data: { nodeId: string; key: string }) {
    return request({ url: '/relation/property/delete', method: 'post', data })
  }
}

/* ============ 语料 ============ */
export interface CorpusChunkParams {
  strategy: string
  chunkSize?: number
  overlap?: number
  separator?: string
}

export interface CorpusChunkItem {
  id?: number
  corpusId?: number
  chunkIndex: number
  content: string
  startOffset: number
  endOffset: number
  charCount: number
  strategy?: string
  chunkSize?: number
  overlap?: number
  customSeparator?: string
  createTime?: string
}

export interface CorpusChunkStats {
  strategy: string
  chunkSize: number
  overlap: number
  separator?: string
  totalChunks: number
  avgCharCount: number
  duration: number
  previewChunks?: CorpusChunkItem[]
}

export const corpusApi = {
  add(data: { projectId: number; title: string; content: string }) {
    return request({ url: '/corpus/add', method: 'post', data })
  },
  upload(file: File, projectId: number, title?: string) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('projectId', String(projectId))
    if (title) formData.append('title', title)
    return request({
      url: '/corpus/upload',
      method: 'post',
      data: formData,
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  reparse(id: number) {
    return request({ url: '/corpus/reparse', method: 'post', data: { id } })
  },
  update(data: { id: number; title: string; content: string }) {
    return request({ url: '/corpus/update', method: 'post', data })
  },
  delete(id: number) {
    return request({ url: '/corpus/delete', method: 'post', data: { id } })
  },
  list(params: { projectId?: number; pageNum: number; pageSize: number }) {
    return request({ url: '/corpus/list', method: 'get', params })
  },
  get(id: number) {
    return request({ url: '/corpus/get', method: 'get', params: { id } })
  },
  /* ---- 语料分块 ---- */
  chunkPreview(id: number | string, data: CorpusChunkParams) {
    return request({ url: `/corpus/${id}/chunks/preview`, method: 'post', data, timeout: 120000 })
  },
  chunkCorpus(id: number | string, data: CorpusChunkParams) {
    return request({ url: `/corpus/${id}/chunks`, method: 'post', data, timeout: 120000 })
  },
  pageChunks(id: number | string, params: { pageNum: number; pageSize: number }) {
    return request({ url: `/corpus/${id}/chunks`, method: 'get', params })
  },
  clearChunks(id: number | string) {
    return request({ url: `/corpus/${id}/chunks`, method: 'delete' })
  }
}

/* ============ 抽取 ============ */
export const extractionApi = {
  llm(data: {
    projectId?: number
    modelId: number
    corpusId?: number
    inputText?: string
    mode?: string
    customEntityTypes?: string[]
    customRelationTypes?: string[]
    llmModelId?: number
  }) {
    return request({ url: '/extraction/llm', method: 'post', data, timeout: 300000 })
  },
  evaluate(data: { text: string; entities: any[]; relations: any[]; sampleSize?: number; llmModelId?: number; taskId?: number; metrics?: string[] }) {
    return request({ url: '/extraction/evaluate', method: 'post', data, timeout: 600000 })
  },
  evaluationList(taskId: number | undefined, params: { pageNum: number; pageSize: number; sortField?: string; sortOrder?: string }) {
    return request({ url: '/extraction/evaluate/list', method: 'get', params: { taskId, ...params } })
  },
  evaluationGet(id: number) {
    return request({ url: '/extraction/evaluate/get', method: 'get', params: { id } })
  },
  evaluationDelete(id: number) {
    return request({ url: '/extraction/evaluate/delete', method: 'post', data: { id } })
  },
  kos(data: {
    projectId?: number | string
    modelId: number | string
    corpusId?: number | string
    inputText?: string
    kosConfig?: {
      termCount?: number
      conceptCount?: number
      categoryCount?: number
      scoreBasis?: string
      weight?: number
      useWeight?: string
      targetSystems?: string[]
      multiDoc?: string
      categoryPrefix?: string
      returnWords?: string
      entityTypes?: string[]
    }
  }) {
    return request({ url: '/extraction/kos', method: 'post', data, timeout: 300000 })
  },
  structureParse(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return request({
      url: '/extraction/structure/parse',
      method: 'post',
      data: formData,
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  dl(data: {
    projectId?: number | string
    modelId: number | string
    corpusId?: number | string
    inputText?: string
    dlConfig?: {
      entityTypes?: string[]
      confidenceThreshold?: number
      maxEntities?: number
      enableRelation?: string
      relationThreshold?: number
      windowSize?: number
      embeddingDim?: number
      modelArchitecture?: string
    }
  }) {
    return request({ url: '/extraction/dl', method: 'post', data, timeout: 300000 })
  },
  structure(data: {
    projectId?: number | string
    modelId: number | string
    fileKey: string
    entityMappings?: Array<{
      entityTypeName: string
      nameColumn: string
      propertyMappings?: Array<{ sourceColumn: string; targetProperty: string }>
    }>
    relationMappings?: Array<{
      relationTypeName: string
      headNameColumn: string
      tailNameColumn: string
      headEntityTypeName?: string
      tailEntityTypeName?: string
      propertyMappings?: Array<{ sourceColumn: string; targetProperty: string }>
    }>
  }) {
    return request({ url: '/extraction/structure', method: 'post', data })
  },
  list(params: { projectId?: number | string; extractionType?: string; pageNum: number; pageSize: number; sortField?: string; sortOrder?: string }) {
    return request({ url: '/extraction/list', method: 'get', params })
  },
  get(id: number) {
    return request({ url: '/extraction/get', method: 'get', params: { id } })
  },
  delete(id: number) {
    return request({ url: '/extraction/delete', method: 'post', data: { id } })
  }
}

/* ============ 图谱探索 ============ */
export const exploreApi = {
  nodes(modelId: number | string, limit: number = 100) {
    return request({
      url: '/explore/nodes',
      method: 'get',
      params: { modelId, limit }
    })
  },
  neighbors(nodeId: string) {
    return request({ url: '/explore/neighbors', method: 'get', params: { nodeId } })
  },
  search(modelId: number | string, keyword: string) {
    return request({
      url: '/explore/search',
      method: 'get',
      params: { modelId, keyword }
    })
  },
  stats(modelId: number | string) {
    return request({ url: '/explore/stats', method: 'get', params: { modelId } })
  }
}

/* ============ 标注任务 ============ */
export const annotationTaskApi = {
  add(data: {
    taskName: string
    projectId: number | string
    corpusId?: number | string
    corpusTitle?: string
    text?: string
    annotator?: string
    reviewer?: string
  }) {
    return request({ url: '/annotationTask/add', method: 'post', data })
  },
  update(data: {
    id: number | string
    taskName?: string
    annotator?: string
    reviewer?: string
    entities?: string
    relations?: string
    totalSentences?: number
    annotatedSentences?: number
  }) {
    return request({ url: '/annotationTask/update', method: 'post', data })
  },
  delete(id: number | string) {
    return request({ url: '/annotationTask/delete', method: 'post', data: { id } })
  },
  list(params: { projectId?: number | string; taskName?: string; pageNum: number; pageSize: number }) {
    return request({ url: '/annotationTask/list', method: 'get', params })
  },
  get(id: number | string) {
    return request({ url: '/annotationTask/get', method: 'get', params: { id } })
  }
}

/* ============ 训练任务 ============ */
export const trainTaskApi = {
  add(data: {
    taskName: string
    projectId: number | string
    annotationTaskId: number | string
    dataset?: string
    architecture: string
    epochs?: number
  }) {
    return request({ url: '/trainTask/add', method: 'post', data })
  },
  list(data: {
    projectId?: number | string
    status?: string
    architecture?: string
    pageNum: number
    pageSize: number
  }) {
    return request({ url: '/trainTask/list', method: 'post', data })
  },
  get(id: number | string) {
    return request({ url: '/trainTask/get', method: 'get', params: { id } })
  },
  delete(id: number | string) {
    return request({ url: '/trainTask/delete', method: 'post', data: { id } })
  }
}

/* ============ 智能问答 ============ */
export const chatApi = {
  agentStream(data: { message: string; modelId: number | string }) {
    return request({
      url: '/v1/chat/agent/stream',
      method: 'post',
      data,
      responseType: 'stream',
      timeout: 120_000,
    })
  },
}

/* ============ 平台管理：模型管理 ============ */
/* 说明：Java 端 /v1/chat/llm-* 接口直接透传 Python 结果，无 { code, data } 统一包装，
   因此走原生 fetch（同 Chat.vue 模式），不走 axios 拦截器。 */
export interface LlmProvider {
  key: string
  label: string
  baseUrl: string
  apiKeyRequired: boolean
}

export interface LlmModelManageRow {
  id: number
  provider: string
  modelName: string
  displayName: string
  baseUrl: string
  apiKeyMasked: string
  hasKey: boolean
  isReasoner: boolean
  enabled: boolean
}

export interface LlmModelPayload {
  provider: string
  modelName: string
  displayName: string
  baseUrl: string
  apiKey?: string
  isReasoner: boolean
  enabled: boolean
}

async function llmFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  const json = await res.json().catch(() => null)
  if (!res.ok) {
    const msg = (json as any)?.detail || (json as any)?.message || `请求失败（HTTP ${res.status}）`
    throw new Error(msg)
  }
  // Java 全局异常处理器可能将 Python 错误包装为 { code, message }（HTTP 200）
  if (json && typeof json === 'object' && !Array.isArray(json) && 'code' in json && (json as any).code !== 0) {
    throw new Error((json as any).message || '请求失败')
  }
  return json as T
}

export const llmModelApi = {
  providers() {
    return llmFetch<LlmProvider[]>('/api/v1/chat/llm-providers')
  },
  list() {
    return llmFetch<LlmModelManageRow[]>('/api/v1/chat/llm-models/manage')
  },
  create(data: LlmModelPayload) {
    return llmFetch<{ id: number; message: string }>('/api/v1/chat/llm-models/manage', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
  update(id: number, data: LlmModelPayload) {
    return llmFetch<{ message: string }>(`/api/v1/chat/llm-models/manage/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },
  remove(id: number) {
    return llmFetch<{ message: string }>(`/api/v1/chat/llm-models/manage/${id}`, {
      method: 'DELETE',
    })
  },
  usage(days: number = 7) {
    return llmFetch<LlmUsageData>(`/api/v1/chat/usage?days=${days}`)
  },
}

export interface LlmUsageDaily {
  date: string
  callCount: number
  totalTokens: number
  avgDuration: number
}

export interface LlmUsageByModel {
  modelName: string
  callCount: number
  totalTokens: number
  avgDuration: number
}

export interface LlmUsageData {
  totalCalls: number
  totalTokens: number
  daily: LlmUsageDaily[]
  byModel: LlmUsageByModel[]
}

export type { ApiResponse }

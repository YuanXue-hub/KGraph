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
    return request({ url: '/model/list', method: 'get', params: { projectId } })
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
export const corpusApi = {
  add(data: { projectId: number; title: string; content: string; source?: string }) {
    return request({ url: '/corpus/add', method: 'post', data })
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
  }) {
    return request({ url: '/extraction/llm', method: 'post', data, timeout: 300000 })
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

export type { ApiResponse }

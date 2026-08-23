import { ElMessage } from 'element-plus'
import { extractionApi } from '@/api'

/**
 * 触发浏览器下载 JSON 文件
 */
export function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * 规整导出数据：结构化抽取的 result 中明细存于 extractedEntities/extractedRelations，
 * 导出时统一改为 entities/relations 字段名，并仅保留主要信息（去掉 writeCount/totalRows 等统计冗余）
 */
function normalizeExportData(data: any): unknown {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return data
  const hasDetail = Array.isArray(data.extractedEntities) || Array.isArray(data.extractedRelations)
  if (!hasDetail) return data
  return {
    entities: (data.extractedEntities || []).map((e: any) => ({
      name: e.name,
      type: e.type,
      properties: e.properties,
    })),
    relations: (data.extractedRelations || []).map((r: any) => ({
      relationType: r.relationType,
      head: r.head,
      tail: r.tail,
      properties: r.properties,
    })),
  }
}

/**
 * 导出抽取任务结果为 JSON 文件
 * 拉取任务详情，解析 result 字段（JSON 字符串），连同任务元信息一起下载
 */
export async function exportExtractionTask(row: any) {
  const res = await extractionApi.get(row.id)
  const task = res.data
  if (!task) {
    ElMessage.warning('未找到该抽取记录')
    return
  }
  let data: unknown = null
  if (task.result) {
    try {
      data = normalizeExportData(typeof task.result === 'string' ? JSON.parse(task.result) : task.result)
    } catch {
      data = task.result
    }
  }
  const payload = {
    taskId: task.id,
    extractionType: task.extractionType,
    projectId: task.projectId,
    modelId: task.modelId,
    corpusId: task.corpusId,
    status: task.status,
    duration: task.duration,
    tokenConsumed: task.tokenConsumed,
    createTime: task.createTime,
    data,
  }
  downloadJson(`extraction_${task.extractionType || 'task'}_${task.id}.json`, payload)
  ElMessage.success('导出成功')
}

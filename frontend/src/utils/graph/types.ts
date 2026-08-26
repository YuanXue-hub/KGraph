// 图谱适配器接口：G6 2D 和 3D-Force-Graph 共用

export interface GraphNode {
  id: string
  label: string
  /** 节点类型，用于颜色染色 */
  group: string
  /** 十六进制颜色 */
  color?: string
  /** 原始节点数据（用于详情面板） */
  rawData?: Record<string, any>
  /** 可选的样式扩展（2D用） */
  style?: { fill?: string; [k: string]: any }
  /** 同 group，冗余字段便于部分API */
  dataType?: string
  /** （3D内部用） */
  __val?: number
  /** （3D内部用） */
  x?: number
  y?: number
  z?: number
  vx?: number
  vy?: number
  vz?: number
  fx?: number | null
  fy?: number | null
  fz?: number | null
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  label?: string
  /** 原始边数据（用于详情面板） */
  rawData?: Record<string, any>
  /** （3D内部用） */
  sourceData?: GraphNode
  targetData?: GraphNode
}

export type GraphKind = '2d' | '3d'

export interface GraphEventHandlers {
  onNodeClick?: (node: GraphNode) => void
  onNodeDblClick?: (node: GraphNode) => void
  onEdgeClick?: (edge: GraphEdge) => void
  onCanvasClick?: () => void
}

export interface GraphAdapter {
  readonly kind: GraphKind
  /** 渲染到容器 */
  mount(container: HTMLElement): void
  /** 设置图数据（会整体替换） */
  setData(nodes: GraphNode[], edges: GraphEdge[]): void
  /** 选中指定节点（高亮） */
  selectNode(nodeId: string): void
  /** 选中指定边（高亮） */
  selectEdge(edgeId: string): void
  /** 清除所有选中态 */
  clearSelection(): void
  /** 自适应画布，padding 像素 */
  fitView(padding?: number): void
  /** 手动调整尺寸（容器 resize 后调用） */
  resize(width?: number, height?: number): void
  /** 销毁 */
  destroy(): void
}

import G6 from '@antv/g6'
import type { GraphAdapter, GraphEdge, GraphEventHandlers, GraphNode, GraphKind } from './types'

export interface G6AdapterOptions {
  handlers: GraphEventHandlers
}

export class G6Adapter implements GraphAdapter {
  readonly kind: GraphKind = '2d'
  private graph: any = null
  private container: HTMLElement | null = null
  private options: G6AdapterOptions
  private currentNodes: GraphNode[] = []
  private currentEdges: GraphEdge[] = []

  constructor(options: G6AdapterOptions) {
    this.options = options
  }

  mount(container: HTMLElement): void {
    this.container = container
    this._ensureGraph()
  }

  private _ensureGraph() {
    if (this.graph) return
    if (!this.container) return
    const width = this.container.offsetWidth
    const height = this.container.offsetHeight

    this.graph = new G6.Graph({
      container: this.container,
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
        style: {
          stroke: '#c0c4cc',
          lineWidth: 1.5,
          endArrow: { path: G6.Arrow.triangle(6, 8, 0), fill: '#c0c4cc' }
        },
        labelCfg: { style: { fill: '#909399', fontSize: 10 } }
      },
      nodeStateStyles: {
        // 优先级从低到高：dim < highlight < hover < selected（后者覆盖前者同键样式）
        // 注意：状态名不可与 G6 图形属性重名（如 path 是边的几何属性，会导致渲染崩溃）
        dim: { opacity: 0.25 },
        highlight: { stroke: '#e6a23c', lineWidth: 3, shadowColor: '#e6a23c', shadowBlur: 8 },
        hover: { stroke: '#409eff', lineWidth: 3, shadowColor: '#409eff', shadowBlur: 6 },
        selected: { stroke: '#409eff', lineWidth: 3, shadowColor: '#409eff', shadowBlur: 10 }
      },
      edgeStateStyles: {
        dim: { opacity: 0.08 },
        highlight: { stroke: '#e6a23c', lineWidth: 3 },
        hover: { stroke: '#409eff', lineWidth: 2 },
        selected: { stroke: '#409eff', lineWidth: 2.5 }
      }
    })

    // 事件绑定
    this.graph.on('node:click', (evt: any) => {
      const model = evt.item.getModel() as GraphNode
      this.options.handlers.onNodeClick?.(model)
    })
    this.graph.on('edge:click', (evt: any) => {
      const model = evt.item.getModel() as GraphEdge
      this.options.handlers.onEdgeClick?.(model)
    })
    this.graph.on('node:dblclick', (evt: any) => {
      const model = evt.item.getModel() as GraphNode
      this.options.handlers.onNodeDblClick?.(model)
    })
    this.graph.on('canvas:click', () => {
      this.options.handlers.onCanvasClick?.()
    })

    // hover 选中效果：鼠标触碰节点/边时高亮，移开恢复
    this.graph.on('node:mouseenter', (evt: any) => {
      this._setItemHover(evt.item, true)
    })
    this.graph.on('node:mouseleave', (evt: any) => {
      this._setItemHover(evt.item, false)
    })
    this.graph.on('edge:mouseenter', (evt: any) => {
      this._setItemHover(evt.item, true)
    })
    this.graph.on('edge:mouseleave', (evt: any) => {
      this._setItemHover(evt.item, false)
    })
  }

  private _setItemHover(item: any, hovered: boolean) {
    if (!this.graph || !item) return
    try {
      this.graph.setItemState(item, 'hover', hovered)
    } catch {
      /* empty */
    }
  }

  setData(nodes: GraphNode[], edges: GraphEdge[]): void {
    this.currentNodes = nodes
    this.currentEdges = edges
    this._ensureGraph()
    if (!this.graph) return
    this.graph.data({
      nodes: nodes.map((n) => ({ ...n })),
      edges: edges.map((e) => ({ ...e }))
    })
    this.graph.render()
  }

  selectNode(nodeId: string): void {
    if (!this.graph) return
    // 仅清除选中态，保留路径高亮（点击路径上的节点查看详情时路径不消失）
    this._clearItemsState('selected')
    try {
      this.graph.setItemState(nodeId, 'selected', true)
    } catch {
      /* empty */
    }
  }

  selectEdge(edgeId: string): void {
    if (!this.graph) return
    this._clearItemsState('selected')
    try {
      this.graph.setItemState(edgeId, 'selected', true)
    } catch {
      /* empty */
    }
  }

  clearSelection(): void {
    if (!this.graph) return
    this._clearItemsState('selected')
    this.clearPathHighlight()
  }

  private _clearItemsState(state: string) {
    this.currentNodes.forEach((n) => {
      try { this.graph.setItemState(n.id, state, false) } catch { /* empty */ }
    })
    this.currentEdges.forEach((e) => {
      try { this.graph.setItemState(e.id, state, false) } catch { /* empty */ }
    })
  }

  highlightPath(nodeIds: string[], edgeIds: string[]): void {
    if (!this.graph) return
    this.clearPathHighlight()
    const nodeSet = new Set(nodeIds)
    const edgeSet = new Set(edgeIds)
    this.currentNodes.forEach((n) => {
      const onPath = nodeSet.has(n.id)
      try {
        // 状态样式只作用于 keyShape（圆/线），标签需单独同步透明度，
        // 否则压暗后图形消失、文字全亮漂浮
        this.graph.updateItem(n.id, { labelCfg: { style: { opacity: onPath ? 1 : 0.25 } } })
        this.graph.setItemState(n.id, onPath ? 'highlight' : 'dim', true)
      } catch { /* empty */ }
    })
    this.currentEdges.forEach((e) => {
      const onPath = edgeSet.has(e.id)
      try {
        this.graph.updateItem(e.id, { labelCfg: { style: { opacity: onPath ? 1 : 0.1 } } })
        this.graph.setItemState(e.id, onPath ? 'highlight' : 'dim', true)
      } catch { /* empty */ }
    })
  }

  clearPathHighlight(): void {
    if (!this.graph) return
    this.currentNodes.forEach((n) => {
      try {
        this.graph.updateItem(n.id, { labelCfg: { style: { opacity: 1 } } })
        this.graph.setItemState(n.id, 'highlight', false)
        this.graph.setItemState(n.id, 'dim', false)
      } catch { /* empty */ }
    })
    this.currentEdges.forEach((e) => {
      try {
        this.graph.updateItem(e.id, { labelCfg: { style: { opacity: 1 } } })
        this.graph.setItemState(e.id, 'highlight', false)
        this.graph.setItemState(e.id, 'dim', false)
      } catch { /* empty */ }
    })
  }

  fitView(padding: number = 20): void {
    this.graph?.fitView(padding)
  }

  fitViewAfterLayout(padding: number = 60): void {
    if (!this.graph) return
    const doFit = () => {
      try { this.graph.fitView(padding) } catch { /* empty */ }
    }
    // G6 力导向布局动画收敛后触发 afterlayout；用 once 只触发一次
    this.graph.once('afterlayout', doFit)
    // 兜底：若 afterlayout 未触发（如布局已完成或无动画），1.5s 后强制 fitView
    setTimeout(doFit, 1500)
  }

  resize(width?: number, height?: number): void {
    if (!this.graph || !this.container) return
    const w = width ?? this.container.offsetWidth
    const h = height ?? this.container.offsetHeight
    this.graph.changeSize(w, h)
  }

  destroy(): void {
    if (this.graph) {
      this.graph.destroy()
      this.graph = null
    }
    this.container = null
    this.currentNodes = []
    this.currentEdges = []
  }
}

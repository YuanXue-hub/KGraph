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
        selected: { stroke: '#409eff', lineWidth: 3, shadowColor: '#409eff', shadowBlur: 10 }
      },
      edgeStateStyles: {
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
    this.clearSelection()
    try {
      this.graph.setItemState(nodeId, 'selected', true)
    } catch {
      /* empty */
    }
  }

  selectEdge(edgeId: string): void {
    if (!this.graph) return
    this.clearSelection()
    try {
      this.graph.setItemState(edgeId, 'selected', true)
    } catch {
      /* empty */
    }
  }

  clearSelection(): void {
    if (!this.graph) return
    this.currentNodes.forEach((n) => {
      try { this.graph.setItemState(n.id, 'selected', false) } catch { /* empty */ }
    })
    this.currentEdges.forEach((e) => {
      try { this.graph.setItemState(e.id, 'selected', false) } catch { /* empty */ }
    })
  }

  fitView(padding: number = 20): void {
    this.graph?.fitView(padding)
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

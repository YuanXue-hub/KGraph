import * as THREE from 'three'
import ForceGraph3D, { type ForceGraph3DInstance } from '3d-force-graph'
import type { GraphAdapter, GraphEdge, GraphEventHandlers, GraphNode, GraphKind } from './types'

export interface FG3DAdapterOptions {
  handlers: GraphEventHandlers
}

const FOCUS_SCALE = 1.25
const DIM_ALPHA = 0.2
const NORMAL_ALPHA = 1.0
const SELECTED_EMISSIVE = '#66aaff'

export class FG3DAdapter implements GraphAdapter {
  readonly kind: GraphKind = '3d'
  private static _glowTexture: THREE.CanvasTexture | null = null
  private instance: ForceGraph3DInstance | null = null
  private container: HTMLElement | null = null
  private options: FG3DAdapterOptions
  private currentNodes: GraphNode[] = []
  private currentEdges: GraphEdge[] = []
  private selectedNodeId: string | null = null
  private selectedEdgeIdx: number | null = null
  private rafTicking = false
  private labelSprites = new Map<string, THREE.Sprite>()

  constructor(options: FG3DAdapterOptions) {
    this.options = options
  }

  mount(container: HTMLElement): void {
    this.container = container
    this._ensureInstance()
  }

  private _ensureInstance() {
    if (this.instance) return
    if (!this.container) return

    const width = this.container.offsetWidth || 800
    const height = this.container.offsetHeight || 600

    // 类型声明是 new (container, config) → Instance。
    // 运行时导出的是可调用函数 ForceGraph3D()(container)，但 TS 强制用 new，
    // 这里先 cast 成 any 同时兼容两种写法。
    const ForceGraphCtor = ForceGraph3D as unknown as (cfg?: any) => (el: HTMLElement) => ForceGraph3DInstance
    const graph = ForceGraphCtor()(this.container)
      .width(width)
      .height(height)
      .backgroundColor('rgba(247,248,250,1)')
      .showNavInfo(false)
      // 力导向参数（对齐 2D 的力导强度）
      .d3AlphaDecay(0.02)
      .d3VelocityDecay(0.25)
      .nodeRelSize(6)
      .nodeVal((n: any) => (n.__val || 1) * 1.2)
      .nodeColor((n: any) => n.color || '#409eff')
      .nodeOpacity(1.0)
      .nodeResolution(16)
      .linkDirectionalArrowLength(3.5)
      .linkDirectionalArrowRelPos(1)
      .linkColor(() => '#b8bfc9')
      .linkOpacity(0.85)
      .linkWidth(1.5)
      // 节点标签使用 canvas sprite
      .nodeThreeObject((n: any) => this._buildNodeSprite(n as GraphNode))

    // 布局间距：减弱斥力让图更紧凑，球体相对图幅更大，避免“细线+小点”的观感
    try {
      ;(graph.d3Force('link') as unknown as { distance?: (d: number) => void })?.distance?.(45)
      ;(graph.d3Force('charge') as unknown as { strength?: (d: number) => void })?.strength?.(-35)
    } catch {
      /* empty */
    }

    // 补一盏定向光，强化球体的明暗立体感
    const scene = graph.scene() as THREE.Scene
    if (scene) {
      const keyLight = new THREE.DirectionalLight(0xffffff, 1.6)
      keyLight.position.set(80, 120, 60)
      scene.add(keyLight)
      // 景深雾：远处节点淡入背景色，强化 3D 纵深感知（near/far 每帧随相机距离自适应）
      scene.fog = new THREE.Fog(0xf7f8fa, 400, 1400)
    }

    // 点击事件
    graph.onNodeClick((node: any, event: MouseEvent) => {
      event.stopPropagation()
      // 双击会先触发两次单击，用小延迟区分
      this._scheduleNodeClick(node as GraphNode)
    })

    graph.onNodeRightClick(() => {
      // 预留右键
    })

    graph.onLinkClick((link: any, event: MouseEvent) => {
      event.stopPropagation()
      // 找到 edge index
      const idx = this.currentEdges.findIndex(
        (e) =>
          e.source === link.source.id &&
          e.target === link.target.id &&
          (e.label || '') === (link.label || '')
      )
      if (idx >= 0) {
        this.selectEdge(this.currentEdges[idx].id)
        this.options.handlers.onEdgeClick?.(this.currentEdges[idx])
      }
    })

    // 背景点击 → 取消选中
    graph.onBackgroundClick(() => {
      this._lastClickTs = 0
      this._lastClickNode = null
      this.options.handlers.onCanvasClick?.()
    })

    // 相机控制：轨道控制器默认启用
    const controls = graph.controls() as any
    controls.enableDamping = true
    controls.dampingFactor = 0.08

    this.instance = graph
    // 调试钩子：便于在控制台/自动化中检查 3D 场景状态
    ;(window as any).__FG3D_DEBUG__ = graph
  }

  private _lastClickTs = 0
  private _lastClickNode: GraphNode | null = null
  private _scheduleNodeClick(node: GraphNode) {
    const now = performance.now()
    const DOUBLE_CLICK_MS = 280
    if (
      this._lastClickNode &&
      this._lastClickNode.id === node.id &&
      now - this._lastClickTs < DOUBLE_CLICK_MS
    ) {
      // 触发双击
      this._lastClickTs = 0
      this._lastClickNode = null
      this.selectNode(node.id)
      this.options.handlers.onNodeDblClick?.(node)
      return
    }
    this._lastClickTs = now
    this._lastClickNode = node
    // 延迟 DOUBLE_CLICK_MS 后如果没有第二次就按单击处理
    window.setTimeout(() => {
      if (this._lastClickNode && this._lastClickNode.id === node.id && performance.now() - this._lastClickTs >= DOUBLE_CLICK_MS - 5) {
        this._lastClickNode = null
        this.selectNode(node.id)
        this.options.handlers.onNodeClick?.(node)
      }
    }, DOUBLE_CLICK_MS)
  }

  private _buildNodeSprite(n: GraphNode): THREE.Object3D {
    const group = new THREE.Group()
    const color = new THREE.Color(n.color || '#409eff')
    // 球体直径取平均边长的 ~1/4（link distance ~45），zoomToFit 后呈饱满的 3D 球
    const radius = 12 + Math.sqrt(n.__val || 1) * 3.5
    const mat = new THREE.MeshPhongMaterial({
      color,
      transparent: true,
      opacity: NORMAL_ALPHA,
      shininess: 60,
      specular: new THREE.Color(0xaad4ff),
      // 自发光用节点色淡化，避免背光面一片死黑
      emissive: color.clone().multiplyScalar(0.28)
    })
    const sphere = new THREE.Mesh(new THREE.SphereGeometry(radius, 28, 28), mat)
    sphere.userData.nodeId = n.id
    group.add(sphere)

    // 柔光晕（径向渐变 + 加色混合），增强 3D 质感
    const glow = this._makeGlowSprite(color)
    glow.scale.setScalar(radius * 2.8)
    group.add(glow)

    // 文字标签（Canvas 生成 sprite，2D 贴屏，不旋转）
    const label = n.label || n.id
    const sprite = this._makeLabelSprite(label, radius)
    sprite.position.set(0, radius + 1.6, 0)
    group.add(sprite)
    this.labelSprites.set(n.id, sprite)
    return group
  }

  private _makeGlowSprite(color: THREE.Color): THREE.Sprite {
    if (!FG3DAdapter._glowTexture) {
      const size = 128
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = size
      const ctx = canvas.getContext('2d')!
      const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
      grad.addColorStop(0, 'rgba(255,255,255,0.85)')
      grad.addColorStop(0.3, 'rgba(255,255,255,0.3)')
      grad.addColorStop(1, 'rgba(255,255,255,0)')
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, size, size)
      FG3DAdapter._glowTexture = new THREE.CanvasTexture(canvas)
    }
    const mat = new THREE.SpriteMaterial({
      map: FG3DAdapter._glowTexture,
      color: color.clone(),
      transparent: true,
      opacity: 0.4,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    })
    const sprite = new THREE.Sprite(mat)
    sprite.renderOrder = -1
    return sprite
  }

  private _makeLabelSprite(text: string, radius: number): THREE.Sprite {
    const maxChars = 14
    const displayText = text.length > maxChars ? text.slice(0, maxChars) + '…' : text
    const fontSize = Math.max(56, 16 * 3.5)
    const paddingX = 14
    const paddingY = 8
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')!
    // 先量尺寸
    ctx.font = `500 ${fontSize}px "PingFang SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
    const metrics = ctx.measureText(displayText)
    const w = Math.ceil(metrics.width) + paddingX * 2
    const h = Math.ceil(fontSize * 1.25) + paddingY * 2
    canvas.width = w
    canvas.height = h
    // 背景（胶囊，透明度低避免遮挡）
    ctx.fillStyle = 'rgba(255,255,255,0.92)'
    const r = h / 2
    ctx.beginPath()
    ctx.moveTo(r, 0)
    ctx.lineTo(w - r, 0)
    ctx.quadraticCurveTo(w, 0, w, r)
    ctx.lineTo(w, h - r)
    ctx.quadraticCurveTo(w, h, w - r, h)
    ctx.lineTo(r, h)
    ctx.quadraticCurveTo(0, h, 0, h - r)
    ctx.lineTo(0, r)
    ctx.quadraticCurveTo(0, 0, r, 0)
    ctx.closePath()
    ctx.fill()
    // 描边
    ctx.strokeStyle = 'rgba(100,116,139,0.35)'
    ctx.lineWidth = 2
    ctx.stroke()
    // 文字
    ctx.font = `500 ${fontSize}px "PingFang SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
    ctx.textBaseline = 'middle'
    ctx.textAlign = 'center'
    ctx.fillStyle = '#1f2937'
    ctx.fillText(displayText, w / 2, h / 2 + 1)

    const tex = new THREE.CanvasTexture(canvas)
    tex.needsUpdate = true
    tex.anisotropy = 4
    // 注意：three r150+ 中 depthTest:false 会导致 sprite 完全不绘制，
    // 这里用 depthWrite:false 保证标签不遮挡其他对象
    const mat = new THREE.SpriteMaterial({ map: tex, depthWrite: false, transparent: true })
    const sprite = new THREE.Sprite(mat)
    // 维持 label 与半径的比例（高度约两倍球半径，保证远距可读）
    const aspect = w / h
    const spriteH = radius * 2.2
    sprite.scale.set(spriteH * aspect, spriteH, 1)
    sprite.renderOrder = 999
    return sprite
  }

  setData(nodes: GraphNode[], edges: GraphEdge[]): void {
    this.currentNodes = nodes
    this.currentEdges = edges
    this._ensureInstance()
    if (!this.instance) return
    this.selectedNodeId = null
    this.selectedEdgeIdx = null
    this.labelSprites.clear()
    // 赋默认 __val（大小），节点类型=事件的稍微大一点
    const withVal: GraphNode[] = nodes.map((n) => {
      const isEvent = (n.group || n.dataType || '') === '事件'
      return { ...n, __val: n.__val ?? (isEvent ? 1.2 : 1.0) } as GraphNode
    })
    const linkData = edges.map((e) => ({
      source: e.source,
      target: e.target,
      label: e.label || '',
      id: e.id,
      rawData: e.rawData
    }))
    this.instance.graphData({ nodes: withVal as any[], links: linkData as any[] })
    // 启动冷却后的视角适配
    this.instance.onEngineStop(() => {
      try {
        if (this.instance && this.container) {
          this.instance.zoomToFit(400, 60)
          // zoomToFit 后相机正对 z 轴且取景偏保守（节点显小），
          // 这里按图幅精确计算取景距离，并补一个斜向视角增强立体感
          window.setTimeout(() => {
            if (!this.instance) return
            const cam = this.instance.camera() as THREE.PerspectiveCamera
            const target = (this.instance.controls() as any)?.target as THREE.Vector3 | undefined
            if (!cam || !target) return
            const data = (this.instance.graphData() || { nodes: [] }) as { nodes?: any[] }
            let r = 0
            ;(data.nodes || []).forEach((n) => {
              if (typeof n.x === 'number' && typeof n.y === 'number' && typeof n.z === 'number') {
                r = Math.max(
                  r,
                  Math.sqrt(
                    (n.x - target.x) ** 2 + (n.y - target.y) ** 2 + (n.z - target.z) ** 2
                  )
                )
              }
            })
            r += 20 // 节点半径 + 标签外扩
            const fov = (cam.fov * Math.PI) / 180
            const dist = Math.max((r / Math.tan(fov / 2)) * 1.12, 120)
            this.instance.cameraPosition(
              { x: target.x + dist * 0.5, y: target.y + dist * 0.34, z: target.z + dist * 0.8 },
              { x: target.x, y: target.y, z: target.z },
              600
            )
          }, 900)
        }
      } catch {
        /* empty */
      }
    })
    // 每帧更新邻居聚焦 + 选中态
    this._bindFrameUpdate()
  }

  private _bindFrameUpdate() {
    if (!this.instance) return
    const graph = this.instance
    const scene = graph.scene() as THREE.Scene
    if (!scene) return

    const tick = () => {
      if (!this.instance) return
      this._updateFog()
      this._applySelectionAndFocus()
      requestAnimationFrame(tick)
    }
    if (!this.rafTicking) {
      this.rafTicking = true
      requestAnimationFrame(tick)
    }
  }

  private _updateFog() {
    if (!this.instance) return
    const scene = this.instance.scene() as THREE.Scene
    const fog = scene?.fog as THREE.Fog | null
    if (!fog) return
    try {
      const cam = this.instance.camera() as THREE.PerspectiveCamera
      const target = (this.instance.controls() as any)?.target as THREE.Vector3 | undefined
      if (!cam || !target) return
      const dist = cam.position.distanceTo(target)
      fog.near = dist * 0.9
      fog.far = dist * 3.2
    } catch {
      /* empty */
    }
  }

  private _applySelectionAndFocus() {
    if (!this.instance) return
    const graphData = (this.instance.graphData() || {}) as { nodes?: any[]; links?: any[] }
    const nodes = graphData.nodes || []
    const links = graphData.links || []

    // 计算相邻集合
    const adjacentNodeIds = new Set<string>()
    const adjacentLinkIdx = new Set<number>()
    if (this.selectedNodeId) {
      adjacentNodeIds.add(this.selectedNodeId)
      links.forEach((l, i) => {
        const sId = (typeof l.source === 'object' ? l.source.id : l.source) as string
        const tId = (typeof l.target === 'object' ? l.target.id : l.target) as string
        if (sId === this.selectedNodeId || tId === this.selectedNodeId) {
          adjacentNodeIds.add(sId)
          adjacentNodeIds.add(tId)
          adjacentLinkIdx.add(i)
        }
      })
    }
    const hasSelected = !!this.selectedNodeId || this.selectedEdgeIdx !== null

    nodes.forEach((n) => {
      const obj = n.__threeObj as THREE.Object3D | undefined
      if (!obj) return
      const sphere = obj.children[0] as THREE.Mesh | undefined
      if (!sphere) return
      const mat = sphere.material as THREE.MeshPhongMaterial
      const dimmed = hasSelected && !adjacentNodeIds.has(n.id)
      if (n.id === this.selectedNodeId) {
        mat.opacity = NORMAL_ALPHA
        mat.emissive = new THREE.Color(SELECTED_EMISSIVE)
        mat.emissiveIntensity = 0.45
        sphere.scale.setScalar(FOCUS_SCALE)
      } else {
        mat.emissive = new THREE.Color(0x000000)
        mat.emissiveIntensity = 0.0
        sphere.scale.setScalar(1.0)
        mat.opacity = dimmed ? DIM_ALPHA : NORMAL_ALPHA
      }
      // 光晕透明度同步（children[1] 为 glow sprite）
      const glow = obj.children[1] as THREE.Sprite | undefined
      if (glow) {
        ;(glow.material as THREE.SpriteMaterial).opacity = n.id === this.selectedNodeId ? 0.85 : dimmed ? 0.06 : 0.4
      }
      // 标签透明度同步
      const labelSprite = this.labelSprites.get(n.id)
      if (labelSprite) {
        ;(labelSprite.material as THREE.SpriteMaterial).opacity = dimmed ? 0.1 : 1.0
      }
    })

    links.forEach((l, i) => {
      const lineObj = l.__lineObj as THREE.Line | undefined
      if (!lineObj) return
      const mat = lineObj.material as THREE.LineBasicMaterial
      const arrowObj = l.__arrowObj as THREE.Mesh | undefined
      const arrowMat = arrowObj ? (arrowObj.material as THREE.MeshBasicMaterial) : null
      if (this.selectedEdgeIdx === i) {
        mat.color = new THREE.Color('#409eff')
        mat.opacity = 1.0
        if (arrowMat) arrowMat.color = new THREE.Color('#409eff')
      } else {
        const isAdj = this.selectedNodeId !== null && adjacentLinkIdx.has(i)
        mat.color = new THREE.Color(isAdj ? '#8ab4f8' : '#b8bfc9')
        mat.opacity = hasSelected ? (isAdj ? 1.0 : 0.12) : 0.85
        if (arrowMat) arrowMat.opacity = mat.opacity
      }
    })
  }

  selectNode(nodeId: string): void {
    this.selectedNodeId = nodeId
    this.selectedEdgeIdx = null
    if (!this.instance) return
    // 相机平滑飞向目标节点
    try {
      const graphData = (this.instance.graphData() || { nodes: [] }) as { nodes: any[] }
      const node = graphData.nodes.find((n) => n.id === nodeId)
      if (node && typeof node.x === 'number' && typeof node.y === 'number' && typeof node.z === 'number') {
        const dist = 60
        this.instance.cameraPosition(
          { x: node.x + dist * 0.6, y: node.y + dist * 0.4, z: node.z + dist * 0.8 },
          { x: node.x, y: node.y, z: node.z },
          500
        )
      }
    } catch {
      /* empty */
    }
  }

  selectEdge(edgeId: string): void {
    const idx = this.currentEdges.findIndex((e) => e.id === edgeId)
    this.selectedEdgeIdx = idx >= 0 ? idx : null
    this.selectedNodeId = null
  }

  clearSelection(): void {
    this.selectedNodeId = null
    this.selectedEdgeIdx = null
  }

  fitView(padding: number = 40): void {
    this.instance?.zoomToFit(500, padding)
  }

  resize(width?: number, height?: number): void {
    if (!this.instance || !this.container) return
    const w = width ?? this.container.offsetWidth
    const h = height ?? this.container.offsetHeight
    this.instance.width(w).height(h)
  }

  destroy(): void {
    this.rafTicking = false
    if (this.instance) {
      try {
        this.instance._destructor?.()
      } catch {
        /* empty */
      }
      // 清空 container（3D-force-graph 没有暴露 destroy API，手动清空 DOM 即可）
      if (this.container) {
        while (this.container.firstChild) {
          try { this.container.removeChild(this.container.firstChild) } catch { /* empty */ }
        }
      }
      this.instance = null
    }
    this.container = null
    this.currentNodes = []
    this.currentEdges = []
    this.selectedNodeId = null
    this.selectedEdgeIdx = null
    this.labelSprites.clear()
  }
}

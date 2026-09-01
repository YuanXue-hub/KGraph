import * as THREE from 'three'
import ForceGraph3D, { type ForceGraph3DInstance } from '3d-force-graph'
import type { GraphAdapter, GraphEdge, GraphEventHandlers, GraphNode, GraphKind } from './types'

export interface FG3DAdapterOptions {
  handlers: GraphEventHandlers
}

const DIM_ALPHA = 0.18
const NORMAL_ALPHA = 1.0
// 浅色主题配色（对齐首页风格：浅灰蓝底 + 品牌蓝 + 柔和粒子）
const BG_COLOR = 0xf7f9fc
const LINK_COLOR = '#c3cbd9'
const LINK_COLOR_ADJ = '#165dff'
const LINK_COLOR_SEL = '#0e42d2'

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
  private linkMats = new Map<any, THREE.LineBasicMaterial>()
  private starfield: THREE.Points | null = null
  private twinklePhase = new Map<string, number>()

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
      .backgroundColor('rgba(247,249,252,1)')
      .showNavInfo(false)
      // 力导向参数（对齐 2D 的力导强度）
      .d3AlphaDecay(0.02)
      .d3VelocityDecay(0.25)
      .nodeRelSize(6)
      .nodeVal((n: any) => (n.__val || 1) * 1.2)
      .nodeColor((n: any) => n.color || '#409eff')
      .nodeOpacity(1.0)
      .nodeResolution(16)
      .linkDirectionalArrowLength(3)
      .linkDirectionalArrowRelPos(1)
      .linkColor(() => LINK_COLOR)
      .linkOpacity(0.45)
      // 注意：linkWidth>0 会将边渲染为细圆柱 Mesh（精确几何拾取，屏幕上仅约 2px，极难点中）。
      // 这里保持默认细线渲染，并放宽射线拾取容差（世界坐标单位），让边容易点中
      .linkHoverPrecision(8)
      // 节点标签使用 canvas sprite
      .nodeThreeObject((n: any) => this._buildNodeSprite(n as GraphNode))

    // 布局间距：减弱斥力让图更紧凑，粒子相对图幅更大，避免“细线+小点”的观感
    try {
      ;(graph.d3Force('link') as unknown as { distance?: (d: number) => void })?.distance?.(45)
      ;(graph.d3Force('charge') as unknown as { strength?: (d: number) => void })?.strength?.(-35)
    } catch {
      /* empty */
    }

    const scene = graph.scene() as THREE.Scene
    if (scene) {
      // 浅色雾：远处元素淡入背景色，强化 3D 纵深感知（near/far 每帧随相机距离自适应）
      scene.fog = new THREE.Fog(BG_COLOR, 400, 1400)
      // 光照说明：3d-force-graph 场景自带默认灯光（AmbientLight + DirectionalLight），
      // 配合节点 Phong 材质即可产生立体明暗与高光，无需额外加灯（避免双重曝光）
      // 背景微尘粒子：浅色主题氛围点缀
      this._addStarfield(scene)
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
      // 优先按 id 匹配（setData 时已写入 id），比 source/target/label 组合更可靠
      let idx = this.currentEdges.findIndex((e) => e.id === link.id)
      if (idx < 0) {
        idx = this.currentEdges.findIndex(
          (e) =>
            e.source === link.source.id &&
            e.target === link.target.id &&
            (e.label || '') === (link.label || '')
        )
      }
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
    // 浅色主题：Phong 材质受光照影响，呈现立体球体（明暗面 + 高光点）
    const coreRadius = 2.6 + Math.sqrt(n.__val || 1) * 1.5
    const coreMat = new THREE.MeshPhongMaterial({
      color: color.clone().lerp(new THREE.Color('#ffffff'), 0.08),
      shininess: 55,
      specular: new THREE.Color('#9aa7bd'),
      transparent: true,
      opacity: NORMAL_ALPHA
    })
    const core = new THREE.Mesh(new THREE.SphereGeometry(coreRadius, 24, 24), coreMat)
    core.userData.nodeId = n.id
    group.add(core)

    // 内层光晕（小而亮）
    const glowIn = this._makeGlowSprite(color, 0.55)
    const sIn = coreRadius * 3.6
    glowIn.scale.set(sIn, sIn, 1)
    glowIn.userData.baseScale = sIn
    group.add(glowIn)

    // 外层光晕（大而弥散）
    const glowOut = this._makeGlowSprite(color, 0.28)
    const sOut = coreRadius * 7
    glowOut.scale.set(sOut, sOut, 1)
    glowOut.userData.baseScale = sOut
    group.add(glowOut)

    // 文字标签（Canvas 生成 sprite，2D 贴屏，不旋转）
    const label = n.label || n.id
    const sprite = this._makeLabelSprite(label, coreRadius)
    sprite.position.set(0, coreRadius * 5 + 2, 0)
    group.add(sprite)
    this.labelSprites.set(n.id, sprite)
    return group
  }

  private _makeGlowSprite(color: THREE.Color, opacity: number): THREE.Sprite {
    if (!FG3DAdapter._glowTexture) {
      const size = 128
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = size
      const ctx = canvas.getContext('2d')!
      // 粒子光晕：中心锐利高亮，向外快速衰减
      const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
      grad.addColorStop(0, 'rgba(255,255,255,1)')
      grad.addColorStop(0.25, 'rgba(255,255,255,0.55)')
      grad.addColorStop(0.55, 'rgba(255,255,255,0.14)')
      grad.addColorStop(1, 'rgba(255,255,255,0)')
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, size, size)
      FG3DAdapter._glowTexture = new THREE.CanvasTexture(canvas)
    }
    const mat = new THREE.SpriteMaterial({
      map: FG3DAdapter._glowTexture,
      // 浅色底：光晕向白色淡化，普通混合呈现"柔和色环"而非深底加色辉光
      color: color.clone().lerp(new THREE.Color('#ffffff'), 0.35),
      transparent: true,
      opacity,
      depthWrite: false,
      fog: false
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
    // 背景（白色半透明胶囊，适配浅色主题）
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
    ctx.strokeStyle = 'rgba(201,205,212,0.9)'
    ctx.lineWidth = 2
    ctx.stroke()
    // 文字
    ctx.font = `500 ${fontSize}px "PingFang SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
    ctx.textBaseline = 'middle'
    ctx.textAlign = 'center'
    ctx.fillStyle = '#1d2129'
    ctx.fillText(displayText, w / 2, h / 2 + 1)

    const tex = new THREE.CanvasTexture(canvas)
    tex.needsUpdate = true
    tex.anisotropy = 4
    // 注意：three r150+ 中 depthTest:false 会导致 sprite 完全不绘制，
    // 这里用 depthWrite:false 保证标签不遮挡其他对象
    const mat = new THREE.SpriteMaterial({ map: tex, depthWrite: false, transparent: true })
    const sprite = new THREE.Sprite(mat)
    // 世界空间固定高度（link distance ~45），保证远距可读；大节点稍大
    const aspect = w / h
    const spriteH = 6 + radius * 0.5
    sprite.scale.set(spriteH * aspect, spriteH, 1)
    sprite.renderOrder = 999
    return sprite
  }

  /** 背景微尘粒子：浅色主题下的柔和漂浮点缀，营造空间纵深 */
  private _addStarfield(scene: THREE.Scene) {
    const count = 400
    const pos = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      // 球壳均匀随机分布
      const r = 500 + Math.random() * 1200
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      pos[i * 3 + 2] = r * Math.cos(phi)
    }
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    const mat = new THREE.PointsMaterial({
      color: 0xaeb8c8,
      size: 2.0,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.4,
      depthWrite: false,
      fog: false
    })
    this.starfield = new THREE.Points(geo, mat)
    scene.add(this.starfield)
  }

  setData(nodes: GraphNode[], edges: GraphEdge[]): void {
    this.currentNodes = nodes
    this.currentEdges = edges
    this._ensureInstance()
    if (!this.instance) return
    this.selectedNodeId = null
    this.selectedEdgeIdx = null
    this.labelSprites.clear()
    this.linkMats.forEach((m) => m.dispose())
    this.linkMats.clear()
    this.twinklePhase.clear()
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
            r += 30 // 节点光晕 + 标签外扩
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
      // 星场缓慢旋转，深空氛围微动效
      if (this.starfield) this.starfield.rotation.y += 0.00035
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
      fog.near = dist * 1.1
      fog.far = dist * 4.0
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
    const tNow = performance.now() / 1000

    nodes.forEach((n) => {
      const obj = n.__threeObj as THREE.Object3D | undefined
      if (!obj) return
      const core = obj.children[0] as THREE.Mesh | undefined
      if (!core) return
      const coreMat = core.material as THREE.MeshPhongMaterial
      const glowIn = obj.children[1] as THREE.Sprite | undefined
      const glowOut = obj.children[2] as THREE.Sprite | undefined
      const dimmed = hasSelected && !adjacentNodeIds.has(n.id)
      const selected = n.id === this.selectedNodeId

      // 微呼吸：光晕轻微律动，营造粒子场流动感
      if (!this.twinklePhase.has(n.id)) this.twinklePhase.set(n.id, Math.random() * Math.PI * 2)
      const phase = this.twinklePhase.get(n.id)!
      const twinkle = 1 + 0.07 * Math.sin(tNow * 2.4 + phase)

      if (selected) {
        // 选中不放大，仅保持高亮（光晕增亮），避免视觉跳动
        coreMat.opacity = NORMAL_ALPHA
        core.scale.setScalar(1.0)
      } else {
        coreMat.opacity = dimmed ? DIM_ALPHA : NORMAL_ALPHA
        core.scale.setScalar(1.0)
      }

      // 双层光晕：选中放大增亮，非关联压暗（浅色底用较低基准透明度）
      if (glowIn) {
        const gm = glowIn.material as THREE.SpriteMaterial
        const base = (glowIn.userData.baseScale as number) || glowIn.scale.x
        const k = selected ? 1.25 : 1
        const f = selected ? 0.8 : dimmed ? 0.06 : 0.5
        gm.opacity = f * twinkle
        glowIn.scale.set(base * k * twinkle, base * k * twinkle, 1)
      }
      if (glowOut) {
        const gm = glowOut.material as THREE.SpriteMaterial
        const base = (glowOut.userData.baseScale as number) || glowOut.scale.x
        const k = selected ? 1.3 : 1
        const f = selected ? 0.6 : dimmed ? 0.04 : 0.25
        gm.opacity = f * twinkle
        glowOut.scale.set(base * k * twinkle, base * k * twinkle, 1)
      }

      // 标签透明度同步
      const labelSprite = this.labelSprites.get(n.id)
      if (labelSprite) {
        ;(labelSprite.material as THREE.SpriteMaterial).opacity = dimmed ? 0.08 : 1.0
      }
    })

    links.forEach((l, i) => {
      const lineObj = l.__lineObj as THREE.Line | undefined
      if (!lineObj) return
      // three-forcegraph 按颜色共享材质实例，直接改共享材质会让所有边互相覆盖。
      // 这里为每条边分配独立材质，才能逐边高亮/压暗
      let mat = this.linkMats.get(l)
      if (!mat) {
        mat = new THREE.LineBasicMaterial({ color: LINK_COLOR, transparent: true, opacity: 0.45 })
        this.linkMats.set(l, mat)
      }
      if (lineObj.material !== mat) lineObj.material = mat
      const arrowObj = l.__arrowObj as THREE.Mesh | undefined
      const arrowMat = arrowObj ? (arrowObj.material as THREE.MeshLambertMaterial) : null
      if (this.selectedEdgeIdx === i) {
        mat.color = new THREE.Color(LINK_COLOR_SEL)
        mat.opacity = 1.0
        if (arrowMat) arrowMat.color = new THREE.Color(LINK_COLOR_SEL)
      } else {
        const isAdj = this.selectedNodeId !== null && adjacentLinkIdx.has(i)
        mat.color = new THREE.Color(isAdj ? LINK_COLOR_ADJ : LINK_COLOR)
        mat.opacity = hasSelected ? (isAdj ? 0.9 : 0.08) : 0.45
        if (arrowMat) arrowMat.opacity = mat.opacity
      }
    })
  }

  selectNode(nodeId: string): void {
    this.selectedNodeId = nodeId
    this.selectedEdgeIdx = null
    // 点击仅高亮选中（不移动相机），视角保持用户当前操控状态，可随时继续点击其他元素
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
    this.linkMats.forEach((m) => m.dispose())
    this.linkMats.clear()
    this.starfield = null
    this.twinklePhase.clear()
  }
}

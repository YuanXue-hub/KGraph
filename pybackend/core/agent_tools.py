"""LangChain Agent 工具集 —— 封装 Neo4j 图谱查询能力。

每个工具都接收 modelId 参数，确保查询结果限定在指定图谱模型内。
"""

from typing import Any, Dict, List

from langchain_core.tools import tool
from neo4j import GraphDatabase


class _Neo4jToolContext:
    """持有 Neo4j driver 并注入到工具函数中。"""

    driver: Any = None

    @classmethod
    def init(cls, config: Dict[str, Any]) -> None:
        neo4j_cfg = config.get("neo4j", {})
        cls.driver = GraphDatabase.driver(
            neo4j_cfg.get("url"),
            auth=(neo4j_cfg.get("username"), neo4j_cfg.get("password")),
        )

    @classmethod
    def close(cls) -> None:
        if cls.driver:
            cls.driver.close()


def _query(cypher: str, **params) -> List[Dict[str, Any]]:
    """执行 Cypher 查询并返回记录列表。"""
    with _Neo4jToolContext.driver.session() as session:
        result = session.run(cypher, **params)
        return [dict(record) for record in result]


# ==================== 工具定义 ====================


@tool
def search_entities(model_id: int, keyword: str, limit: int = 10) -> str:
    """根据关键词搜索实体节点。返回匹配的实体名称、类型和属性列表。"""
    records = _query(
        """
        MATCH (n:Entity {modelId: $modelId})
        WHERE n.name CONTAINS $keyword
        RETURN n.name AS name, n.type AS type, properties(n) AS props
        LIMIT $limit
        """,
        modelId=model_id,
        keyword=keyword,
        limit=limit,
    )
    if not records:
        return "未找到匹配的实体。"
    lines = []
    for r in records:
        name = r.get("name", "")
        etype = r.get("type", "")
        props = {k: v for k, v in (r.get("props") or {}).items() if k not in ("modelId", "createTime", "name", "type")}
        prop_str = ", ".join(f"{k}={v}" for k, v in props.items()) if props else ""
        lines.append(f"- {name}（类型: {etype}）{prop_str}")
    return "\n".join(lines)


@tool
def get_entity_detail(model_id: int, name: str) -> str:
    """获取指定实体的完整属性信息。"""
    records = _query(
        """
        MATCH (n:Entity {name: $name, modelId: $modelId})
        RETURN n.name AS name, n.type AS type, properties(n) AS props
        LIMIT 1
        """,
        modelId=model_id,
        name=name,
    )
    if not records:
        return f"未找到实体「{name}」。"
    r = records[0]
    props = {k: v for k, v in (r.get("props") or {}).items() if k not in ("modelId", "createTime", "name", "type")}
    lines = [f"实体名称: {r.get('name')}", f"实体类型: {r.get('type')}"]
    if props:
        lines.append("属性:")
        for k, v in props.items():
            lines.append(f"  - {k}: {v}")
    return "\n".join(lines)


@tool
def get_entity_relations(model_id: int, name: str, limit: int = 20) -> str:
    """获取指定实体的所有关系（作为头实体或尾实体）。
    同时覆盖 :RELATION（普通关系）和 :CAUSES（因果边）两种关系类型；
    因果边额外标注 [因果FORWARD] 或 [因果PREVENT] 前缀。"""
    # 出边：不限定关系类型，覆盖 :RELATION + :CAUSES
    out_records = _query(
        """
        MATCH (a:Entity {name: $name, modelId: $modelId})-[r]->(b:Entity {modelId: $modelId})
        RETURN a.name AS head,
               coalesce(r.type, r.direction, type(r)) AS relation,
               type(r) AS relationType,
               coalesce(r.direction, '') AS direction,
               b.name AS tail
        LIMIT $limit
        """,
        modelId=model_id,
        name=name,
        limit=limit,
    )
    # 入边：同样不限定关系类型
    in_records = _query(
        """
        MATCH (a:Entity {modelId: $modelId})-[r]->(b:Entity {name: $name, modelId: $modelId})
        RETURN a.name AS head,
               coalesce(r.type, r.direction, type(r)) AS relation,
               type(r) AS relationType,
               coalesce(r.direction, '') AS direction,
               b.name AS tail
        LIMIT $limit
        """,
        modelId=model_id,
        name=name,
        limit=limit,
    )

    def _prefix(r: dict) -> str:
        rt = r.get("relationType", "")
        d = r.get("direction", "")
        if rt == "CAUSES" and d == "PREVENT":
            return "[因果·预防]"
        if rt == "CAUSES":
            return "[因果]"
        return ""

    lines = []
    if out_records:
        lines.append(f"「{name}」作为头实体的关系:")
        for r in out_records:
            pre = _prefix(r)
            lines.append(f"  - {r['head']} --[{pre}{r['relation']}]--> {r['tail']}")
    if in_records:
        lines.append(f"「{name}」作为尾实体的关系:")
        for r in in_records:
            pre = _prefix(r)
            lines.append(f"  - {r['head']} --[{pre}{r['relation']}]--> {r['tail']}")
    if not lines:
        return f"「{name}」暂无关系。"
    return "\n".join(lines)


@tool
def get_graph_stats(model_id: int) -> str:
    """获取当前图谱模型的统计信息：节点总数、关系总数（含因果边）、实体类型分布。"""
    node_count = _query(
        "MATCH (n:Entity {modelId: $modelId}) RETURN count(n) AS cnt",
        modelId=model_id,
    )
    # 同时统计 :RELATION 和 :CAUSES 两种关系类型
    rel_count = _query(
        """
        MATCH ()-[r {modelId: $modelId}]->()
        WHERE type(r) IN ['RELATION', 'CAUSES']
        RETURN count(r) AS cnt
        """,
        modelId=model_id,
    )
    # 因果边单独计数
    causal_count = _query(
        "MATCH ()-[r:CAUSES {modelId: $modelId}]->() RETURN count(r) AS cnt",
        modelId=model_id,
    )
    type_dist = _query(
        """
        MATCH (n:Entity {modelId: $modelId})
        RETURN n.type AS type, count(n) AS cnt
        ORDER BY cnt DESC
        LIMIT 10
        """,
        modelId=model_id,
    )

    total_nodes = node_count[0]["cnt"] if node_count else 0
    total_rels = rel_count[0]["cnt"] if rel_count else 0
    total_causal = causal_count[0]["cnt"] if causal_count else 0
    total_normal = total_rels - total_causal

    lines = [
        f"图谱统计: 实体总数 {total_nodes}, 关系总数 {total_rels} "
        f"(普通关系 {total_normal}, 因果边 {total_causal})",
        "实体类型分布:",
    ]
    for t in type_dist:
        lines.append(f"  - {t['type']}: {t['cnt']} 个")
    return "\n".join(lines)


@tool
def list_entity_types(model_id: int) -> str:
    """列出当前图谱模型中所有的实体类型。"""
    records = _query(
        """
        MATCH (n:Entity {modelId: $modelId})
        RETURN DISTINCT n.type AS type
        ORDER BY type
        """,
        modelId=model_id,
    )
    if not records:
        return "当前图谱模型暂无实体。"
    types = [r["type"] for r in records]
    return f"当前图谱包含以下实体类型: {', '.join(types)}"


@tool
def get_entities_by_type(model_id: int, entity_type: str, limit: int = 50) -> str:
    """按实体类型查询实体列表。当用户询问"某类型有哪些实体"（如"人物有哪些"、"地点有什么"）时使用此工具。"""
    records = _query(
        """
        MATCH (n:Entity {modelId: $modelId, type: $entityType})
        RETURN n.name AS name, properties(n) AS props
        ORDER BY n.name
        LIMIT $limit
        """,
        modelId=model_id,
        entityType=entity_type,
        limit=limit,
    )
    if not records:
        return f"未找到类型为「{entity_type}」的实体。"
    lines = [f"类型「{entity_type}」共有 {len(records)} 个实体（最多展示 {limit} 个）:"]
    for r in records:
        name = r.get("name", "")
        props = {k: v for k, v in (r.get("props") or {}).items() if k not in ("modelId", "createTime", "name", "type")}
        prop_str = ", ".join(f"{k}={v}" for k, v in props.items()) if props else ""
        lines.append(f"- {name}" + (f"（{prop_str}）" if prop_str else ""))
    return "\n".join(lines)


@tool
def get_entities_by_name(model_id: int, name: str, limit: int = 20) -> str:
    """根据实体名称查询多条实体数据。同名实体在图谱中可能存在多个不同类型的版本，本工具返回全部匹配记录。

    参数说明：
      - model_id: 图谱模型 ID
      - name:     实体名称（精确匹配 name 或 canonicalName）
      - limit:    最多返回的记录条数，根据问题需要自行决定（如只需要概况传 5，需要全量传 50）

    适用场景：用户问「某名称的实体有哪些记录/版本/类型」或需要确认同名实体的多个类型时使用。"""
    if not name or not name.strip():
        return "错误：name 不能为空。"
    name = name.strip()
    limit = max(1, min(100, int(limit)))

    records = _query(
        """
        MATCH (n:Entity {modelId: $modelId})
        WHERE n.name = $name OR n.canonicalName = $name
        RETURN n.name AS name, n.type AS type, properties(n) AS props
        ORDER BY n.type
        LIMIT $limit
        """,
        modelId=model_id,
        name=name,
        limit=limit,
    )
    if not records:
        return f"未找到名称为「{name}」的实体，可用 search_entities 做模糊搜索确认名称。"

    lines = [f"名称为「{name}」的实体共匹配 {len(records)} 条记录:"]
    for idx, r in enumerate(records, 1):
        etype = r.get("type", "")
        props = {k: v for k, v in (r.get("props") or {}).items()
                 if k not in ("modelId", "createTime", "name", "type", "canonicalName")}
        prop_str = ", ".join(f"{k}={v}" for k, v in props.items()) if props else ""
        lines.append(f"{idx}. {name}（类型: {etype}）{prop_str}")
    return "\n".join(lines)


@tool
def get_causal_chain(
    model_id: int,
    start_entity: str,
    end_entity: str | None = None,
    max_hops: int = 3,
    direction: str = "BOTH",
    limit_paths: int = 10,
) -> str:
    """查询因果链路径：基于 [:CAUSES] 关系做 BFS 多跳遍历。

    参数说明：
      - model_id:       图谱模型 ID
      - start_entity:   起始节点名称（必填，对应 canonicalName 或 name）
      - end_entity:     可选，目标节点名称；填了就查「起点→终点」的最短因果路径；
                        不填就查「起点向外辐射」的多跳因果邻居树
      - max_hops:       最大跳数，1~5；默认 3 跳（覆盖 A→B→C→D 级联影响）
      - direction:      FORWARD=只查正向因果（导致/使得）；PREVENT=只查预防因果；
                        BOTH=两类因果都查（默认）
      - limit_paths:    最多返回路径条数，默认 10 条避免输出过长

    典型用法：
      · "疫情应急响应 后续引发了什么连锁反应？" → start_entity="启动应急响应" end_entity=None
      · "休市 和 康泰生物涨停 之间有因果关系吗？" → start_entity="华南海鲜市场休市" end_entity="康泰生物涨停"
    """
    # ---- 参数规范 ----
    if not start_entity or not start_entity.strip():
        return "错误：start_entity 不能为空。"
    start_entity = start_entity.strip()
    end_entity = end_entity.strip() if (end_entity and end_entity.strip()) else None
    max_hops = max(1, min(5, int(max_hops)))       # 夹到 1~5
    limit_paths = max(1, min(50, int(limit_paths)))

    # 构建方向过滤条件：方向 BOTH 时不过滤；FORWARD/PREVENT 精确限定
    dir_filter = ""
    if direction == "FORWARD":
        dir_filter = " AND r.direction = 'FORWARD'"
    elif direction == "PREVENT":
        dir_filter = " AND r.direction = 'PREVENT'"

    # ====================================================================
    # 场景 A：指定了 end_entity → 查 start→end 的最短路径（BFS，逐跳扩展）
    # ====================================================================
    if end_entity:
        # 先确认起终点都存在，不存在就提示用户
        exist = _query(
            """
            MATCH (s:Entity {modelId: $mid})
            WHERE s.canonicalName = $start OR s.name = $start
            WITH s
            MATCH (e:Entity {modelId: $mid})
            WHERE e.canonicalName = $end OR e.name = $end
            RETURN count(DISTINCT s) AS s_cnt, count(DISTINCT e) AS e_cnt
            """,
            mid=model_id, start=start_entity, end=end_entity,
        )
        if not exist or exist[0]["s_cnt"] == 0:
            return f"未找到起始实体「{start_entity}」，请先通过 search_entities 确认名称。"
        if exist[0]["e_cnt"] == 0:
            return f"未找到目标实体「{end_entity}」，请先通过 search_entities 确认名称。"

        # 逐步增加跳数找最短路径（1..max_hops），Neo4j variable-length path 天然支持 BFS
        paths_records = _query(
            f"""
            MATCH path = (s:Entity {{modelId: $mid}})-[r:CAUSES *..{max_hops}]->(e:Entity {{modelId: $mid}})
            WHERE (s.canonicalName = $start OR s.name = $start)
              AND (e.canonicalName = $end OR e.name = $end)
              AND ALL(rel IN relationships(path) WHERE NOT coalesce(rel.isBackEdge, false){dir_filter.replace('AND r.direction', ' AND rel.direction')})
            WITH path, length(path) AS hops,
                 [rel IN relationships(path) | coalesce(rel.type, rel.signalWord, rel.direction)] AS edges,
                 [rel IN relationships(path) | coalesce(rel.direction, 'FORWARD')]     AS dirs,
                 [rel IN relationships(path) | coalesce(rel.confidence, -1.0)]          AS confs,
                 [n IN nodes(path) | coalesce(n.canonicalName, n.name)]                 AS nodes
            RETURN nodes, edges, dirs, confs, hops
            ORDER BY hops ASC, reduce(acc = 1.0, c IN confs | acc * c) DESC
            LIMIT $lim
            """,
            mid=model_id, start=start_entity, end=end_entity, lim=limit_paths,
        )

        if not paths_records:
            return (
                f"在 {max_hops} 跳以内未找到「{start_entity}」→「{end_entity}」的因果路径。\n"
                f"提示：可以调大 max_hops（当前 {max_hops}）或把 direction 设为 BOTH 再试。"
            )

        lines = [
            f"查询结果：从「{start_entity}」到「{end_entity}」共找到 {len(paths_records)} 条因果路径 "
            f"（{max_hops} 跳以内，按跳数升序、置信度乘积降序）：",
            "-" * 40,
        ]
        for idx, p in enumerate(paths_records, 1):
            nodes = p["nodes"]
            edges = p["edges"]
            dirs = p["dirs"]
            confs = p["confs"]
            hops = p["hops"]
            conf_prod = 1.0
            for c in confs:
                if isinstance(c, (int, float)) and c >= 0:
                    conf_prod *= float(c)
            # 组装一条路径的可读表示
            parts: list[str] = []
            for i, n in enumerate(nodes):
                parts.append(f"「{n}」")
                if i < len(edges):
                    d = dirs[i] if i < len(dirs) else "FORWARD"
                    arrow = "==>" if d == "FORWARD" else "-¤-"   # ¤ 表示阻断/预防
                    label = edges[i] if i < len(edges) else d
                    parts.append(f"—[{label}]—{arrow}")
            lines.append(
                f"路径{idx}（{hops}跳，综合置信 {conf_prod:.2f}）：\n  " + " ".join(parts)
            )
        return "\n".join(lines)

    # ====================================================================
    # 场景 B：未指定 end_entity → 从 start 向外辐射的多跳因果邻居（BFS 层序）
    # ====================================================================
    # 先确认起点存在
    exist = _query(
        """
        MATCH (s:Entity {modelId: $mid})
        WHERE s.canonicalName = $start OR s.name = $start
        RETURN count(s) AS cnt
        """,
        mid=model_id, start=start_entity,
    )
    if not exist or exist[0]["cnt"] == 0:
        return f"未找到起始实体「{start_entity}」，请先通过 search_entities 确认名称。"

    # 查 max_hops 内所有因果路径，按层级聚合展示
    tree_records = _query(
        f"""
        MATCH path = (s:Entity {{modelId: $mid}})-[r:CAUSES *..{max_hops}]->(t:Entity {{modelId: $mid}})
        WHERE (s.canonicalName = $start OR s.name = $start)
          AND ALL(rel IN relationships(path) WHERE NOT coalesce(rel.isBackEdge, false){dir_filter.replace('AND r.direction', ' AND rel.direction')})
        WITH DISTINCT t, length(path) AS hops
        ORDER BY hops ASC, t.name ASC
        RETURN hops,
               collect(DISTINCT coalesce(t.canonicalName, t.name)) AS neighbors,
               count(DISTINCT t) AS cnt
        ORDER BY hops ASC
        """,
        mid=model_id, start=start_entity,
    )

    # 同时把每条路径的首跳（最常用的直接因果）详细列出来
    first_hop = _query(
        f"""
        MATCH (s:Entity {{modelId: $mid}})-[r:CAUSES]->(t:Entity {{modelId: $mid}})
        WHERE (s.canonicalName = $start OR s.name = $start)
          AND NOT coalesce(r.isBackEdge, false){dir_filter}
        RETURN coalesce(r.type, r.signalWord, r.direction) AS edge,
               coalesce(r.direction, 'FORWARD')               AS dir,
               coalesce(r.confidence, -1.0)                   AS conf,
               coalesce(t.canonicalName, t.name)              AS target,
               t.type                                         AS ttype
        ORDER BY conf DESC, target ASC
        LIMIT $lim
        """,
        mid=model_id, start=start_entity, lim=max(20, limit_paths),
    )

    lines = [f"「{start_entity}」的因果辐射链（{max_hops} 跳以内，direction={direction}）："]

    if first_hop:
        lines.append("")
        lines.append("【第 1 跳 · 直接因果邻居】（按置信度降序，最多展示 20 条）：")
        for r in first_hop:
            d = r.get("dir", "FORWARD")
            arrow = "导致 →" if d == "FORWARD" else "预防 ⊣"
            conf = r.get("conf")
            conf_str = f"（置信 {conf:.2f}）" if isinstance(conf, (int, float)) and conf >= 0 else ""
            ttype = f" [{r.get('ttype') or '未分类'}]" if r.get("ttype") else ""
            lines.append(
                f"  · {start_entity}  —[{r.get('edge', d)}]— {arrow}  {r.get('target', '')}{ttype}  {conf_str}"
            )

    if tree_records:
        lines.append("")
        lines.append("【按跳数汇总的可达节点】：")
        total_reachable = 0
        for row in tree_records:
            h = row["hops"]
            cnt = row["cnt"]
            total_reachable += int(cnt or 0)
            neighbors = row["neighbors"] or []
            # 节点太多就截断展示前 10 个，提示还有多少
            shown = neighbors[:10]
            more = len(neighbors) - len(shown)
            shown_str = "、".join(f"「{n}」" for n in shown)
            more_str = f" …等 {cnt} 个节点" if more > 0 else f" 共 {cnt} 个节点"
            lines.append(f"  · 第 {h} 跳：{shown_str}{more_str}")
        lines.append("")
        lines.append(f"合计：{max_hops} 跳以内共可达 {total_reachable} 个不同实体。")
    else:
        lines.append("")
        lines.append("未找到任何因果邻居：该节点可能还没有 [:CAUSES] 类型的因果边。")

    return "\n".join(lines)


# 全部工具列表
ALL_TOOLS = [
    search_entities,
    get_entity_detail,
    get_entities_by_name,
    get_entity_relations,
    get_graph_stats,
    list_entity_types,
    get_entities_by_type,
    get_causal_chain,
]
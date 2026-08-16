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
    """获取指定实体的所有关系（作为头实体或尾实体）。返回关系类型及关联实体。"""
    out_records = _query(
        """
        MATCH (a:Entity {name: $name, modelId: $modelId})-[r:RELATION]->(b:Entity {modelId: $modelId})
        RETURN a.name AS head, r.type AS relation, b.name AS tail
        LIMIT $limit
        """,
        modelId=model_id,
        name=name,
        limit=limit,
    )
    in_records = _query(
        """
        MATCH (a:Entity {modelId: $modelId})-[r:RELATION]->(b:Entity {name: $name, modelId: $modelId})
        RETURN a.name AS head, r.type AS relation, b.name AS tail
        LIMIT $limit
        """,
        modelId=model_id,
        name=name,
        limit=limit,
    )

    lines = []
    if out_records:
        lines.append(f"「{name}」作为头实体的关系:")
        for r in out_records:
            lines.append(f"  - {r['head']} --[{r['relation']}]--> {r['tail']}")
    if in_records:
        lines.append(f"「{name}」作为尾实体的关系:")
        for r in in_records:
            lines.append(f"  - {r['head']} --[{r['relation']}]--> {r['tail']}")
    if not lines:
        return f"「{name}」暂无关系。"
    return "\n".join(lines)


@tool
def get_graph_stats(model_id: int) -> str:
    """获取当前图谱模型的统计信息：节点总数、关系总数、实体类型分布。"""
    node_count = _query(
        "MATCH (n:Entity {modelId: $modelId}) RETURN count(n) AS cnt",
        modelId=model_id,
    )
    rel_count = _query(
        "MATCH ()-[r:RELATION {modelId: $modelId}]->() RETURN count(r) AS cnt",
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

    lines = [
        f"图谱统计: 实体总数 {total_nodes}, 关系总数 {total_rels}",
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


# 全部工具列表
ALL_TOOLS = [
    search_entities,
    get_entity_detail,
    get_entity_relations,
    get_graph_stats,
    list_entity_types,
    get_entities_by_type,
]
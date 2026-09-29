"""图谱最短路径检索核心（BFS / shortestPath）。

核心检索逻辑无 FastAPI 依赖（对齐 evaluation_core.py 的"核心下沉"模式），
api 层（api/graph_path.py）与未来的 MCP 工具 / Agent 工具复用同一实现，零漂移。

设计要点：
- 检索委托 Neo4j 原生 shortestPath（数据库内核双向 BFS），按 modelId 隔离
- 无向遍历：KG 关系有向，但路径探索语义按"实体间可达"理解
- 返回结构对齐 Java /explore/nodes 的节点/边格式，前端可直接复用 transform 逻辑
"""
from __future__ import annotations

from typing import Any, Dict, List

from neo4j import GraphDatabase

MAX_HOPS_LIMIT = 20
DEFAULT_MAX_HOPS = 15


class _GraphPathContext:
    """持有 Neo4j driver。

    与 agent_tools 解耦（后者 import langchain），保证本模块可被 MCP Server
    等轻量进程复用而不引入额外依赖。
    """

    driver: Any = None

    @classmethod
    def init(cls, config: Dict[str, Any]) -> None:
        if cls.driver is not None:
            return
        neo4j_cfg = config.get("neo4j", {})
        cls.driver = GraphDatabase.driver(
            neo4j_cfg.get("url"),
            auth=(neo4j_cfg.get("username"), neo4j_cfg.get("password")),
        )

    @classmethod
    def close(cls) -> None:
        if cls.driver:
            cls.driver.close()
            cls.driver = None


def _run(cypher: str, **params) -> List[Dict[str, Any]]:
    with _GraphPathContext.driver.session() as session:
        result = session.run(cypher, **params)
        return [dict(record) for record in result]


def _clamp_max_hops(max_hops: Any) -> int:
    try:
        hops = int(max_hops)
    except (TypeError, ValueError):
        hops = DEFAULT_MAX_HOPS
    return max(1, min(hops, MAX_HOPS_LIMIT))


def _node_to_map(node: Any) -> Dict[str, Any]:
    """对齐 Java Neo4jService.nodeToMap：全部属性 + elementId + labels。"""
    m = dict(node)
    m["elementId"] = node.element_id
    m["labels"] = list(node.labels)
    return m


def _edge_to_map(rel: Any) -> Dict[str, Any]:
    """对齐 Java Neo4jService.buildEdge：source/target 为端点 elementId，label 取关系属性 type。"""
    props = dict(rel)
    # 实际关系名称存在 rel 的 type 属性里（graph_writer 写入），Neo4j 关系类型是通用值
    label = props.get("type") or rel.type
    return {
        "source": rel.start_node.element_id,
        "target": rel.end_node.element_id,
        "label": label,
        "data": {
            **props,
            "elementId": rel.element_id,
            "relationType": rel.type,
            "startNodeElementId": rel.start_node.element_id,
            "endNodeElementId": rel.end_node.element_id,
        },
    }


def find_shortest_path(
    model_id: int, from_id: str, to_id: str, max_hops: int = DEFAULT_MAX_HOPS
) -> Dict[str, Any]:
    """检索 from → to 的最短路径（无向 BFS，按 modelId 隔离）。

    返回 {found, hops, nodes(按路径顺序), edges(按路径顺序)}，
    found=False 时附带 reason（端点不存在 / 不连通）。
    """
    if not from_id or not to_id:
        return {"found": False, "reason": "起点或目标不能为空"}
    if not model_id or int(model_id) <= 0:
        return {"found": False, "reason": "modelId 无效"}

    hops_limit = _clamp_max_hops(max_hops)
    model_id = int(model_id)

    # 起点即目标：直接返回单节点路径
    if from_id == to_id:
        records = _run(
            "MATCH (a:Entity {modelId: $modelId}) WHERE elementId(a) = $fromId RETURN a",
            modelId=model_id,
            fromId=from_id,
        )
        if not records:
            return {"found": False, "reason": "起点或目标节点不存在"}
        return {"found": True, "hops": 0, "nodes": [_node_to_map(records[0]["a"])], "edges": []}

    # 变长路径上界须字面量（Neo4j 限制），hops_limit 已 clamp 为 1..20 的安全整数
    cypher = (
        "MATCH (a:Entity {modelId: $modelId}), (b:Entity {modelId: $modelId}) "
        "WHERE elementId(a) = $fromId AND elementId(b) = $toId "
        f"MATCH p = shortestPath((a)-[*..{hops_limit}]-(b)) "
        "RETURN p"
    )
    records = _run(cypher, modelId=model_id, fromId=from_id, toId=to_id)
    if not records:
        # 区分"端点不存在"与"不连通"，给前端准确提示
        exists = _run(
            "MATCH (n:Entity {modelId: $modelId}) WHERE elementId(n) IN [$fromId, $toId] "
            "RETURN count(n) AS c",
            modelId=model_id,
            fromId=from_id,
            toId=to_id,
        )
        count = exists[0]["c"] if exists else 0
        reason = "起点或目标节点不存在" if count < 2 else "两节点间不存在可达路径"
        return {"found": False, "reason": reason}

    path = records[0]["p"]
    nodes = [_node_to_map(n) for n in path.nodes]
    edges = [_edge_to_map(r) for r in path.relationships]
    return {"found": True, "hops": len(edges), "nodes": nodes, "edges": edges}

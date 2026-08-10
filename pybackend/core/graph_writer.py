import json
from typing import Any, Dict, List

from neo4j import GraphDatabase


def _sanitize_properties(props: Any) -> Dict[str, Any]:
    """过滤属性值，只保留 Neo4j 支持的基本类型（string/int/float/bool）及其列表。"""
    if not isinstance(props, dict):
        return {}
    result: Dict[str, Any] = {}
    for k, v in props.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            result[k] = v
        elif isinstance(v, list) and all(isinstance(i, (str, int, float, bool)) for i in v):
            result[k] = v
        elif isinstance(v, (dict, list)):
            # 嵌套结构序列化为 JSON 字符串
            result[k] = json.dumps(v, ensure_ascii=False)
    return result


class GraphWriter:
    """Neo4j 图写入器。使用 config.json 中的 neo4j 配置连接。"""

    def __init__(self, config: Dict[str, Any]):
        neo4j_cfg = config.get("neo4j", {})
        self.driver = GraphDatabase.driver(
            neo4j_cfg.get("url"),
            auth=(neo4j_cfg.get("username"), neo4j_cfg.get("password")),
        )

    def close(self) -> None:
        self.driver.close()

    def write(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        model_id: int,
    ) -> Dict[str, int]:
        """写入实体与关系到 Neo4j，节点/关系均带 modelId 隔离。使用 MERGE 避免重复。"""
        entity_count = 0
        relation_count = 0

        with self.driver.session() as session:
            # 写入实体
            for e in entities:
                props = _sanitize_properties(e.get("properties", {}))
                session.run(
                    """
                    MERGE (n:Entity {name: $name, type: $type, modelId: $modelId})
                    SET n += $properties,
                        n.createTime = timestamp()
                    """,
                    name=e.get("name"),
                    type=e.get("type"),
                    modelId=model_id,
                    properties=props,
                )
                entity_count += 1

            # 写入关系
            for r in relations:
                props = _sanitize_properties(r.get("properties", {}))
                session.run(
                    """
                    MATCH (a:Entity {name: $head, modelId: $modelId}),
                          (b:Entity {name: $tail, modelId: $modelId})
                    MERGE (a)-[rel:RELATION {type: $relationType, modelId: $modelId}]->(b)
                    SET rel += $properties,
                        rel.createTime = timestamp()
                    """,
                    head=r.get("head"),
                    tail=r.get("tail"),
                    relationType=r.get("relation"),
                    modelId=model_id,
                    properties=props,
                )
                relation_count += 1

        return {"entities": entity_count, "relations": relation_count}

import json
from typing import Any, Dict, List, Tuple

from neo4j import GraphDatabase

from core.extraction_schema import (
    CONF_CAUSAL_KEEP,
    CONF_RELATION_KEEP,
    EvidenceSpan,
    LlmExtractionPayload,
)


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
            result[k] = json.dumps(v, ensure_ascii=False)
    return result


def _span_list(evidence: List[EvidenceSpan]) -> List[str]:
    """把 EvidenceSpan 列表序列化成 ['s1,e1','s2,e2',...]，Neo4j 原生支持字符串列表。"""
    return [f"{s.start},{s.end}" for s in evidence or []]


def _entity_extra_label(etype: str) -> str:
    """按实体类型附加一个额外的 Neo4j label，便于前端按类型筛选。"""
    if not etype:
        return ""
    # 去掉所有非字母数字中文字符，拼一个合法 label
    chars = []
    for c in etype:
        if c.isalnum() or ("\u4e00" <= c <= "\u9fff"):
            chars.append(c)
    label = "".join(chars).strip()
    return label or ""


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

    # ------------------------------------------------------------------------
    # 旧接口：兼容 KOS / DL / 结构化抽取（完全不动，保持 MERGE 语义）
    # ------------------------------------------------------------------------
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

    # ------------------------------------------------------------------------
    # 新接口：基于 LLM 抽取结果的双时态 + 因果写入（借鉴 Semantica A-Box 分层）
    #   - 实体：MERGE（canonicalName + type + modelId 唯一），追加 mentions/spans 到列表属性
    #   - 关系：CREATE（**不再 MERGE 关系**），避免覆盖掉前任期时态版本
    #           写库时带上 vt / evidence / confidence 全部字段
    #   - 因果：CREATE [:CAUSES]，独立关系类型，不混在普通 RELATION
    # ------------------------------------------------------------------------
    def write_llm_extracted(
        self,
        payload: LlmExtractionPayload,
        model_id: int,
        doc_id: str | None = None,
    ) -> Dict[str, Any]:
        """写入 LLM 抽取 payload 到 Neo4j。返回写入计数 + 缺失节点列表。"""
        counts = {"entities": 0, "timeAnchors": 0, "relations": 0, "causalEdges": 0,
                  "missing_nodes_created": 0}

        VALID_ANCHOR_TYPES = {"DATE", "DATERANGE", "RELATIVE", "NOW", "OPEN", "UNKNOWN"}
        with self.driver.session() as session:
            # 1) 实体写入（MERGE，记录所有 mentions + spans 列表，便于后续证据查询）
            for e in payload.entities:
                # L0 兜底：核心字段为空直接跳过（上游 Pydantic 应该已经拦了，但做双保险避免造空节点）
                if (not e.canonicalName or not e.canonicalName.strip()
                        or not e.type or not e.type.strip()
                        or not e.mention or not e.mention.strip()):
                    continue
                extra_label = _entity_extra_label(e.type)
                label_clause = f":{extra_label}" if extra_label else ""
                span_str = f"{e.span.start},{e.span.end}"
                session.run(
                    f"""
                    MERGE (n:Entity{label_clause} {{canonicalName: $canonicalName,
                                                      type: $type,
                                                      modelId: $modelId}})
                    ON CREATE SET n.name = $canonicalName,
                                  n.source = 'llm_extract',
                                  n.kosCategory = coalesce($kosCategory, n.kosCategory),
                                  n.mentions = coalesce(n.mentions, []) + CASE
                                      WHEN $mention IN coalesce(n.mentions, []) THEN []
                                      ELSE [$mention] END,
                                  n.mentionSpans = coalesce(n.mentionSpans, []) + CASE
                                      WHEN $span IN coalesce(n.mentionSpans, []) THEN []
                                      ELSE [$span] END,
                                  n.updateTime = timestamp(),
                                  n.createTime = timestamp()
                    ON MATCH SET n.name = $canonicalName,
                                 n.source = 'llm_extract',
                                 n.kosCategory = coalesce($kosCategory, n.kosCategory),
                                 n.mentions = coalesce(n.mentions, []) + CASE
                                     WHEN $mention IN coalesce(n.mentions, []) THEN []
                                     ELSE [$mention] END,
                                 n.mentionSpans = coalesce(n.mentionSpans, []) + CASE
                                     WHEN $span IN coalesce(n.mentionSpans, []) THEN []
                                     ELSE [$span] END,
                                 n.updateTime = timestamp()
                    """,
                    canonicalName=e.canonicalName,
                    type=e.type,
                    modelId=model_id,
                    kosCategory=e.kosCategory,
                    mention=e.mention,
                    span=span_str,
                )
                counts["entities"] += 1

            # 2) 时间锚点写入（独立 TimeAnchor 节点，挂在对应实体附近；也作为可查询的一等公民）
            for a in payload.timeAnchors:
                # L0 兜底：expr 为空 / 类型非法 / RELATIVE 类型但无解析结果 → 跳过（避免造孤立点）
                if (not a.expr or not a.expr.strip()
                        or a.type not in VALID_ANCHOR_TYPES):
                    continue
                if a.type == "RELATIVE":
                    has_norm = bool(a.normISO and a.normISO.strip())
                    has_rel = bool(a.relativeAnchor and a.relativeAnchor.strip())
                    if not (has_norm or has_rel):
                        continue
                span_str = f"{a.span.start},{a.span.end}"
                session.run(
                    """
                    CREATE (:TimeAnchor {
                        expr: $expr, type: $type, normISO: $normISO,
                        precision: $precision, relativeAnchor: $relativeAnchor,
                        mentionSpan: $span,
                        docId: coalesce($docId, ''),
                        modelId: $modelId, createTime: timestamp()
                    })
                    """,
                    expr=a.expr, type=a.type, normISO=a.normISO or "",
                    precision=a.precision,
                    relativeAnchor=a.relativeAnchor or "",
                    span=span_str, docId=doc_id, modelId=model_id,
                )
                counts["timeAnchors"] += 1

            # 辅助：确保某个 canonicalName 节点存在；若 T2 因果两端引用了 T1 没覆盖的新实体，
            # 就自动补占位节点，type 写 "未分类实体/事件"，后续审核人员可以在前端补类型
            def ensure_node(session_obj, cname: str, ctype: str | None) -> None:
                if not cname:
                    return
                final_type = (ctype or "").strip() or "未分类实体"
                extra_label = _entity_extra_label(final_type)
                label_clause = f":{extra_label}" if extra_label else ""
                result = session_obj.run(
                    f"""
                    MERGE (n:Entity{label_clause} {{canonicalName: $cname, type: $ctype, modelId: $modelId}})
                    ON CREATE SET n.name = $cname, n.source = 'llm_extract:auto_placeholder',
                                  n.createTime = timestamp(), n.updateTime = timestamp(),
                                  n.autoCreated = true
                    ON MATCH  SET n.updateTime = timestamp()
                    RETURN n.autoCreated as autoCreated
                    """,
                    cname=cname, ctype=final_type, modelId=model_id,
                ).single()
                if result and result.get("autoCreated") is True:
                    counts["missing_nodes_created"] += 1

            # 3) 关系写入（CREATE，永不覆盖；同一条多次抽会存多个时态版本——这是 Semantica 双时态的核心）
            for r in payload.relations:
                ensure_node(session, r.subject, r.subjectType)
                ensure_node(session, r.object, r.objectType)
                low_conf = r.confidence < CONF_RELATION_KEEP
                evidence = _span_list(r.evidenceSpans)
                session.run(
                    """
                    MATCH (s:Entity {canonicalName: $s_cname, modelId: $modelId}),
                          (o:Entity {canonicalName: $o_cname, modelId: $modelId})
                    CREATE (s)-[r:RELATION {
                        predicate: $predicate,
                        type: $predicate,
                        modelId: $modelId,
                        source: 'llm_extract',
                        subjectType: coalesce($st, ''),
                        objectType: coalesce($ot, ''),
                        vt_from: coalesce($vf, ''),
                        vt_to: coalesce($vt, ''),
                        vt_precision_from: coalesce($vpf, 'unknown'),
                        vt_precision_to: coalesce($vpt, 'unknown'),
                        confidence: $conf,
                        lowConfidence: $lowConf,
                        evidence: $evidence,
                        docId: coalesce($docId, ''),
                        createTime: timestamp()
                    }]->(o)
                    """,
                    s_cname=r.subject, o_cname=r.object,
                    predicate=r.predicate,
                    st=r.subjectType, ot=r.objectType,
                    vf=r.vt_from, vt=r.vt_to,
                    vpf=r.vt_precision_from, vpt=r.vt_precision_to,
                    conf=float(r.confidence),
                    lowConf=low_conf,
                    evidence=evidence,
                    docId=doc_id,
                    modelId=model_id,
                )
                counts["relations"] += 1

            # 4) 因果边写入（独立关系类型 [:CAUSES]，direction 决定 FORWARD/PREVENT）
            #    关键：额外写一个 "type" 属性，值 = signalWord或中文默认，
            #    保证 Java 端 buildEdge() 优先读 r.type 时，图谱上显示中文边标签而非 "CAUSES" 英文
            for c in payload.causalEdges:
                ensure_node(session, c.causeEvent, c.causeType or "事件")
                ensure_node(session, c.effectEvent, c.effectType or "事件")
                low_conf = c.confidence < CONF_CAUSAL_KEEP
                evidence = _span_list(c.evidenceSpans)
                # type属性 = 优先使用信号词，缺失则用中文默认
                default_label = "导致" if c.direction == "FORWARD" else "预防/缓解"
                display_type = (c.signalWord or "").strip() or default_label
                session.run(
                    """
                    MATCH (ca:Entity {canonicalName: $ca_cname, modelId: $modelId}),
                          (cb:Entity {canonicalName: $cb_cname, modelId: $modelId})
                    CREATE (ca)-[c:CAUSES {
                        type: $display_type,
                        direction: $direction,
                        modelId: $modelId,
                        source: 'llm_extract',
                        causeType: coalesce($ct, ''),
                        effectType: coalesce($et, ''),
                        signalWord: coalesce($sig, ''),
                        vt_order: coalesce($vto, 'UNKNOWN'),
                        confidence: $conf,
                        lowConfidence: $lowConf,
                        evidence: $evidence,
                        docId: coalesce($docId, ''),
                        createTime: timestamp()
                    }]->(cb)
                    """,
                    ca_cname=c.causeEvent, cb_cname=c.effectEvent,
                    display_type=display_type,
                    direction=c.direction,
                    ct=c.causeType, et=c.effectType,
                    sig=c.signalWord, vto=c.vt_order or "UNKNOWN",
                    conf=float(c.confidence),
                    lowConf=low_conf,
                    evidence=evidence,
                    docId=doc_id,
                    modelId=model_id,
                )
                counts["causalEdges"] += 1

        return counts

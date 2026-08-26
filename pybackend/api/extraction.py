"""基于 LLM 的知识抽取端点（Semantica 式两阶段流水线 · 2026-08-23 重构）。

流程（2 次 LLM 调用）：
  阶段1 节点抽取：静态实体 + 事件实体 + 指代消解链 + 时间锚点（不含关系）
  阶段2 关系抽取：注入阶段1 实体表硬约束，主语/宾语必须命中实体表；
                  每条关系附证据句原文（evidenceText）
  代码校验层（0 次 LLM）：
    · mention / expr / evidenceText 回原文 find() 定位生成 span（LLM 不再输出数字偏移）
    · 事件 type 归一化（统一为「事件」，语义靠 canonicalName 描述）
    · 关系主语/宾语引用检查（未命中实体表 → 丢弃记 WARNING）
    · subjectType/objectType 从实体表反查、vt_precision 从 ISO 格式推断
  入库：graph_writer.write_llm_extracted（实体 MERGE / 关系 CREATE / 锚点 CREATE）

因果边（causalEdges）不做 LLM 抽取：等图谱构建完成后走图上离线推理。
LLM / KOS / DL / 结构化是四种完全独立的抽取方法，本模块只负责 LLM 抽取。
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Request

from core.extraction_schema import (
    EvidenceSpan,
    ExtractedEntity,
    ExtractedRelation,
    LlmExtractionPayload,
    TimeAnchor,
)
from core.extraction_validator import (
    QualityReport,
    run_quality_pipeline,
)
from core.graph_writer import GraphWriter
from core.llm_client import LLMClient
from core.prompt_builder import (
    build_node_messages,
    build_relation_messages,
    format_entity_table,
)
from models.schemas import ExtractionRequest, ExtractionResult

router = APIRouter()

# 合法锚点类型（与 graph_writer 保持一致）
_VALID_ANCHOR_TYPES = {"DATE", "DATERANGE", "RELATIVE", "NOW", "OPEN", "UNKNOWN"}
_VALID_STATUS = {"CURRENT", "EXPIRED", "NEGATED"}


# ============================================================================
# JSON 解析（兼容 markdown 代码块包裹；解析失败带原因重试 1 次）
# ============================================================================
def _extract_json(content: str) -> Dict[str, Any]:
    """从 LLM 返回内容中解析 JSON，兼容 markdown 代码块包裹。"""
    text = content.strip()

    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    else:
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"无法解析 LLM 返回的 JSON: {content[:300]}")


def _llm_call_with_retry(
    llm_client: LLMClient, messages: List[Dict[str, str]], last_error: str | None = None
) -> Tuple[Dict[str, Any], int]:
    """一次 LLM 调用（JSON 模式）+ 解析；失败把原因带回重试 1 次。"""
    try:
        content, tokens = llm_client.chat(messages, force_json=True)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {e}")
    try:
        return _extract_json(content), tokens
    except ValueError as first_err:
        retry_messages = [*messages]
        extra_note = (
            f"\n\n【重要提示】上一次解析失败，原因：{last_error or str(first_err)}。"
            "请你严格只输出一段符合 Schema 的 JSON，不要解释、不要代码块包裹之外的内容。"
        )
        retry_messages[-1] = {
            "role": retry_messages[-1]["role"],
            "content": retry_messages[-1]["content"] + extra_note,
        }
        try:
            content2, tokens2 = llm_client.chat(retry_messages, force_json=True)
            return _extract_json(content2), tokens + tokens2
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"LLM 返回 JSON 解析重试失败: first={first_err} second={e}",
            )


# ============================================================================
# 代码校验层工具
# ============================================================================
def _locate_span(text: str, needle: str) -> Optional[EvidenceSpan]:
    """在原文中定位子串，返回闭区间 span；找不到返回 None。"""
    if not needle:
        return None
    idx = text.find(needle)
    if idx < 0:
        return None
    return EvidenceSpan(start=idx, end=idx + len(needle) - 1)


def _normalize_event_type(etype: str, rep: QualityReport, name: str) -> str:
    """事件 type 归一化：统一为「事件」。

    设计简化（2026-08-23）：事件不再细分三级 type 枚举，语义全靠 canonicalName 描述。
    LLM 若仍输出「事件-xx-xx」「金融事件」等变体，此处一律归一为「事件」，
    保证 Agent 端 type 检索恒可命中。
    """
    t = (etype or "").strip()
    if t == "事件":
        return t
    if "事件" in t:
        rep.add("WARNING", "NODE_EVENT_TYPE_COERCED",
                f"事件实体 '{name}' type='{t}' 已归一化为「事件」")
        return "事件"
    return t


def _infer_precision(iso: Optional[str]) -> str:
    """从 ISO 字符串长度推断时间精度：10=day / 7=month / 4=year。"""
    if not iso:
        return "unknown"
    s = iso.strip()
    if len(s) >= 10:
        return "day"
    if len(s) == 7:
        return "month"
    if len(s) == 4:
        return "year"
    return "unknown"


# ============================================================================
# 阶段1 解析：节点 JSON → Pydantic 实体/锚点 + 别名映射表
# ============================================================================
def _parse_nodes(
    node_json: Dict[str, Any], text: str, rep: QualityReport
) -> Tuple[List[ExtractedEntity], List[TimeAnchor], Dict[str, str], Optional[str]]:
    """返回 (entities, timeAnchors, alias_map, docTime)。

    alias_map: 指代词 → 规范实体名（阶段2 关系引用解析用，指代词本身不建节点）
    """
    alias_map: Dict[str, str] = {}

    # ---- 实体 ----
    name_set: Dict[str, str] = {}  # canonicalName -> type（关系阶段反查用）
    entities: List[ExtractedEntity] = []
    for e in node_json.get("entities") or []:
        if not isinstance(e, dict):
            continue
        mention = str(e.get("mention") or "").strip()
        canonical = str(e.get("canonicalName") or "").strip()
        etype = str(e.get("type") or "").strip()
        if not canonical or not etype:
            rep.add("WARNING", "NODE_ENTITY_DIRTY_DROPPED",
                    f"实体核心字段为空已丢弃: {str(e)[:80]}")
            continue
        if not mention:
            mention = canonical
        etype = _normalize_event_type(etype, rep, canonical)
        # span 由代码回原文定位（LLM 不输出数字偏移）
        span = _locate_span(text, mention)
        if span is None:
            span = _locate_span(text, canonical)
        if span is None:
            rep.add("WARNING", "NODE_ENTITY_SPAN_MISS",
                    f"实体 '{canonical}' 的 mention 未在原文中定位到，span 置为 (0,0)")
            span = EvidenceSpan(start=0, end=0)
        if canonical not in name_set:
            name_set[canonical] = etype
            entities.append(ExtractedEntity(
                mention=mention, canonicalName=canonical, type=etype, span=span,
            ))

    # ---- 指代消解链（别名并入映射表，不建独立节点）----
    for c in node_json.get("coreferenceChains") or []:
        if not isinstance(c, dict):
            continue
        canonical = str(c.get("canonicalName") or "").strip()
        if canonical not in name_set:
            continue  # 指向不存在的实体，丢弃
        for a in c.get("aliases") or []:
            alias = str(a or "").strip()
            if alias and alias != canonical and alias not in name_set:
                alias_map[alias] = canonical

    # ---- 时间锚点 ----
    anchors: List[TimeAnchor] = []
    for a in node_json.get("timeAnchors") or []:
        if not isinstance(a, dict):
            continue
        expr = str(a.get("expr") or "").strip()
        if not expr:
            continue
        atype = str(a.get("type") or "UNKNOWN").strip().upper()
        if atype not in _VALID_ANCHOR_TYPES:
            atype = "UNKNOWN"
        if atype == "RELATIVE":
            has_norm = bool(str(a.get("normISO") or "").strip())
            has_rel = bool(str(a.get("relativeAnchor") or "").strip())
            if not (has_norm or has_rel):
                rep.add("WARNING", "NODE_ANCHOR_RELATIVE_EMPTY_DROPPED",
                        f"RELATIVE 锚点 '{expr}' 无 normISO 且无 relativeAnchor，已丢弃")
                continue
        span = _locate_span(text, expr)
        if span is None:
            rep.add("WARNING", "NODE_ANCHOR_SPAN_MISS",
                    f"锚点 '{expr}' 未在原文中定位到，span 置为 (0,0)")
            span = EvidenceSpan(start=0, end=0)
        anchors.append(TimeAnchor(
            expr=expr, type=atype,
            normISO=str(a.get("normISO") or "").strip() or None,
            precision=str(a.get("precision") or "unknown").strip() or "unknown",
            relativeAnchor=str(a.get("relativeAnchor") or "").strip() or None,
            span=span,
        ))

    doc_time = str(node_json.get("docTime") or "").strip() or None
    return entities, anchors, alias_map, doc_time


# ============================================================================
# 阶段2 解析：关系 JSON → Pydantic 关系（引用校验 + 证据句定位）
# ============================================================================
def _parse_relations(
    rel_json: Dict[str, Any], text: str,
    name_set: Dict[str, str], alias_map: Dict[str, str],
    rep: QualityReport,
) -> List[ExtractedRelation]:
    """主语/宾语引用解析（允许实体表外名称 → 后处理 ensure_node 会补占位节点）。

    解析顺序：
      1. 精确命中 name_set
      2. alias_map 别名映射（阶段1 coreferenceChains 产生）
      3. 【新增】名称包含 + 类型匹配（如「省疾控中心」 ⊆ 「广东省疾病预防控制中心」，且 type=组织/疾控中心）
      4. 【新增】字符串相似度 ≥ 0.80 的近邻命中（错别字/遗漏字容错）
      5. 完全没命中 → 仍然保留（允许 create placeholder，不 DROP 关系）
    证据句必须能在原文中定位（否则丢弃——没有证据的关系不可信）。
    """
    relations: List[ExtractedRelation] = []

    def _jaccard_sim(a: str, b: str) -> float:
        sa, sb = set(a), set(b)
        return len(sa & sb) / max(1, len(sa | sb))

    def _resolve(name: str) -> Optional[Tuple[str, Optional[str]]]:
        """返回 (规范实体名, 已知类型或None)。没命中实体表时类型返回None，后续占位节点。"""
        n = (name or "").strip()
        if not n:
            return None
        # 1) 精确
        if n in name_set:
            return n, name_set[n]
        # 2) 别名映射
        mapped = alias_map.get(n)
        if mapped and mapped in name_set:
            return mapped, name_set[mapped]
        # 3) 名称包含（优先同类型 -> 更长的 canonicalName 命中）
        best_match = None
        best_len = 0
        for canon, ctype in name_set.items():
            if n in canon or canon in n:
                if len(canon) > best_len:
                    best_match = (canon, ctype)
                    best_len = len(canon)
        if best_match:
            rep.add("WARNING", "REL_NAME_SUBSTRING_MATCHED",
                    f"关系引用 '{n}' 名称包含匹配到 canonical='{best_match[0]}' (type={best_match[1]})")
            return best_match
        # 4) 近邻 Jaccard 字符合集 ≥ 0.80
        best_sim = 0.0
        best_neighbor = None
        for canon, ctype in name_set.items():
            sim = _jaccard_sim(n, canon)
            if sim >= 0.80 and sim > best_sim:
                best_sim = sim
                best_neighbor = (canon, ctype)
        if best_neighbor:
            rep.add("WARNING", "REL_NAME_JACCARD_MATCHED",
                    f"关系引用 '{n}' Jaccard≈{best_sim:.2f} 匹配到 canonical='{best_neighbor[0]}'")
            return best_neighbor
        # 5) 完全没命中 → 允许，类型返回 None（占位节点 未分类实体）
        return n, None

    seen_triples: Dict[Tuple[str, str, str], int] = {}  # 三元组key → relations下标

    for r in rel_json.get("relations") or []:
        if not isinstance(r, dict):
            continue
        subj_resolved = _resolve(str(r.get("subject") or ""))
        obj_resolved = _resolve(str(r.get("object") or ""))
        pred = str(r.get("predicate") or "").strip()
        if not subj_resolved or not obj_resolved or not pred:
            rep.add("WARNING", "REL_EMPTY_FIELD_DROPPED",
                    f"关系主谓宾有空字段已丢弃: {r.get('subject')} -[{pred}]-> {r.get('object')}")
            continue
        subj, subj_type_hint = subj_resolved
        obj, obj_type_hint = obj_resolved
        if subj == obj:
            rep.add("WARNING", "REL_SELF_LOOP_DROPPED",
                    f"自环关系已丢弃: {subj} -[{pred}]-> {obj}")
            continue

        # 证据句必须能在原文中定位（关系无证据不可信 → 丢弃）
        evidence = str(r.get("evidenceText") or "").strip()
        ev_span = _locate_span(text, evidence) if evidence else None
        if ev_span is None:
            rep.add("WARNING", "REL_EVIDENCE_MISS_DROPPED",
                    f"关系证据句未在原文中定位到已丢弃: {subj} -[{pred}]-> {obj}")
            continue

        status = str(r.get("status") or "CURRENT").strip().upper()
        if status not in _VALID_STATUS:
            status = "CURRENT"
        conf = r.get("confidence")
        conf = float(conf) if isinstance(conf, (int, float)) else 0.8
        conf = max(0.0, min(1.0, conf))

        vt_from = str(r.get("vt_from") or "").strip() or None
        vt_to = str(r.get("vt_to") or "").strip() or None

        # ========== 三元组去重（subj/pred/obj 全同取最大置信度保留一条）==========
        dedup_key = (subj, pred, obj)
        if dedup_key in seen_triples:
            idx = seen_triples[dedup_key]
            if conf > relations[idx].confidence:
                # 替换为更高置信度的那条，保留更多信息
                relations[idx] = ExtractedRelation(
                    subject=subj, predicate=pred, object=obj,
                    subjectType=subj_type_hint or relations[idx].subjectType,
                    objectType=obj_type_hint or relations[idx].objectType,
                    vt_from=vt_from or relations[idx].vt_from,
                    vt_to=vt_to or relations[idx].vt_to,
                    vt_precision_from=_infer_precision(vt_from or relations[idx].vt_from),
                    vt_precision_to=_infer_precision(vt_to or relations[idx].vt_to),
                    status=status, confidence=conf,
                    evidenceSpans=[ev_span],
                )
                rep.add("WARNING", "REL_TRIPLE_DEDUP_REPLACED",
                        f"重复三元组 {subj}-[{pred}]->{obj} 替换为更高置信度 conf={conf:.2f}")
            else:
                rep.add("WARNING", "REL_TRIPLE_DEDUP_SKIPPED",
                        f"重复三元组 {subj}-[{pred}]->{obj} (本项conf={conf:.2f}) 丢弃")
            continue
        seen_triples[dedup_key] = len(relations)

        # 如果映射后子/宾type已知，就用已知的；否则用解析阶段hint
        subj_t = name_set.get(subj, subj_type_hint)
        obj_t = name_set.get(obj, obj_type_hint)
        relations.append(ExtractedRelation(
            subject=subj, predicate=pred, object=obj,
            subjectType=subj_t, objectType=obj_t,
            vt_from=vt_from, vt_to=vt_to,
            vt_precision_from=_infer_precision(vt_from),
            vt_precision_to=_infer_precision(vt_to),
            status=status, confidence=conf,
            evidenceSpans=[ev_span],
        ))
    return relations


# ============================================================================
# 把 Pydantic payload + QualityReport 转成普通 dict（供 API 返回）
# ============================================================================
def _to_api_payload(
    payload: LlmExtractionPayload, rep: QualityReport
) -> Dict[str, Any]:
    def _span_dict(s):
        return {"start": s.start, "end": s.end}

    def _ent(e: ExtractedEntity) -> Dict[str, Any]:
        return {"name": e.canonicalName, "mention": e.mention, "type": e.type,
                "span": _span_dict(e.span)}

    def _anc(a: TimeAnchor) -> Dict[str, Any]:
        return {"expr": a.expr, "type": a.type, "normISO": a.normISO,
                "precision": a.precision, "relativeAnchor": a.relativeAnchor,
                "span": _span_dict(a.span)}

    def _rel(r: ExtractedRelation) -> Dict[str, Any]:
        return {"head": r.subject, "relation": r.predicate, "tail": r.object,
                "subjectType": r.subjectType, "objectType": r.objectType,
                "vt_from": r.vt_from, "vt_to": r.vt_to,
                "vt_precision_from": r.vt_precision_from,
                "vt_precision_to": r.vt_precision_to,
                "status": r.status, "confidence": r.confidence,
                "evidenceSpans": [_span_dict(s) for s in r.evidenceSpans]}

    def _iss(i) -> Dict[str, Any]:
        return {"level": i.level, "code": i.code, "message": i.message}

    return {
        "entities": [_ent(e) for e in payload.entities],
        "timeAnchors": [_anc(a) for a in payload.timeAnchors],
        "relations": [_rel(r) for r in payload.relations],
        "causalEdges": [],
        "qualityReport": [_iss(i) for i in rep.issues],
        "qualityStats": rep.stats,
    }


# ============================================================================
# 主 API /api/extract（两阶段：节点 → 关系）
# ============================================================================
@router.post("/api/extract", response_model=ExtractionResult)
def extract(req: ExtractionRequest, request: Request) -> ExtractionResult:
    llm_client: LLMClient = request.app.state.llm_client
    graph_writer: GraphWriter = request.app.state.graph_writer
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="待抽取文本为空")

    t_total = time.time()
    total_tokens = 0
    rep = QualityReport()

    # ---- 阶段1：节点抽取 ----
    node_msgs = build_node_messages(text=text, ontology=req.ontology or None)
    node_json, tok1 = _llm_call_with_retry(llm_client, node_msgs)
    total_tokens += tok1
    entities, anchors, alias_map, doc_time = _parse_nodes(node_json, text, rep)

    if not entities:
        raise HTTPException(status_code=500,
                            detail=f"阶段1 未抽到任何实体，无法进入关系抽取。issues={rep.stats}")

    # 实体名 → type 映射（阶段2 反查 + 实体表注入）
    name_set: Dict[str, str] = {e.canonicalName: e.type for e in entities}
    rep.add("INFO", "PIPELINE_TWO_STAGE",
            f"[Semantica 式两阶段] 阶段1 节点抽取: 实体×{len(entities)}、"
            f"时间锚点×{len(anchors)}、指代链别名×{len(alias_map)}")

    # ---- 阶段2：关系抽取（实体表硬约束）----
    entity_table = format_entity_table(
        [{"canonicalName": n, "type": t} for n, t in name_set.items()]
    )
    rel_msgs = build_relation_messages(
        text=text, entity_table_str=entity_table, ontology=req.ontology or None,
    )
    rel_json, tok2 = _llm_call_with_retry(llm_client, rel_msgs)
    total_tokens += tok2
    relations = _parse_relations(rel_json, text, name_set, alias_map, rep)
    rep.stats["relations_extracted"] = len(relations)

    # ---- 组装 payload + 质量管道兜底（W1-W3：span 夹紧 / 时态交换 / 近邻消歧）----
    payload = LlmExtractionPayload(
        docTime=doc_time,
        entities=entities,
        timeAnchors=anchors,
        relations=relations,
        causalEdges=[],
    )
    payload, rep2 = run_quality_pipeline(payload, text)
    for i in rep2.issues:
        rep.add(i.level, i.code, i.message)

    # ---- 写入 Neo4j ----
    try:
        write_count = graph_writer.write_llm_extracted(
            payload, model_id=int(req.modelId), doc_id=req.docId,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j 写入失败: {e}")

    api_dict = _to_api_payload(payload, rep)
    return ExtractionResult(
        entities=api_dict["entities"],
        relations=api_dict["relations"],
        timeAnchors=api_dict["timeAnchors"],
        causalEdges=api_dict["causalEdges"],
        qualityReport=api_dict["qualityReport"],
        qualityStats=api_dict["qualityStats"],
        tokenConsumed=total_tokens,
        duration=int((time.time() - t_total) * 1000),
        writeCount=write_count,
    )

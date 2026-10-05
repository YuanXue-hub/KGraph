"""基于 LLM 的知识抽取端点（Semantica 式两阶段流水线）。

抽取逻辑已下沉到 core/extraction_service.py（可复用的 extract_entities /
extract_relations 两个方法），本模块只负责：
  · HTTP 协议层：参数校验、llm_model 动态选模型、异常 → HTTPException
  · 两阶段编排：extract_entities → extract_relations
  · 质量管道兜底（W1-W5）与 Neo4j 写入
  · Pydantic payload → API dict 转换

因果边（causalEdges）不做 LLM 抽取：等图谱构建完成后走图上离线推理。
LLM / KOS / DL / 结构化是四种完全独立的抽取方法，本模块只负责 LLM 抽取。
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from core.extraction_schema import (
    ExtractedEntity,
    ExtractedRelation,
    LlmExtractionPayload,
    TimeAnchor,
)
from core.extraction_service import (
    EntityStageResult,
    extract_entities,
    extract_relations,
)
from core.extraction_validator import (
    QualityReport,
    run_quality_pipeline,
)
from core.graph_writer import GraphWriter
from core.llm_client import LLMClient
from models.schemas import (
    EntityExtractRequest,
    RelationExtractRequest,
    ExtractionRequest,
    ExtractionResult,
)

router = APIRouter()


# ============================================================================
# 公共：动态选模型 + 调用埋点（主链路与纯计算接口共用，逻辑与主链路原实现一致）
# ============================================================================
def _pick_llm_client(request: Request, llm_model_id: Optional[int]) -> LLMClient:
    """llm_model 表 id 动态构造客户端，无效/未指定则返回服务默认。"""
    if not llm_model_id:
        return request.app.state.llm_client
    try:
        from utils.db.mysql_client import MysqlClient
        row = MysqlClient().get_llm_model_by_id(int(llm_model_id))
        if row and row.get("enabled"):
            return LLMClient({
                "model": {
                    "model_name": row["model_name"],
                    "provider": row.get("provider"),
                    "context_window": row.get("context_window"),
                    "api_key": row["api_key"],
                    "base_url": row["base_url"],
                    "timeout_sec": 300.0,
                    "max_retries": 1,
                }
            })
    except Exception:
        import traceback
        traceback.print_exc()
    return request.app.state.llm_client


def _log_call(user_id: Optional[int], llm_client: LLMClient,
              tokens: int, dur_ms: int) -> None:
    """按实际 LLM 调用逐条埋点（阶段1/阶段2 各 1 条，与评估按指标埋点口径一致）。"""
    try:
        from utils.db.mysql_client import MysqlClient
        model_name = llm_client.model_name if hasattr(llm_client, "model_name") else "unknown"
        MysqlClient().log_request(
            user_id=user_id,
            model_name=model_name,
            total_tokens=tokens,
            duration=dur_ms,
            status="success",
        )
    except Exception:
        pass


# ============================================================================
# 把 Pydantic payload + QualityReport 转成普通 dict（供 API 返回）
# ============================================================================
def _to_api_payload(
    payload: LlmExtractionPayload, rep: QualityReport
) -> Dict[str, Any]:
    def _span_dict(s):
        return {"start": s.start, "end": s.end} if s else None

    def _ent(e: ExtractedEntity) -> Dict[str, Any]:
        return {"name": e.canonicalName, "evidenceText": e.evidenceText,
                "type": e.type, "span": None, "evidenceSpans": []}

    def _anc(a: TimeAnchor) -> Dict[str, Any]:
        return {"evidenceText": a.evidenceText, "type": a.type, "normISO": a.normISO,
                "precision": a.precision, "relativeAnchor": a.relativeAnchor,
                "span": None, "evidenceSpans": []}

    def _rel(r: ExtractedRelation) -> Dict[str, Any]:
        return {"head": r.subject, "relation": r.predicate, "tail": r.object,
                "subjectType": r.subjectType, "objectType": r.objectType,
                "vt_from": r.vt_from, "vt_to": r.vt_to,
                "vt_precision_from": r.vt_precision_from,
                "vt_precision_to": r.vt_precision_to,
                "confidence": r.confidence,
                "evidenceText": r.evidenceText,
                "evidenceSpans": [_span_dict(s) for s in r.evidenceSpans]}

    def _iss(i) -> Dict[str, Any]:
        return {"level": i.level, "code": i.code, "message": i.message}

    # 从 alias_map 还原 coreferenceChains（别名 → 规范名 分组）
    from collections import defaultdict
    grouped: Dict[str, List[str]] = defaultdict(list)
    for alias, canonical in (payload.aliasMap or {}).items():
        grouped[canonical].append(alias)
    coreference_chains = [
        {"canonicalName": c, "aliases": aliases}
        for c, aliases in grouped.items()
    ]

    return {
        "entities": [_ent(e) for e in payload.entities],
        "timeAnchors": [_anc(a) for a in payload.timeAnchors],
        "coreferenceChains": coreference_chains,
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
    llm_client = _pick_llm_client(request, req.llmModelId)
    graph_writer: GraphWriter = request.app.state.graph_writer
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="待抽取文本为空")

    t_total = time.time()
    total_tokens = 0
    rep = QualityReport()

    # ---- 阶段1：节点抽取（可复用方法）----
    t_stage = time.time()
    try:
        stage1: EntityStageResult = extract_entities(
            llm_client, text, ontology=req.ontology or None, rep=rep,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    total_tokens += stage1.tokens
    _log_call(req.userId, llm_client, stage1.tokens, int((time.time() - t_stage) * 1000))

    # ---- 阶段2：关系抽取（实体表硬约束，可复用方法）----
    t_stage = time.time()
    try:
        relations, tok2 = extract_relations(
            llm_client, text, stage1, ontology=req.ontology or None, rep=rep,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    total_tokens += tok2
    _log_call(req.userId, llm_client, tok2, int((time.time() - t_stage) * 1000))

    # ---- 组装 payload + 质量管道兜底（W1-W5：span 夹紧 / 时态交换 / 消歧 / DAG / 低置信标记）----
    payload = LlmExtractionPayload(
        docTime=stage1.doc_time,
        entities=stage1.entities,
        timeAnchors=stage1.time_anchors,
        relations=relations,
        causalEdges=[],
        aliasMap=stage1.alias_map,
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
    duration_ms = int((time.time() - t_total) * 1000)
    # LLM 调用监控埋点：阶段1/阶段2 已在上方 _log_call 逐条记录，此处不再重复汇总
    return ExtractionResult(
        entities=api_dict["entities"],
        relations=api_dict["relations"],
        timeAnchors=api_dict["timeAnchors"],
        coreferenceChains=api_dict["coreferenceChains"],
        causalEdges=api_dict["causalEdges"],
        qualityReport=api_dict["qualityReport"],
        qualityStats=api_dict["qualityStats"],
        tokenConsumed=total_tokens,
        duration=duration_ms,
        writeCount=write_count,
    )


# ============================================================================
# 纯计算接口（不写库）：分层抽取，供对比实验/分层消融复用
# ============================================================================
def _rebuild_stage1(entity_stage: Dict[str, Any]) -> EntityStageResult:
    """把阶段1 API 输出（dict）重建为 EntityStageResult（Pydantic 校验兜底）。"""
    entities = [
        ExtractedEntity(
            mention=e["mention"],
            canonicalName=e.get("name") or e.get("canonicalName"),
            type=e["type"],
            span=e["span"],
        )
        for e in entity_stage.get("entities", [])
        if e.get("name") or e.get("canonicalName")
    ]
    anchors = [
        TimeAnchor(
            expr=a["expr"], type=a.get("type", "UNKNOWN"),
            normISO=a.get("normISO"), precision=a.get("precision", "unknown"),
            relativeAnchor=a.get("relativeAnchor"), span=a["span"],
        )
        for a in entity_stage.get("timeAnchors", [])
    ]
    return EntityStageResult(
        entities=entities,
        time_anchors=anchors,
        alias_map=entity_stage.get("aliasMap", {}) or {},
        doc_time=entity_stage.get("docTime"),
        tokens=0,  # 阶段1 token 已在其端点记录，此处不重复计
    )


@router.post("/api/extract/entities")
def extract_entities_api(req: EntityExtractRequest, request: Request) -> Dict[str, Any]:
    """阶段1：只抽实体（含时间锚点/指代链归并），纯计算不写库。"""
    llm_client = _pick_llm_client(request, req.llmModelId)
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="待抽取文本为空")

    t0 = time.time()
    rep = QualityReport()
    try:
        stage1 = extract_entities(
            llm_client, text, ontology=req.ontology or None, rep=rep,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    _log_call(req.userId, llm_client, stage1.tokens, int((time.time() - t0) * 1000))

    def _ent(e: ExtractedEntity):
        return {"name": e.canonicalName, "mention": e.mention, "type": e.type,
                "span": {"start": e.span.start, "end": e.span.end} if e.span else None}

    def _anc(a: TimeAnchor):
        return {"expr": a.expr, "type": a.type, "normISO": a.normISO,
                "precision": a.precision, "relativeAnchor": a.relativeAnchor,
                "span": {"start": a.span.start, "end": a.span.end} if a.span else None}

    return {
        "entities": [_ent(e) for e in stage1.entities],
        "timeAnchors": [_anc(a) for a in stage1.time_anchors],
        "aliasMap": stage1.alias_map,
        "docTime": stage1.doc_time,
        "qualityReport": [{"level": i.level, "code": i.code, "message": i.message}
                          for i in rep.issues],
        "tokenConsumed": stage1.tokens,
        "duration": int((time.time() - t0) * 1000),
    }


@router.post("/api/extract/relations")
def extract_relations_api(req: RelationExtractRequest, request: Request) -> Dict[str, Any]:
    """阶段2：注入阶段1产物抽关系（实体表硬约束），纯计算不写库、不带质量管道。"""
    llm_client = _pick_llm_client(request, req.llmModelId)
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="待抽取文本为空")
    if not req.entityStage or not req.entityStage.get("entities"):
        raise HTTPException(status_code=400, detail="entityStage 为空，请先调用 /api/extract/entities")

    t0 = time.time()
    stage1 = _rebuild_stage1(req.entityStage)
    if not stage1.entities:
        raise HTTPException(status_code=400, detail="entityStage.entities 解析失败")

    try:
        relations, tok2 = extract_relations(
            llm_client, text, stage1, ontology=req.ontology or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    _log_call(req.userId, llm_client, tok2, int((time.time() - t0) * 1000))

    # 纯抽取结果：不跑 W1-W5 质量管道（主链路 /api/extract 才跑，这里保留方法原生输出）
    payload = LlmExtractionPayload(
        docTime=stage1.doc_time,
        entities=stage1.entities,
        timeAnchors=stage1.time_anchors,
        relations=relations,
        causalEdges=[],
        aliasMap=stage1.alias_map,
    )
    api_dict = _to_api_payload(payload, QualityReport())
    return {
        "entities": api_dict["entities"],
        "relations": api_dict["relations"],
        "timeAnchors": api_dict["timeAnchors"],
        "causalEdges": [],
        "qualityReport": [],
        "qualityStats": {},
        "tokenConsumed": tok2,
        "duration": int((time.time() - t0) * 1000),
        "writeCount": {},
    }

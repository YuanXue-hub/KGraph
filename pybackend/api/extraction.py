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
from typing import Any, Dict

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
from models.schemas import ExtractionRequest, ExtractionResult

router = APIRouter()


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
                "confidence": r.confidence,
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
    # 抽取模型可指定（llm_model 表 id）：动态构造，无效则回退服务默认配置
    if req.llmModelId:
        try:
            from utils.db.mysql_client import MysqlClient
            row = MysqlClient().get_llm_model_by_id(int(req.llmModelId))
            if row and row.get("enabled"):
                llm_client = LLMClient({
                    "model": {
                        "model_name": row["model_name"],
                        "api_key": row["api_key"],
                        "base_url": row["base_url"],
                        "timeout_sec": 300.0,
                        "max_retries": 1,
                    }
                })
        except Exception:
            import traceback
            traceback.print_exc()
    graph_writer: GraphWriter = request.app.state.graph_writer
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="待抽取文本为空")

    def _log_call(tokens: int, dur_ms: int):
        """按实际 LLM 调用逐条埋点（阶段1/阶段2 各 1 条，与评估按指标埋点口径一致）。"""
        try:
            from utils.db.mysql_client import MysqlClient
            model_name = llm_client.model_name if hasattr(llm_client, "model_name") else "unknown"
            MysqlClient().log_request(
                user_id=getattr(req, "userId", None),
                model_name=model_name,
                total_tokens=tokens,
                duration=dur_ms,
                status="success",
            )
        except Exception:
            pass

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
    _log_call(stage1.tokens, int((time.time() - t_stage) * 1000))

    # ---- 阶段2：关系抽取（实体表硬约束，可复用方法）----
    t_stage = time.time()
    try:
        relations, tok2 = extract_relations(
            llm_client, text, stage1, ontology=req.ontology or None, rep=rep,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    total_tokens += tok2
    _log_call(tok2, int((time.time() - t_stage) * 1000))

    # ---- 组装 payload + 质量管道兜底（W1-W5：span 夹紧 / 时态交换 / 消歧 / DAG / 低置信标记）----
    payload = LlmExtractionPayload(
        docTime=stage1.doc_time,
        entities=stage1.entities,
        timeAnchors=stage1.time_anchors,
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
    duration_ms = int((time.time() - t_total) * 1000)
    # LLM 调用监控埋点：阶段1/阶段2 已在上方 _log_call 逐条记录，此处不再重复汇总
    return ExtractionResult(
        entities=api_dict["entities"],
        relations=api_dict["relations"],
        timeAnchors=api_dict["timeAnchors"],
        causalEdges=api_dict["causalEdges"],
        qualityReport=api_dict["qualityReport"],
        qualityStats=api_dict["qualityStats"],
        tokenConsumed=total_tokens,
        duration=duration_ms,
        writeCount=write_count,
    )

"""LLM 抽取质量评估端点（G-Eval 风格 LLM-as-Judge + 内在指标）。

核心评估逻辑（criteria / 裁判 / 内在指标计算）在 core/evaluation_core.py
（无 FastAPI 依赖），MCP Server（mcp_server.py）复用同一套实现，零漂移。
本文件只保留 HTTP 层：请求模型 + 事件 generator + 同步/SSE 端点 + 用量埋点。
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.evaluation_core import (
    ALL_METRIC_KEYS as _ALL_METRICS,
    CRITERIA_BITEMPORAL as _CRITERIA_BITEMPORAL,
    CRITERIA_ENTITY as _CRITERIA_ENTITY,
    CRITERIA_EVIDENCE as _CRITERIA_EVIDENCE,
    CRITERIA_FAITH as _CRITERIA_FAITH,
    CRITERIA_PREDICATE as _CRITERIA_PREDICATE,
    DEFAULT_SAMPLE,
    compute_intrinsic as _compute_intrinsic,
    evidence_text as _evidence_text,
    judge_safe as _judge_safe,
    sample_items as _sample,
)
from core.llm_client import LLMClient
from utils.db.mysql_client import MysqlClient

router = APIRouter()


class EvaluationRequest(BaseModel):
    text: str = ""
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    sampleSize: int = DEFAULT_SAMPLE  # 正数 = 抽样条数；0 = 全量判定
    llmModelId: Optional[int] = None  # 裁判模型（llm_model 表 id），不传用服务默认配置
    metrics: Optional[List[str]] = None  # 选中的裁判指标 key，空/None = 全部指标
    userId: Optional[int] = None


def _validate_eval(req: EvaluationRequest) -> str:
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="待评估原文为空")
    if not req.entities and not req.relations:
        raise HTTPException(status_code=400, detail="抽取结果为空，无法评估")
    return text


def _evaluate_events(req: EvaluationRequest, request: Request):
    """评估主流程 generator：逐指标产出 (event, data) 事件。

    事件序列：intrinsic → metric（每选中指标一个）→ done。
    SSE 端点逐事件推送（前端实时出分），同步端点聚合为完整报告。
    """
    llm_client: LLMClient = request.app.state.llm_client
    # 裁判模型标识：judgeModelRaw=原始 model_name（埋点/统计口径），judgeModel=显示格式（随报告返回）
    judge_model_raw = getattr(llm_client, "model_name", "") or "default"
    judge_model_name = judge_model_raw
    # 裁判模型可指定（llm_model 表 id）：动态构造，无效则回退服务默认配置
    if req.llmModelId:
        try:
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
                judge_model_raw = row["model_name"]
                judge_model_name = f"{row.get('display_name') or row['model_name']} ({row['model_name']})"
        except Exception:
            import traceback
            traceback.print_exc()

    text = (req.text or "").strip()
    t0 = time.time()
    total_tokens = 0
    # sampleSize：正数 = 抽样条数；0 或负数 = 全量评估
    sample_n = req.sampleSize if req.sampleSize is not None else DEFAULT_SAMPLE

    # 指标选择：metrics 为空/None 时评估全部裁判指标（非法 key 忽略）
    selected = {m for m in (req.metrics or []) if m in _ALL_METRICS} or _ALL_METRICS

    # ---- 层次1：内在指标（全量，0 次 LLM）----
    intrinsic = _compute_intrinsic(text, req.entities, req.relations)
    yield "intrinsic", intrinsic

    # ---- 层次2：LLM-as-Judge（抽样，每指标 1 次 LLM 调用，算完即推送）----
    rel_sample = _sample(req.relations, sample_n)
    ent_sample = _sample(req.entities, sample_n)
    judge: Dict[str, Dict[str, Any]] = {}
    # 逐次调用收集器：每次真实发起的裁判 LLM 调用记一条，供调用监控逐条埋点
    judge_calls: List[Dict[str, Any]] = []

    def _emit_metric(key: str, label: str, m: Dict[str, Any]):
        judge[key] = m
        return ("metric", {"key": key, "label": label, "data": m})

    if rel_sample:
        # 关系级基础样本（忠实度 / 谓词合理性共用）
        base_items = [
            {
                "id": i + 1,
                "head": str(r.get("head") or ""),
                "predicate": str(r.get("relation") or ""),
                "tail": str(r.get("tail") or ""),
            }
            for i, r in enumerate(rel_sample)
        ]
        if "tripleFaithfulness" in selected:
            m = _judge_safe(llm_client, "三元组忠实度", _CRITERIA_FAITH, text, base_items)
            total_tokens += m["tokens"]
            yield _emit_metric("tripleFaithfulness", "三元组忠实度", m)

        if "predicateReasonableness" in selected:
            m = _judge_safe(llm_client, "谓词合理性", _CRITERIA_PREDICATE, text, base_items, calls=judge_calls)
            total_tokens += m["tokens"]
            yield _emit_metric("predicateReasonableness", "谓词合理性", m)

        # 双时态标注（附加 vt 字段）
        if "bitemporalCorrectness" in selected:
            bi_items = []
            for i, r in enumerate(rel_sample):
                bi_items.append({
                    **base_items[i],
                    "vt_from": r.get("vt_from"),
                    "vt_to": r.get("vt_to"),
                })
            m = _judge_safe(llm_client, "双时态标注正确性", _CRITERIA_BITEMPORAL, text, bi_items)
            total_tokens += m["tokens"]
            yield _emit_metric("bitemporalCorrectness", "双时态标注正确性", m)

        # 证据句有效性（仅有证据片段的关系）
        if "evidenceValidity" in selected:
            ev_items = []
            for r in rel_sample:
                ev = _evidence_text(text, r)
                if ev:
                    ev_items.append({
                        "id": len(ev_items) + 1,
                        "head": str(r.get("head") or ""),
                        "predicate": str(r.get("relation") or ""),
                        "tail": str(r.get("tail") or ""),
                        "evidence": ev,
                    })
            m = _judge_safe(llm_client, "证据句有效性", _CRITERIA_EVIDENCE, text, ev_items, calls=judge_calls)
            total_tokens += m["tokens"]
            yield _emit_metric("evidenceValidity", "证据句有效性", m)
    elif req.entities:
        # 有实体但无关系：选中的关系级指标按缺失计 0 分，避免综合得分虚高
        _missing = {
            "tripleFaithfulness": "三元组忠实度",
            "predicateReasonableness": "谓词合理性",
            "bitemporalCorrectness": "双时态标注正确性",
            "evidenceValidity": "证据句有效性",
        }
        for key, label in _missing.items():
            if key in selected:
                m = {
                    "score": 0.0,
                    "reason": f"抽取结果无任何关系，{label}按缺失计 0 分（实体孤立率 100%，图谱无结构）",
                    "details": [],
                    "tokens": 0,
                }
                yield _emit_metric(key, label, m)

    if ent_sample and "entityCorrectness" in selected:
        ent_items = [
            {"id": i + 1, "name": str(e.get("name") or ""), "type": str(e.get("type") or "")}
            for i, e in enumerate(ent_sample)
        ]
        m = _judge_safe(llm_client, "实体边界正确性", _CRITERIA_ENTITY, text, ent_items, calls=judge_calls)
        total_tokens += m["tokens"]
        yield _emit_metric("entityCorrectness", "实体边界正确性", m)

    # ---- 综合得分：选中且已出分指标的均值 ----
    scores = [v["score"] for v in judge.values() if v.get("score") is not None]
    overall = round(sum(scores) / len(scores), 4) if scores else None

    yield "done", {
        "overall": overall,
        "sampledRelations": len(rel_sample),
        "sampledEntities": len(ent_sample),
        "tokenConsumed": total_tokens,
        "duration": int((time.time() - t0) * 1000),
        "judgeModel": judge_model_name,
        "judgeModelRaw": judge_model_raw,
        "judgeCalls": len(judge_calls),
        "judgeCallDetails": judge_calls,
    }


@router.post("/api/evaluate")
def evaluate(req: EvaluationRequest, request: Request) -> Dict[str, Any]:
    _validate_eval(req)
    result: Dict[str, Any] = {}
    judge: Dict[str, Dict[str, Any]] = {}
    judge_model_name = ""
    call_details: List[Dict[str, Any]] = []
    for event, data in _evaluate_events(req, request):
        if event == "intrinsic":
            result["intrinsic"] = data
        elif event == "metric":
            judge[data["key"]] = data["data"]
        elif event == "done":
            result.update(data)
            # 埋点用原始 model_name（与抽取/问答一致），报告字段 judgeModel 保留显示格式
            judge_model_name = data.get("judgeModelRaw") or data.get("judgeModel") or ""
            call_details = data.get("judgeCallDetails") or []
    result["llmJudge"] = judge
    # 记录 LLM 调用日志（供用量统计）：按裁判实际调用次数逐条记录（每次评估最多 5 条）
    try:
        from utils.db.mysql_client import MysqlClient
        client = MysqlClient()
        for c in call_details:
            client.log_request(
                user_id=req.userId,
                model_name=judge_model_name or "unknown",
                total_tokens=c.get("tokens", 0),
                duration=c.get("duration", 0),
                status=c.get("status", "success"),
            )
    except Exception:
        pass
    return result


@router.post("/api/evaluate/stream")
def evaluate_stream(req: EvaluationRequest, request: Request):
    """SSE 流式评估：逐指标实时推送（intrinsic → metric* → done）。

    事件格式：event: <name>\ndata: <json>\n\n
    """
    _validate_eval(req)

    def gen():
        judge_model_name = ""
        total_tokens = 0
        duration = 0
        call_details: List[Dict[str, Any]] = []
        try:
            for event, data in _evaluate_events(req, request):
                if event == "done":
                    # 埋点用原始 model_name（与抽取/问答/同步端点一致口径）
                    judge_model_name = data.get("judgeModelRaw") or data.get("judgeModel") or ""
                    total_tokens = data.get("tokenConsumed", 0)
                    duration = data.get("duration", 0)
                    call_details = data.get("judgeCallDetails") or []
                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        except HTTPException as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e.detail)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)[:200]}, ensure_ascii=False)}\n\n"
        finally:
            # 记录 LLM 调用日志（供用量统计）：按裁判实际调用次数逐条记录（每次评估最多 5 条）
            try:
                from utils.db.mysql_client import MysqlClient
                client = MysqlClient()
                for c in call_details:
                    client.log_request(
                        user_id=req.userId,
                        model_name=judge_model_name or "unknown",
                        total_tokens=c.get("tokens", 0),
                        duration=c.get("duration", 0),
                        status=c.get("status", "success"),
                    )
            except Exception:
                pass

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

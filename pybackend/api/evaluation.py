"""LLM 抽取质量评估端点（G-Eval 风格 LLM-as-Judge + 内在指标）。

评估分两层（与 DeepEval G-Eval 机制一致：criteria -> 逐步推理 -> score + reason，
但直接复用项目内 LLMClient 的 DeepSeek JSON 模式，避免引入 deepeval 重依赖）：

  1. 内在指标（0 次 LLM，全量计算）：
     孤立实体率 / 平均度 / 证据覆盖率 / 低置信率 等图结构统计
  2. LLM-as-Judge（每指标 1 次 LLM 调用，抽样或全量判定，sampleSize<=0 为全量）：
     - 三元组忠实度  tripleFaithfulness    关系是否被原文明确支持
     - 谓词合理性    predicateReasonableness 谓词是否恰当、方向是否正确
     - 双时态正确性  bitemporalCorrectness   vt_from/vt_to 标注是否符合原文语义
     - 证据句有效性  evidenceValidity        evidenceSpans 切片是否支撑三元组
     - 实体边界正确性 entityCorrectness      实体名称是否完整、类型是否匹配

裁判约束：只基于原文判定，禁止使用裁判模型自身世界知识推断
（规避 LREC 2026 指出的 world-knowledge bias）。
"""
from __future__ import annotations

import json
import random
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.extraction_service import _extract_json
from core.llm_client import LLMClient
from utils.db.mysql_client import MysqlClient

router = APIRouter()

DEFAULT_SAMPLE = 30


class EvaluationRequest(BaseModel):
    text: str = ""
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    sampleSize: int = DEFAULT_SAMPLE  # 正数 = 抽样条数；0 = 全量判定
    llmModelId: Optional[int] = None  # 裁判模型（llm_model 表 id），不传用服务默认配置
    metrics: Optional[List[str]] = None  # 选中的裁判指标 key，空/None = 全部指标


# ============================================================================
# 内在指标（0 次 LLM）
# ============================================================================
def _compute_intrinsic(text: str, entities: List[Dict[str, Any]],
                       relations: List[Dict[str, Any]]) -> Dict[str, Any]:
    ent_names = [str(e.get("name") or "").strip() for e in entities]
    ent_names = [n for n in ent_names if n]
    entity_count = len(ent_names)
    relation_count = len(relations)

    # 孤立实体：未出现在任何关系头/尾的实体
    rel_entities = set()
    for r in relations:
        h = str(r.get("head") or "").strip()
        t = str(r.get("tail") or "").strip()
        if h:
            rel_entities.add(h)
        if t:
            rel_entities.add(t)
    isolated = [n for n in ent_names if n not in rel_entities]

    # 证据覆盖率：存在非平凡 evidenceSpans 的关系占比
    def _has_evidence(r: Dict[str, Any]) -> bool:
        for s in r.get("evidenceSpans") or []:
            try:
                start, end = int(s.get("start", 0)), int(s.get("end", -1))
                if 0 < start < end <= len(text):
                    return True
            except (TypeError, ValueError):
                continue
        return False

    evidenced = sum(1 for r in relations if _has_evidence(r))

    # 低置信率：confidence < 0.60 的关系占比（有 confidence 字段时）
    confs = []
    for r in relations:
        c = r.get("confidence")
        if c is not None and c != "":
            try:
                confs.append(float(c))
            except (TypeError, ValueError):
                continue
    low_conf = sum(1 for c in confs if c < 0.60)

    return {
        "entityCount": entity_count,
        "relationCount": relation_count,
        "isolatedEntities": isolated,
        "isolatedRate": round(len(isolated) / entity_count, 4) if entity_count else 0.0,
        "avgDegree": round(2 * relation_count / entity_count, 4) if entity_count else 0.0,
        "evidenceCoverage": round(evidenced / relation_count, 4) if relation_count else 0.0,
        "lowConfidenceRate": round(low_conf / len(confs), 4) if confs else None,
    }


# ============================================================================
# G-Eval 风格裁判（每指标 1 次 LLM 调用）
# ============================================================================
_CRITERIA_FAITH = (
    "逐条判断三元组（头实体, 谓词, 尾实体）是否被原文明确支持：\n"
    "a) 头实体与尾实体必须是原文中出现的人/物/事件（允许规范化的名称变体）；\n"
    "b) 谓词表达的关系必须是原文明确陈述的，不能是你基于常识的推断；\n"
    "c) 原文明确否定的关系（如传闻已被否认）判为不通过。"
)

_CRITERIA_PREDICATE = (
    "逐条判断谓词是否恰当：\n"
    "a) 谓词准确表达头尾实体之间的真实关系，且头尾方向正确（未颠倒）；\n"
    "b) 谓词语义与实体类型兼容（如「任职于」连接人物与机构合理，连接人物与数值则不合理）；\n"
    "c) 谓词粒度恰当，不是过于宽泛的「相关」「有关」类词。"
)

_CRITERIA_BITEMPORAL = (
    "逐条判断时间有效性标注（vt_from / vt_to）是否符合原文语义：\n"
    "a) vt_to 为空表示关系持续有效（原文无终止表述）；\n"
    "b) vt_to 有值表示原文明确给出关系终止（如「曾任」「已卸任」「于X年终止」）；\n"
    "c) vt_from/vt_to 时间区间若给出，应与原文时间表述一致；\n"
    "d) 谓词为否定表述（如「并无冲突」「未发生」）且原文确有否认的，时间标注按否定语境判断；\n"
    "e) 原文无任何时间信息且 vt_from/vt_to 均为空的，默认通过。"
)

_CRITERIA_EVIDENCE = (
    "逐条判断证据片段是否真实支撑对应三元组：\n"
    "a) 证据片段确实是原文的一部分；\n"
    "b) 证据片段包含能推断出该三元组的关键信息（同时涉及头实体、尾实体或其指代）；\n"
    "c) 证据与三元组语义一致，不存在证据实际支持其他关系的情况。"
)

_CRITERIA_ENTITY = (
    "逐条判断实体是否为合格的图谱节点：\n"
    "a) 名称是完整的实体指称，无截断（如「北京大学经济学院」被截成「北京大学经济」）也无粘连（两个实体连在一起）；\n"
    "b) 名称语义自洽，不是动词短语或无关片段；\n"
    "c) type 类型标注与实体本身性质匹配。"
)


def _sample(items: List[Any], n: int) -> List[Any]:
    # n <= 0 表示全量评估（前端「全部」选项）
    if n <= 0 or len(items) <= n:
        return list(items)
    return random.sample(items, n)


def _judge(llm_client: LLMClient, metric_label: str, criteria: str,
           text: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """G-Eval 风格单维度裁判：criteria 注入 + 逐条判定 + 严格 JSON 输出。

    三级判定：verdict 2=完全满足 / 1=部分满足（轻微偏差）/ 0=不满足或错误。
    score = Σverdict / (2n)，部分正确的样本贡献 0.5 分，避免二值判定的信息损失。

    返回 {score: 0-1 或 None, reason: 整体结论, details: 每条样本判定, tokens}。
    """
    system = (
        "你是知识图谱抽取质量评估专家。你的任务是严格按照评估标准（criteria），"
        "对每一条待评估样本逐步推理后给出判定。判定必须只基于原文内容，"
        "禁止使用你自己的世界知识进行推断。"
    )
    user = (
        f"## 评估指标\n{metric_label}\n\n"
        f"## 评估标准（criteria）\n{criteria}\n\n"
        f"## 原文\n```\n{text}\n```\n\n"
        f"## 待评估样本\n{json.dumps(items, ensure_ascii=False)}\n\n"
        "## 输出要求\n"
        "请逐步推理每条样本（不要输出推理过程），严格只输出如下 JSON，"
        "不要任何解释或多余文本：\n"
        '{"items": [{"id": <样本id>, "verdict": 0或1或2, "reason": "<不超过40字的判定理由>"}], '
        '"summary": "<不超过80字的整体质量结论>"}\n'
        "verdict 判定标准：2=完全满足评估标准；"
        "1=部分满足（存在轻微偏差，如关系方向正确但谓词粒度宽泛、实体边界轻微不精确、"
        "时间区间部分吻合等）；0=不满足评估标准或错误。"
    )
    content, tokens = llm_client.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        force_json=True,
    )
    data = _extract_json(content)

    verdicts: Dict[int, Dict[str, Any]] = {}
    for v in data.get("items") or []:
        if isinstance(v, dict) and v.get("id") is not None:
            try:
                verdicts[int(v["id"])] = v
            except (TypeError, ValueError):
                continue

    total_verdict = 0
    details: List[Dict[str, Any]] = []
    for it in items:
        v = verdicts.get(int(it["id"])) or {}
        # verdict 解析：优先三级判定；兼容旧版 pass 布尔（true→2 / false→0）；漏判保守取 0
        try:
            verdict = int(v.get("verdict"))
            if verdict not in (0, 1, 2):
                verdict = 2 if v.get("pass") else 0
        except (TypeError, ValueError):
            verdict = 2 if v.get("pass") else 0
        total_verdict += verdict
        detail = {k: it[k] for k in it if k != "id"}
        detail["verdict"] = verdict
        detail["pass"] = verdict == 2
        detail["reason"] = str(v.get("reason") or "")
        details.append(detail)

    return {
        "score": round(total_verdict / (2 * len(items)), 4) if items else None,
        "reason": str(data.get("summary") or ""),
        "details": details,
        "tokens": tokens,
    }


def _judge_safe(llm_client: LLMClient, metric_label: str, criteria: str,
                text: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """单指标失败不拖垮整体评估。"""
    if not items:
        return {"score": None, "reason": "无可用样本", "details": [], "tokens": 0}
    try:
        return _judge(llm_client, metric_label, criteria, text, items)
    except Exception as e:
        return {"score": None, "reason": f"该指标评估失败: {str(e)[:120]}", "details": [], "tokens": 0}


def _evidence_text(text: str, r: Dict[str, Any]) -> str:
    """从 evidenceSpans 切出证据片段（最多取前 2 段拼接）。"""
    parts: List[str] = []
    for s in r.get("evidenceSpans") or []:
        try:
            start = max(0, int(s.get("start", 0)))
            end = min(len(text), int(s.get("end", -1)) + 1)
            if end > start:
                parts.append(text[start:end])
        except (TypeError, ValueError):
            continue
        if len(parts) >= 2:
            break
    return " …… ".join(parts)


# ============================================================================
# 主流程：事件 generator（同步 evaluate 与 SSE stream 共用）
# ============================================================================
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
    # 裁判模型标识：记录实际使用的模型（显示名 + model_name），随报告返回
    judge_model_name = getattr(llm_client, "model_name", "") or "default"
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
    _ALL_METRICS = {
        "tripleFaithfulness", "predicateReasonableness",
        "bitemporalCorrectness", "evidenceValidity", "entityCorrectness",
    }
    selected = {m for m in (req.metrics or []) if m in _ALL_METRICS} or _ALL_METRICS

    # ---- 层次1：内在指标（全量，0 次 LLM）----
    intrinsic = _compute_intrinsic(text, req.entities, req.relations)
    yield "intrinsic", intrinsic

    # ---- 层次2：LLM-as-Judge（抽样，每指标 1 次 LLM 调用，算完即推送）----
    rel_sample = _sample(req.relations, sample_n)
    ent_sample = _sample(req.entities, sample_n)
    judge: Dict[str, Dict[str, Any]] = {}

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
            m = _judge_safe(llm_client, "谓词合理性", _CRITERIA_PREDICATE, text, base_items)
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
            m = _judge_safe(llm_client, "证据句有效性", _CRITERIA_EVIDENCE, text, ev_items)
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
        m = _judge_safe(llm_client, "实体边界正确性", _CRITERIA_ENTITY, text, ent_items)
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
    }


@router.post("/api/evaluate")
def evaluate(req: EvaluationRequest, request: Request) -> Dict[str, Any]:
    _validate_eval(req)
    result: Dict[str, Any] = {}
    judge: Dict[str, Dict[str, Any]] = {}
    for event, data in _evaluate_events(req, request):
        if event == "intrinsic":
            result["intrinsic"] = data
        elif event == "metric":
            judge[data["key"]] = data["data"]
        elif event == "done":
            result.update(data)
    result["llmJudge"] = judge
    return result


@router.post("/api/evaluate/stream")
def evaluate_stream(req: EvaluationRequest, request: Request):
    """SSE 流式评估：逐指标实时推送（intrinsic → metric* → done）。

    事件格式：event: <name>\ndata: <json>\n\n
    """
    _validate_eval(req)

    def gen():
        try:
            for event, data in _evaluate_events(req, request):
                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        except HTTPException as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e.detail)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)[:200]}, ensure_ascii=False)}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

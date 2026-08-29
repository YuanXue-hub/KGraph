"""LLM 抽取质量评估端点（G-Eval 风格 LLM-as-Judge + 内在指标）。

评估分两层（与 DeepEval G-Eval 机制一致：criteria -> 逐步推理 -> score + reason，
但直接复用项目内 LLMClient 的 DeepSeek JSON 模式，避免引入 deepeval 重依赖）：

  1. 内在指标（0 次 LLM，全量计算）：
     孤立实体率 / 平均度 / 证据覆盖率 / 低置信率 等图结构统计
  2. LLM-as-Judge（每指标 1 次 LLM 调用，抽样判定）：
     - 三元组忠实度  tripleFaithfulness    关系是否被原文明确支持
     - 谓词合理性    predicateReasonableness 谓词是否恰当、方向是否正确
     - 双时态正确性  bitemporalCorrectness   status/vt 标注是否符合原文语义
     - 证据句有效性  evidenceValidity        evidenceSpans 切片是否支撑三元组
     - 实体边界正确性 entityCorrectness      实体名称是否完整、类型是否匹配

裁判约束：只基于原文判定，禁止使用裁判模型自身世界知识推断
（规避 LREC 2026 指出的 world-knowledge bias）。
"""
from __future__ import annotations

import json
import random
import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.extraction import _extract_json
from core.llm_client import LLMClient

router = APIRouter()

MAX_SAMPLE = 50
DEFAULT_SAMPLE = 30


class EvaluationRequest(BaseModel):
    text: str = ""
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    sampleSize: int = DEFAULT_SAMPLE


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
    "逐条判断双时态标注是否符合原文语义：\n"
    "a) status=CURRENT 表示原文表明关系当前有效；\n"
    "b) status=EXPIRED 表示原文表明关系已结束（如「曾任」「已卸任」）；\n"
    "c) status=NEGATED 表示原文明确否认该关系（如「传闻不实」「予以否认」）；\n"
    "d) vt_from/vt_to 时间区间若给出，应与原文时间表述一致；\n"
    "e) 原文无任何时间/时态信息且标注 CURRENT 的，默认通过。"
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
    if len(items) <= n:
        return list(items)
    return random.sample(items, n)


def _judge(llm_client: LLMClient, metric_label: str, criteria: str,
           text: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """G-Eval 风格单维度裁判：criteria 注入 + 逐条判定 + 严格 JSON 输出。

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
        '{"items": [{"id": <样本id>, "pass": true或false, "reason": "<不超过40字的判定理由>"}], '
        '"summary": "<不超过80字的整体质量结论>"}'
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

    passed = 0
    details: List[Dict[str, Any]] = []
    for it in items:
        v = verdicts.get(int(it["id"])) or {}
        ok = bool(v.get("pass"))
        if ok:
            passed += 1
        detail = {k: it[k] for k in it if k != "id"}
        detail["pass"] = ok
        detail["reason"] = str(v.get("reason") or "")
        details.append(detail)

    return {
        "score": round(passed / len(items), 4) if items else None,
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
# 主 API /api/evaluate
# ============================================================================
@router.post("/api/evaluate")
def evaluate(req: EvaluationRequest, request: Request) -> Dict[str, Any]:
    llm_client: LLMClient = request.app.state.llm_client
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="待评估原文为空")
    if not req.entities and not req.relations:
        raise HTTPException(status_code=400, detail="抽取结果为空，无法评估")

    t0 = time.time()
    total_tokens = 0
    sample_n = max(1, min(req.sampleSize or DEFAULT_SAMPLE, MAX_SAMPLE))

    # ---- 层次1：内在指标（全量，0 次 LLM）----
    intrinsic = _compute_intrinsic(text, req.entities, req.relations)

    # ---- 层次2：LLM-as-Judge（抽样，每指标 1 次 LLM 调用）----
    rel_sample = _sample(req.relations, sample_n)
    ent_sample = _sample(req.entities, sample_n)
    judge: Dict[str, Dict[str, Any]] = {}

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
        m = _judge_safe(llm_client, "三元组忠实度", _CRITERIA_FAITH, text, base_items)
        judge["tripleFaithfulness"] = m
        total_tokens += m["tokens"]

        m = _judge_safe(llm_client, "谓词合理性", _CRITERIA_PREDICATE, text, base_items)
        judge["predicateReasonableness"] = m
        total_tokens += m["tokens"]

        # 双时态标注（附加 status / vt 字段）
        bi_items = []
        for i, r in enumerate(rel_sample):
            bi_items.append({
                **base_items[i],
                "status": r.get("status"),
                "vt_from": r.get("vt_from"),
                "vt_to": r.get("vt_to"),
            })
        m = _judge_safe(llm_client, "双时态标注正确性", _CRITERIA_BITEMPORAL, text, bi_items)
        judge["bitemporalCorrectness"] = m
        total_tokens += m["tokens"]

        # 证据句有效性（仅有证据片段的关系）
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
        judge["evidenceValidity"] = m
        total_tokens += m["tokens"]

    if ent_sample:
        ent_items = [
            {"id": i + 1, "name": str(e.get("name") or ""), "type": str(e.get("type") or "")}
            for i, e in enumerate(ent_sample)
        ]
        m = _judge_safe(llm_client, "实体边界正确性", _CRITERIA_ENTITY, text, ent_items)
        judge["entityCorrectness"] = m
        total_tokens += m["tokens"]

    # ---- 综合得分：已出分指标的均值 ----
    scores = [v["score"] for v in judge.values() if v.get("score") is not None]
    overall = round(sum(scores) / len(scores), 4) if scores else None

    return {
        "intrinsic": intrinsic,
        "llmJudge": judge,
        "overall": overall,
        "sampledRelations": len(rel_sample),
        "sampledEntities": len(ent_sample),
        "tokenConsumed": total_tokens,
        "duration": int((time.time() - t0) * 1000),
    }

"""KGraph MCP Server —— 把知识抽取 + 质量评估两个能力暴露给大模型。

MCP（Model Context Protocol）兼容所有支持 MCP 的客户端：
  - Trae / Claude Desktop / Cursor / Windsurf（IDE 场景）
  - OpenClaw / AutoGPT / LangGraph（Agent 场景）
  - 任何实现了 mcp client 的 LLM 应用

提供且仅提供两个 Tool：
  kg_extract_full  两阶段 LLM 抽取 + W1-W5 质量管道 → 实体/关系/时间锚点/质量报告
  kg_evaluate      G-Eval 风格评估 → 内在指标 + LLM-as-Judge 五维裁判

运行方式（任选其一）：
  # 本地 CLI（stdio）—— 给 IDE 里的 LLM 用
  python mcp_server.py --transport stdio

  # 远程 HTTP（streamable-http）—— 给远端 Agent 集群用
  python mcp_server.py --transport streamable-http --host 0.0.0.0 --port 8003

  # SSE（传统 HTTP + Server-Sent Events）
  python mcp_server.py --transport sse --port 8003
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ============================================================================
# 1. 启动前准备：把 pybackend 加入 sys.path + 加载 config.json
# ============================================================================
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

# 复用主服务的 config.json（LLM 模型连接），只读不写
_CONFIG_PATH = _THIS_DIR / "config.json"
if not _CONFIG_PATH.exists():
    raise FileNotFoundError(f"config.json 不存在: {_CONFIG_PATH}")
with open(_CONFIG_PATH, encoding="utf-8") as _f:
    CONFIG: Dict[str, Any] = json.load(_f)

# MCP Server（SDK 2.x 要求用 MCPServer，旧版 FastMCP 已被重命名）
from mcp.server.mcpserver import MCPServer

# ============================================================================
# 2. LLM Client 懒加载（唯一运行期外部依赖：DeepSeek API；首次调用时创建）
# ============================================================================
_llm_client = None


def _get_llm_client():
    """懒加载 LLMClient（复用 core/llm_client.py，硬编码 temp=0，推理模型自动 reasoning_effort=low）。"""
    global _llm_client
    if _llm_client is None:
        from core.llm_client import LLMClient
        _llm_client = LLMClient(CONFIG)
    return _llm_client


def _get_client_with_model(model_name: Optional[str]):
    """按需覆盖模型：传了 model_name 动态构造（抽取/裁判共用）；否则用懒加载默认 Client。"""
    if model_name:
        from core.llm_client import LLMClient
        return LLMClient({**CONFIG, "model": {**CONFIG["model"], "model_name": model_name}})
    return _get_llm_client()


# ============================================================================
# 3. 构造 MCP Server
# ============================================================================
kgraph = MCPServer(
    name="kgraph",
    title="KGraph 知识抽取与评估引擎",
    version="0.2.0",
    description=(
        "从非结构化文本抽取实体、关系、时间锚点（两阶段 LLM + 质量管道），"
        "并对抽取结果做 G-Eval 风格质量评估（内在指标 + LLM-as-Judge 五维裁判）。"
    ),
    instructions=(
        "当用户需要从文本构建知识图谱时，调用 kg_extract_full 一次性获得实体、关系、"
        "时间锚点和质量报告。需要评估抽取质量时，把原文和抽取结果传给 kg_evaluate"
        "（entities/relations 直接使用 kg_extract_full 返回的对应 JSON 数组即可）。"
    ),
)


# ============================================================================
# 4. TOOL 1：知识抽取
# ============================================================================

@kgraph.tool(
    name="kg_extract_full",
    description=(
        "从一段文本中一次性抽取完整知识图谱：两阶段 LLM 抽取 + 质量管道（span 夹紧、"
        "去重、事件时序补边、孤立实体兜底）。返回实体清单、关系清单、时间锚点和质量报告。"
        "抽取结果可直接传给 kg_evaluate 做质量评估。"
    ),
)
def kg_extract_full(
    text: str,
    model_name: Optional[str] = None,
    ontology: Optional[str] = None,
    skip_pipeline: bool = False,
) -> str:
    """
    Args:
        text: 待抽取的原文（UTF-8，建议 ≤ 8000 字；超过请先分片）
        model_name: 可选，覆盖默认模型（如 "deepseek-v4-pro" / "deepseek-v4-flash"）
        ontology: 可选，JSON 字符串，自定义实体/关系类型约束。格式：
            {
              "entities": [{"name": "人物", "description": "..."}],
              "relations": [{"name": "任职于", "source": "人物", "target": "组织"}]
            }
        skip_pipeline: True 则跳过 W1-W5 质量管道，纯 LLM 原生输出
    """
    import json as _json

    client = _get_client_with_model(model_name)

    onto = None
    if ontology:
        try:
            onto = _json.loads(ontology)
        except _json.JSONDecodeError as e:
            return _json.dumps({"error": f"ontology JSON 解析失败: {e}"}, ensure_ascii=False)

    try:
        from core.extraction_service import extract_entities, extract_relations
        from core.extraction_validator import QualityReport, run_quality_pipeline
        from core.extraction_schema import LlmExtractionPayload

        rep = QualityReport()
        stage1 = extract_entities(client, text, ontology=onto, rep=rep)
        relations, _ = extract_relations(client, text, stage1, ontology=onto, rep=rep)

        payload = LlmExtractionPayload(
            docTime=stage1.doc_time, entities=stage1.entities,
            timeAnchors=stage1.time_anchors, relations=relations, causalEdges=[],
        )
        if not skip_pipeline:
            payload, rep2 = run_quality_pipeline(payload, text)
            for i in rep2.issues:
                rep.add(i.level, i.code, i.message)

        result = _serialize_payload(payload, rep)
        return _json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        import traceback
        return _json.dumps({
            "error": str(e),
            "traceback": traceback.format_exc(limit=5),
        }, ensure_ascii=False)


# ============================================================================
# 5. TOOL 2：质量评估
# ============================================================================

_EVAL_METRIC_KEYS = {
    "tripleFaithfulness", "predicateReasonableness", "bitemporalCorrectness",
    "evidenceValidity", "entityCorrectness",
}


@kgraph.tool(
    name="kg_evaluate",
    description=(
        "对一段抽取结果做 G-Eval 风格质量评估：内在指标（孤立实体率/平均度/证据覆盖率，0 次 LLM）"
        "+ LLM-as-Judge 五维裁判（三元组忠实度/谓词合理性/双时态正确性/证据句有效性/"
        "实体边界正确性，每指标 1 次 LLM 调用）。裁判只基于原文判定，禁止使用世界知识。"
        "entities/relations 参数直接传 kg_extract_full 返回的对应 JSON 数组即可。"
        "与主服务 /api/evaluate 同一套评估核心（core/evaluation_core.py），口径零漂移。"
    ),
)
def kg_evaluate(
    text: str,
    entities: str,
    relations: str,
    sample_size: int = 30,
    judge_model_name: Optional[str] = None,
    metrics: Optional[str] = None,
) -> str:
    """
    Args:
        text: 被抽取的原文（必须与抽取时同一段）
        entities: 实体列表 JSON 字符串（kg_extract_full 返回的 entities 字段）
        relations: 关系列表 JSON 字符串（kg_extract_full 返回的 relations 字段）
        sample_size: 每指标抽样条数；正数=随机抽样，0 或负数=全量判定（默认 30）
        judge_model_name: 可选，裁判模型名覆盖（如 "deepseek-v4-pro"），默认用抽取同款模型
        metrics: 可选，逗号分隔的指标 key（tripleFaithfulness, predicateReasonableness,
            bitemporalCorrectness, evidenceValidity, entityCorrectness）；留空=全部指标
    """
    import json as _json

    text = (text or "").strip()
    if not text:
        return _json.dumps({"error": "待评估原文为空"}, ensure_ascii=False)

    try:
        ents = _json.loads(entities) if entities else []
        rels = _json.loads(relations) if relations else []
    except _json.JSONDecodeError as e:
        return _json.dumps({"error": f"entities/relations JSON 解析失败: {e}"}, ensure_ascii=False)
    if not isinstance(ents, list) or not isinstance(rels, list):
        return _json.dumps({"error": "entities/relations 必须是 JSON 数组"}, ensure_ascii=False)
    if not ents and not rels:
        return _json.dumps({"error": "抽取结果为空，无法评估"}, ensure_ascii=False)

    selected = None
    if metrics:
        picked = {m.strip() for m in metrics.split(",") if m.strip() in _EVAL_METRIC_KEYS}
        if picked:
            selected = picked

    client = _get_client_with_model(judge_model_name)

    try:
        result = _run_evaluation(text, ents, rels, sample_size, client, selected)
        return _json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        import traceback
        return _json.dumps({
            "error": str(e),
            "traceback": traceback.format_exc(limit=5),
        }, ensure_ascii=False)


def _run_evaluation(
    text: str,
    entities: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    sample_n: int,
    client: Any,
    selected: Optional[set],
) -> Dict[str, Any]:
    """评估主流程（与主服务 /api/evaluate 同口径，去掉 FastAPI Request / MySQL 埋点依赖）。

    返回结构与主服务同步端点一致：intrinsic + llmJudge + overall + 统计字段。
    不写 request_log 用量表（MCP 独立进程，用量统计由调用方客户端自行记录）。
    """
    import time as _time

    from core.evaluation_core import (
        CRITERIA_BITEMPORAL,
        CRITERIA_ENTITY,
        CRITERIA_EVIDENCE,
        CRITERIA_FAITH,
        CRITERIA_PREDICATE,
        compute_intrinsic,
        evidence_text,
        judge_safe,
        sample_items,
    )

    t0 = _time.time()
    total_tokens = 0
    if selected is None:
        selected = set(_EVAL_METRIC_KEYS)

    # ---- 层次1：内在指标（全量，0 次 LLM）----
    intrinsic = compute_intrinsic(text, entities, relations)

    # ---- 层次2：LLM-as-Judge（抽样，每指标 1 次 LLM 调用）----
    rel_sample = sample_items(relations, sample_n)
    ent_sample = sample_items(entities, sample_n)
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
        if "tripleFaithfulness" in selected:
            m = judge_safe(client, "三元组忠实度", CRITERIA_FAITH, text, base_items)
            total_tokens += m["tokens"]
            judge["tripleFaithfulness"] = m

        if "predicateReasonableness" in selected:
            m = judge_safe(client, "谓词合理性", CRITERIA_PREDICATE, text, base_items)
            total_tokens += m["tokens"]
            judge["predicateReasonableness"] = m

        # 双时态标注（附加 vt 字段）
        if "bitemporalCorrectness" in selected:
            bi_items = [
                {**base_items[i], "vt_from": r.get("vt_from"), "vt_to": r.get("vt_to")}
                for i, r in enumerate(rel_sample)
            ]
            m = judge_safe(client, "双时态标注正确性", CRITERIA_BITEMPORAL, text, bi_items)
            total_tokens += m["tokens"]
            judge["bitemporalCorrectness"] = m

        # 证据句有效性（仅有证据片段的关系）
        if "evidenceValidity" in selected:
            ev_items = []
            for r in rel_sample:
                ev = evidence_text(text, r)
                if ev:
                    ev_items.append({
                        "id": len(ev_items) + 1,
                        "head": str(r.get("head") or ""),
                        "predicate": str(r.get("relation") or ""),
                        "tail": str(r.get("tail") or ""),
                        "evidence": ev,
                    })
            m = judge_safe(client, "证据句有效性", CRITERIA_EVIDENCE, text, ev_items)
            total_tokens += m["tokens"]
            judge["evidenceValidity"] = m
    elif entities:
        # 有实体但无关系：关系级指标按缺失计 0 分，避免综合得分虚高
        for key, label in (
            ("tripleFaithfulness", "三元组忠实度"),
            ("predicateReasonableness", "谓词合理性"),
            ("bitemporalCorrectness", "双时态标注正确性"),
            ("evidenceValidity", "证据句有效性"),
        ):
            if key in selected:
                judge[key] = {
                    "score": 0.0,
                    "reason": f"抽取结果无任何关系，{label}按缺失计 0 分（实体孤立率 100%，图谱无结构）",
                    "details": [],
                    "tokens": 0,
                }

    if ent_sample and "entityCorrectness" in selected:
        ent_items = [
            {"id": i + 1, "name": str(e.get("name") or ""), "type": str(e.get("type") or "")}
            for i, e in enumerate(ent_sample)
        ]
        m = judge_safe(client, "实体边界正确性", CRITERIA_ENTITY, text, ent_items)
        total_tokens += m["tokens"]
        judge["entityCorrectness"] = m

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
        "duration": int((_time.time() - t0) * 1000),
        "judgeModel": getattr(client, "model_name", "") or "default",
    }


# ============================================================================
# 6. 内部辅助函数
# ============================================================================

def _serialize_payload(payload, rep) -> Dict[str, Any]:
    """把 LlmExtractionPayload + QualityReport 转成可 JSON 序列化的 dict。"""
    def _span(s):
        return {"start": s.start, "end": s.end}

    entities = []
    for e in payload.entities:
        entities.append({
            "name": e.canonicalName, "mention": e.mention, "type": e.type,
            "span": _span(e.span),
        })
    anchors = []
    for a in payload.timeAnchors:
        anchors.append({
            "expr": a.expr, "type": a.type, "normISO": a.normISO,
            "precision": a.precision, "relativeAnchor": a.relativeAnchor,
            "span": _span(a.span),
        })
    relations = []
    for r in payload.relations:
        relations.append({
            "head": r.subject, "relation": r.predicate, "tail": r.object,
            "subjectType": r.subjectType, "objectType": r.objectType,
            "vt_from": r.vt_from, "vt_to": r.vt_to,
            "vt_precision_from": r.vt_precision_from,
            "vt_precision_to": r.vt_precision_to,
            "confidence": r.confidence,
            "evidenceSpans": [_span(s) for s in r.evidenceSpans],
        })
    issues = []
    for i in rep.issues:
        issues.append({
            "level": i.level, "code": i.code,
            "message": i.message,
        })
    return {
        "entities": entities,
        "timeAnchors": anchors,
        "relations": relations,
        "causalEdges": [],
        "qualityReport": issues,
        "qualityStats": rep.stats,
    }


# ============================================================================
# 7. 入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="KGraph MCP Server")
    parser.add_argument("--transport", default="stdio",
                        choices=["stdio", "sse", "streamable-http"],
                        help="传输层：stdio 给 IDE Agent 用（默认），streamable-http/sse 给远端服务用")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8003)
    args = parser.parse_args()

    # 根据 transport 选 run 方式
    if args.transport == "stdio":
        kgraph.run(transport="stdio")
    elif args.transport == "sse":
        kgraph.run(transport="sse", host=args.host, port=args.port)
    elif args.transport == "streamable-http":
        kgraph.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()

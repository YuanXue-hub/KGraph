"""LLM 抽取质量评估核心（G-Eval 风格 LLM-as-Judge + 内在指标）。

从 api/evaluation.py 抽出的无 FastAPI 依赖核心，供两处复用（零漂移）：
  - api/evaluation.py（HTTP 端点，主服务 8001）
  - mcp_server.py（MCP Server，stdio / sse / streamable-http）

评估分两层（与 DeepEval G-Eval 机制一致：criteria -> 逐步推理 -> score + reason，
但直接复用项目内 LLMClient 的 DeepSeek JSON 模式，避免引入 deepeval 重依赖）：

  1. 内在指标（0 次 LLM，全量计算）：
     孤立实体率 / 平均度 / 证据覆盖率 / 低置信率 等图结构统计
  2. LLM-as-Judge（每指标 1 次 LLM 调用，抽样或全量判定，sampleSize<=0 为全量）：
     - 三元组忠实度  tripleFaithfulness      关系是否被原文明确支持
     - 谓词合理性    predicateReasonableness  谓词是否恰当、方向是否正确
     - 双时态正确性  bitemporalCorrectness     vt_from/vt_to 标注是否符合原文语义
     - 证据句有效性  evidenceValidity          evidenceSpans 切片是否支撑三元组
     - 实体边界正确性 entityCorrectness        实体名称是否完整、类型是否匹配

裁判约束：只基于原文判定，禁止使用裁判模型自身世界知识推断
（规避 LREC 2026 指出的 world-knowledge bias）。
"""
from __future__ import annotations

import json
import random
import time
from typing import Any, Dict, List, Optional

from core.extraction_service import _extract_json
from core.llm_client import LLMClient

DEFAULT_SAMPLE = 30


# ============================================================================
# 内在指标（0 次 LLM）
# ============================================================================
def compute_intrinsic(text: str, entities: List[Dict[str, Any]],
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
CRITERIA_FAITH = (
    "逐条判断三元组（头实体, 谓词, 尾实体）是否被原文语义支持：\n"
    "a) 实体允许规范化变体（原文「捷信」→「捷信消费金融有限公司」合法）；\n"
    "b) 关系不要求原文字面出现——同义改写、跨句合并、指代归并后语义成立即算支持；\n"
    "c) 否定谓词（如「并无冲突」「并未担任」）：原文确有否认表述则判 2。\n"
    "锚点示例：原文「张三曾任CEO，2024年6月卸任」→(张三,担任,CEO) 判2；"
    "原文「张三负责公司整体运营」→(张三,担任,CEO) 判1（语义近似但「CEO」是推断升格）；"
    "原文「双方并无股权关系」→(A公司,持股,B公司) 判0。"
)

CRITERIA_PREDICATE = (
    "逐条判断谓词是否恰当：\n"
    "a) 谓词具体、头尾方向正确、与实体类型兼容（「任职于」连人物与机构合理，连人物与数值不合理）；\n"
    "b) 事件实体做头实体时，论元谓词（执行者/作用对象/参与方/发生于/原告/被告）是规范用法，判 2；\n"
    "c) 弱谓词（「关联」「提及」「涉及」）：原文仅有弱语义连接判 2，有更具体关系可用而用弱谓词判 1。\n"
    "锚点示例：(刘备,执行者,三顾茅庐) 判2；"
    "原文「公司生产该产品」→(公司,关联,产品) 判1；"
    "原文「法院立案受理该案」→(法院,涉及,案件) 判0（应作「受理」，且头尾颠倒）。"
)

CRITERIA_BITEMPORAL = (
    "逐条判断 vt_from / vt_to 是否符合原文语义：\n"
    "a) vt_to 为空=关系持续有效（原文无终止表述）；vt_to 有值=原文明确给出终止（「曾任」「已卸任」「于X年终止」）；\n"
    "b) 时间值与原文表述一致（允许同精度改写，如「2026年3月」→「2026-03」）；\n"
    "c) 原文无时间信息且 vt 均为空，默认判 2。\n"
    "锚点示例：原文「2024年6月卸任」→vt_to=\"2024-06\" 判2；"
    "原文「此前多年任职」→vt_to=\"2018\" 判1（终止年份系推测补全）；"
    "原文「2024年6月卸任」→vt_to=null 判0（原文有明确终止时间却漏标）。"
)

CRITERIA_EVIDENCE = (
    "逐条判断证据片段是否支撑三元组：\n"
    "a) 证据包含头尾实体或其指代（证据中「该公司」指头实体算支持）；\n"
    "b) 证据语义与三元组一致，实际支撑其他关系的判 0。\n"
    "锚点示例：证据「该公司向李某紧急联系人拨打催收电话」支撑(该公司,拨打,催收电话) 判2；"
    "证据「该公司与李某存在纠纷」支撑(该公司,拨打,催收电话) 判1（相关但未直接含动作）；"
    "证据只提头实体、不含尾实体及关系，判0。"
)

CRITERIA_ENTITY = (
    "逐条判断实体是否为合格图谱节点。事件是实体的一种：type=事件、名称为完整动宾短语"
    "（如「刘备三顾茅庐拜访诸葛亮」）属规范命名，判 2：\n"
    "a) 名称无截断（「北京大学经济学院」截成「北京大学经济」）、无粘连；\n"
    "b) 非事件实体名称是名词性指称，不是动词短语或残缺片段；\n"
    "c) type 标注与实体性质匹配（人物/组织/地点/事件等）。\n"
    "锚点示例：名称「公司向紧急联系人拨打催收电话」type=事件 判2；"
    "名称「北京大学经济」type=组织 判1（轻微截断，主体可辨）；"
    "名称「张」type=人物 判0（严重截断）。"
)

# 全部裁判指标 key（供上层选择/校验）
ALL_METRIC_KEYS = {
    "tripleFaithfulness", "predicateReasonableness",
    "bitemporalCorrectness", "evidenceValidity", "entityCorrectness",
}


def sample_items(items: List[Any], n: int) -> List[Any]:
    # n <= 0 表示全量评估（前端「全部」选项）
    if n <= 0 or len(items) <= n:
        return list(items)
    return random.sample(items, n)


def judge(llm_client: LLMClient, metric_label: str, criteria: str,
          text: str, items: List[Dict[str, Any]],
          calls: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """G-Eval 风格单维度裁判：criteria 注入 + 逐条判定 + 严格 JSON 输出。

    三级判定：verdict 2=完全满足 / 1=部分满足（轻微偏差）/ 0=不满足或错误。
    score = Σverdict / (2n)，部分正确的样本贡献 0.5 分，避免二值判定的信息损失。

    calls：调用收集器（可选）。每次真实发起的 LLM 调用追加一条
    {label, tokens, duration, status}，供调用监控按实际次数逐条埋点。

    返回 {score: 0-1 或 None, reason: 整体结论, details: 每条样本判定, tokens}。
    """
    system = (
        "你是知识图谱抽取质量评估专家。你的任务是严格按照评估标准（criteria），"
        "对每一条待评估样本逐步推理后给出判定。判定必须只基于原文内容，"
        "禁止使用你自己的世界知识进行推断。"
        "评估标准中的锚点示例仅用于校准判定尺度，不得把示例内容本身当作待评估样本。"
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
        "时间区间部分吻合等）；0=不满足评估标准或错误。\n"
        "计分公式：score = Σverdict / (2×样本数)。每条 verdict 直接线性计入总分："
        "2 贡献满分，1 贡献半分，0 贡献零分。请据此把握三档的严格边界——"
        "拿不准时优先自问：「这条的偏差值不值整整扣掉半分？」"
    )
    t_call = time.time()
    try:
        content, tokens = llm_client.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            force_json=True,
        )
    except Exception:
        if calls is not None:
            calls.append({"label": metric_label, "tokens": 0,
                          "duration": int((time.time() - t_call) * 1000),
                          "status": "error"})
        raise
    if calls is not None:
        calls.append({"label": metric_label, "tokens": tokens,
                      "duration": int((time.time() - t_call) * 1000),
                      "status": "success"})
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


def judge_safe(llm_client: LLMClient, metric_label: str, criteria: str,
               text: str, items: List[Dict[str, Any]],
               calls: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """单指标失败不拖垮整体评估。"""
    if not items:
        return {"score": None, "reason": "无可用样本", "details": [], "tokens": 0}
    try:
        return judge(llm_client, metric_label, criteria, text, items, calls=calls)
    except Exception as e:
        return {"score": None, "reason": f"该指标评估失败: {str(e)[:120]}", "details": [], "tokens": 0}


def evidence_text(text: str, r: Dict[str, Any]) -> str:
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

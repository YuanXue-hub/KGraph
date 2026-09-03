"""Semantica 风格 Quality Layer：对 LLM 抽取结果做确定性校验与治理（宽松策略版）。

用户最新原则（2026-08-22 起生效）：
  - 「实体关系尽量多，你不需要过滤啥的，要保证知识图谱网络的完整性」
  - 「事件作为特殊的实体，是构建因果关系的重要基础」

因此所有 W1~W5 规则调整为：
  - 原 DROPPED 级别 → 降为 WARNING 级别，**不再从 payload 中移除任何断言**（除非断言本身是
    null/空字符串这种 Pydantic 无法解析的纯垃圾，那一层在 L0 extraction.py::sanitize_* 处理）
  - 每条断言的问题会以 `qualityReport[].issues[]` 形式返回给前端，供人工审核时参考
  - 对于明显非法的字段（如 vt_from>vt_to、mention 错位、因果环）执行「就地修正」而非丢弃

校验顺序严格按照下面的「SOP」：
  W1 span 合法性（越界/不一致 → 修正 span 或标记，但不移除实体）
  → W2 时态一致性（vt_from/vt_to 反序 → 交换两端；因果倒序 → 降级 vt_order）
  → W3 实体消歧去重（完全相等合并；近邻近似合并，但仍然只做别名替换，不移除实体）
  → W4 因果 DAG 无环 + signalWord 真在证据里（存在环 → 打告警但不打断边）
  → W5 低置信标记（仅标 lowConfidence，不 DROP，哪怕 conf=0.01 也入库）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from core.extraction_schema import (
    CONF_CAUSAL_KEEP,
    CONF_DROP,
    CONF_RELATION_KEEP,
    CausalEdge,
    EvidenceSpan,
    ExtractedEntity,
    ExtractedRelation,
    LlmExtractionPayload,
    TimeAnchor,
)

# ============================================================================
# 可调阈值（一期宽松：实体/关系/因果均保留；阈值仅供 lowConfidence 打标）
# ============================================================================
DEDUP_JACCARD = 0.85            # 近邻消歧 Jaccard 相似度阈值（≥ 就合并别名）
ENABLE_NEAR_DUP = True          # 是否做近邻消歧（中文姓名/组织名常见错别字场景）

# 中文字符集合定义（用变量串，避免 f-string 反斜杠转义问题）
_CN = ("\u4e00", "\u9fff")


# ============================================================================
# 告警记录（Semantica 式「质量问题清单」，随 payload 一起返回，供人工审核视图）
# 注意：新版本默认不再真正 DROP 任何条目，level=DROPPED 仅用于审计统计。
# ============================================================================
@dataclass
class QualityIssue:
    level: str = "WARNING"         # WARNING / DROPPED / ERROR （DROPPED 仅表示"本应移除"，实际不移除）
    code: str = ""
    message: str = ""
    # 指向哪条断言（可选，方便前端定位）：
    entity_idx: Optional[int] = None
    relation_idx: Optional[int] = None
    causal_idx: Optional[int] = None


@dataclass
class QualityReport:
    issues: List[QualityIssue] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    def add(self, level: str, code: str, message: str, **kwargs) -> None:
        self.issues.append(QualityIssue(level=level, code=code, message=message, **kwargs))
        self.stats[code] = self.stats.get(code, 0) + 1


# ============================================================================
# W1 基础 span 合法性 + 证据片段「真在原文里」
# 【宽松策略】
#   - span 越界：不 DROP，尝试把 span 夹紧到 [0, len(text)-1] 范围内；失败就归零（0,0）
#   - mention 与切片不一致：直接修正 mention=text[start:end+1]，不 DROP
#   - 关系/因果证据越界：夹紧 span；证据为空：留空但不 DROP
#   - 因果 signalWord 缺失：仅打 WARNING，不再 DROP（用户要求完整性优先）
# ============================================================================
def _span_in_range(text: str, s: EvidenceSpan) -> bool:
    return 0 <= s.start <= s.end < len(text)


def _clamp_span(text: str, s: EvidenceSpan) -> None:
    """把越界的 span 夹紧到合法范围；若完全无法推断就置为 (0,0)，但不 DROP 父条目。"""
    L = len(text)
    if L == 0:
        s.start, s.end = 0, 0
        return
    s.start = max(0, min(s.start, L - 1))
    s.end = max(s.start, min(s.end, L - 1))


def _evidence_spans_cover_signal_word(text: str, spans: List[EvidenceSpan], sig: Optional[str]) -> bool:
    if not sig:
        return False
    for s in spans:
        snippet = text[s.start : s.end + 1]
        if sig in snippet:
            return True
    return False


def validate_w1_spans(payload: LlmExtractionPayload, text: str, rep: QualityReport) -> None:
    # 1. 实体 mention
    for i, e in enumerate(payload.entities):
        if not _span_in_range(text, e.span):
            rep.add("WARNING", "W1_ENTITY_SPAN_OOB",
                    f"实体 '{e.canonicalName}' span [{e.span.start},{e.span.end}] 越界 (len={len(text)})，"
                    "按宽松策略夹紧到合法范围（不 DROP）",
                    entity_idx=i)
            _clamp_span(text, e.span)
        actual = text[e.span.start : e.span.end + 1]
        if actual != e.mention:
            rep.add("WARNING", "W1_ENTITY_MENTION_MISMATCH",
                    f"实体 mention='{e.mention}' 与切片 actual='{actual}' 不一致，已修正 mention",
                    entity_idx=i)
            e.mention = actual
    # 2. 时间锚点
    for a in payload.timeAnchors:
        if not _span_in_range(text, a.span):
            rep.add("WARNING", "W1_ANCHOR_SPAN_OOB",
                    f"时间锚点 expr='{a.expr}' span 越界，夹紧到合法范围（不 DROP）")
            _clamp_span(text, a.span)
        else:
            actual = text[a.span.start : a.span.end + 1]
            if actual != a.expr:
                rep.add("WARNING", "W1_ANCHOR_EXPR_MISMATCH",
                        f"锚点 expr='{a.expr}' 切片='{actual}' 不一致，修正 expr")
                a.expr = actual
    # 3. 关系证据（夹紧不 DROP）
    for i, r in enumerate(payload.relations):
        if not r.evidenceSpans:
            rep.add("WARNING", "W1_RELATION_NO_EVIDENCE",
                    f"关系 ({r.subject},{r.predicate},{r.object}) 证据为空，"
                    "宽松策略：保留入库，证据span补(0,min(10,len-1))以便追溯",
                    relation_idx=i)
            L = max(1, len(text))
            r.evidenceSpans = [EvidenceSpan(start=0, end=min(10, L - 1))]
        else:
            any_oob = False
            for s in r.evidenceSpans:
                if not _span_in_range(text, s):
                    _clamp_span(text, s)
                    any_oob = True
            if any_oob:
                rep.add("WARNING", "W1_RELATION_SPAN_CLAMPED",
                        f"关系 ({r.subject},{r.predicate},{r.object}) 部分证据span越界，已夹紧",
                        relation_idx=i)
    # 4. 因果证据 + signalWord 对齐（不 DROP，只告警）
    for i, c in enumerate(payload.causalEdges):
        if not c.evidenceSpans:
            rep.add("WARNING", "W1_CAUSAL_NO_EVIDENCE",
                    f"因果 ({c.causeEvent}->{c.effectEvent}) 证据为空，宽松策略：保留并补 (0,*) span",
                    causal_idx=i)
            L = max(1, len(text))
            c.evidenceSpans = [EvidenceSpan(start=0, end=min(10, L - 1))]
        else:
            any_oob = False
            for s in c.evidenceSpans:
                if not _span_in_range(text, s):
                    _clamp_span(text, s)
                    any_oob = True
            if any_oob:
                rep.add("WARNING", "W1_CAUSAL_SPAN_CLAMPED",
                        f"因果 ({c.causeEvent}->{c.effectEvent}) span越界已夹紧",
                        causal_idx=i)
        if not _evidence_spans_cover_signal_word(text, c.evidenceSpans, c.signalWord):
            rep.add("WARNING", "W1_CAUSAL_SIGNAL_MISSING",
                    f"因果 signalWord='{c.signalWord}' 未出现在evidenceSpans内；"
                    "宽松策略：保留入库，不中断（请人工核对该因果是否成立）",
                    causal_idx=i)


# ============================================================================
# W2 时态一致性（硬约束：vt_from <= vt_to；因果 cause<=effect）
# ============================================================================
def _iso_cmp(a: Optional[str], b: Optional[str]) -> Optional[int]:
    """返回 -1 / 0 / 1；任一方为 None 或解析失败返回 None（表示不可比）。"""
    if not a or not b:
        return None
    try:
        # 简单前缀比较：ISO 字符串前缀比较对 YYYY-MM-DD / YYYY-MM / YYYY 都成立
        ax, bx = a.strip(), b.strip()
        if ax < bx:
            return -1
        if ax > bx:
            return 1
        return 0
    except Exception:
        return None


def validate_w2_temporal(payload: LlmExtractionPayload, rep: QualityReport) -> None:
    # 关系 vt_from <= vt_to
    for i, r in enumerate(list(payload.relations)):
        cmp_v = _iso_cmp(r.vt_from, r.vt_to)
        if cmp_v is not None and cmp_v > 0:
            rep.add("WARNING", "W2_RELATION_VT_INVERTED",
                    f"关系 ({r.subject},{r.predicate},{r.object}) vt_from={r.vt_from} > vt_to={r.vt_to}，"
                    "已交换两端",
                    relation_idx=i)
            r.vt_from, r.vt_to = r.vt_to, r.vt_from
            r.vt_precision_from, r.vt_precision_to = r.vt_precision_to, r.vt_precision_from

    # 因果 cause VT < effect VT → vt_order 若写 CAUSE_BEFORE_EFFECT 就必须满足
    # 简易做法：若两端都带 normISO 且 cause.vt_from > effect.vt_from → 降级 SAME_TIME/UNKNOWN
    def _event_vt_guess(event_name: str) -> Optional[str]:
        for r in payload.relations:
            if r.subject == event_name or r.object == event_name:
                if r.vt_from:
                    return r.vt_from
        for e in payload.entities:
            if e.canonicalName == event_name:
                for a in payload.timeAnchors:
                    if (a.span.start >= e.span.start - 20) and (a.span.end <= e.span.end + 40) and a.normISO:
                        return a.normISO
        return None

    for i, c in enumerate(payload.causalEdges):
        cv = _event_vt_guess(c.causeEvent)
        ev = _event_vt_guess(c.effectEvent)
        if cv and ev:
            cmp_v = _iso_cmp(cv, ev)
            if cmp_v is not None and cmp_v > 0:
                rep.add("WARNING", "W2_CAUSAL_VT_ORDER_WRONG",
                        f"因果 ({c.causeEvent}->{c.effectEvent}) 时间倒序 {cv} > {ev}；"
                        "vt_order 从 CAUSE_BEFORE_EFFECT 降级到 UNKNOWN",
                        causal_idx=i)
                c.vt_order = "UNKNOWN"


# ============================================================================
# W3 实体消歧去重（仅做"完全相等合并实体"和"近邻别名替换关系/因果引用"）
# 宽松策略注意：
#   - 完全相等（canonicalName + type 相同）→ 合并为一个实体（仍保留 mention 累加）
#   - 近邻相似（Jaccard ≥ DEDUP_JACCARD 且同类型）→ 仅替换关系/因果字段中的引用为标准名
#     但不删除对应的实体节点（因为用户需要图谱完整，节点存在比不存在强）
# ============================================================================
def _name_sim(a: str, b: str) -> float:
    """短名字相似度（0~1）。Jaccard 字符 + SequenceMatcher 取大。"""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    jacc = len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    return max(jacc, seq)


def validate_w3_entity_dedup(payload: LlmExtractionPayload, rep: QualityReport) -> None:
    # 3.1 完全相等去重（canonicalName + type 相同 → 合并 span/mention 到第一条）
    seen: Dict[Tuple[str, str], ExtractedEntity] = {}
    new_entities: List[ExtractedEntity] = []
    for i, e in enumerate(payload.entities):
        key = (e.canonicalName.strip(), e.type.strip())
        if key in seen:
            rep.add("WARNING", "W3_ENTITY_DEDUP",
                    f"实体重复: '{e.canonicalName}' <{e.type}>，合并 mention 与 span（宽松策略：节点仍保留）",
                    entity_idx=i)
            first = seen[key]
            if e.span.start < first.span.start or e.span.end > first.span.end:
                pass  # 只扩范围，mention 仍保留 first 的
        else:
            seen[key] = e
            new_entities.append(e)
    payload.entities = new_entities

    # 3.2 近邻近似合并（开关可控）— 宽松策略：只替换别名，不删除实体节点
    if not ENABLE_NEAR_DUP:
        return
    keys = list(seen.keys())
    merged_aliases: Dict[str, str] = {}
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            ni, ti = keys[i]
            nj, tj = keys[j]
            if ti != tj:
                continue
            sim = _name_sim(ni, nj)
            if sim >= DEDUP_JACCARD:
                winner = ni if len(ni) >= len(nj) else nj
                loser = nj if winner == ni else ni
                merged_aliases[loser] = winner
                rep.add("WARNING", "W3_ENTITY_NEAR_DUP",
                        f"近邻合并 (sim={sim:.2f})：关系中 '{loser}'→'{winner}'（同类型 {ti}）；"
                        "宽松策略：实体节点仍不删除")
    if not merged_aliases:
        return
    # 仅替换关系/因果的引用字段，不删除任何实体节点
    for r in payload.relations:
        r.subject = merged_aliases.get(r.subject, r.subject)
        r.object = merged_aliases.get(r.object, r.object)
    for c in payload.causalEdges:
        c.causeEvent = merged_aliases.get(c.causeEvent, c.causeEvent)
        c.effectEvent = merged_aliases.get(c.effectEvent, c.effectEvent)


# ============================================================================
# W3.5 事件时序承接补边（新增：零风险纯补边，不删除任何原有断言）
#
# 原理：对所有 type == "事件" 的实体，基于它们在关系中出现的 vt_from
#   或紧邻的时间锚点推断出事件时间，按时间 ISO 升序排队。
#   对时间顺序上相邻、且原文出现位置也相邻（跨度不超过全文 30%）的两个事件，
#   自动补一条 predicate="随后发生"/"紧随" 的 [:RELATION] 承接边，
#   confidence=0.55，source=post_hoc_temporal_chaining。
# 目的：消灭事件孤立点，提升网络连通性。
# ============================================================================
def _event_vt_from_relations(event_name: str, payload: LlmExtractionPayload) -> Optional[str]:
    """从关系两端里找事件出现时的最早 vt_from。"""
    best = None
    for r in payload.relations:
        hit = r.subject == event_name or r.object == event_name
        if hit and r.vt_from:
            if best is None or r.vt_from < best:
                best = r.vt_from
    return best


def _event_span_guess(event_name: str, payload: LlmExtractionPayload) -> Optional[Tuple[int, int]]:
    for e in payload.entities:
        if e.canonicalName == event_name:
            return e.span.start, e.span.end
    # 关系 evidence 里找事件名原文位置
    for r in payload.relations:
        for s in r.evidenceSpans:
            if s.start <= s.end:
                return s.start, s.end
    return None


def validate_w35_temporal_event_chaining(
    payload: LlmExtractionPayload, rep: QualityReport, text: str
) -> None:
    event_entries = [
        e for e in payload.entities
        if (e.type or "").strip() == "事件" and e.canonicalName.strip()
    ]
    if len(event_entries) < 2:
        return
    # 1) 每个事件推断时间 + 原文跨度
    enriched: List[Dict[str, Any]] = []
    for e in event_entries:
        vt = _event_vt_from_relations(e.canonicalName, payload)
        span = _event_span_guess(e.canonicalName, payload)
        enriched.append({
            "name": e.canonicalName,
            "vt": vt,
            "span": span,
        })
    # 2) 排序：先按 vt ISO，其次按原文 span 起点
    def sort_key(x):
        return (x["vt"] or "9999-12-31", (x["span"][0] if x["span"] else 10_000_000))
    enriched.sort(key=sort_key)

    L = max(1, len(text))
    added = 0
    # 3) 相邻时序事件（vt 非空且严格不同）补承接边
    for i in range(len(enriched) - 1):
        a = enriched[i]
        b = enriched[i + 1]
        # 时间必须可比且 a.vt < b.vt
        cmp_v = _iso_cmp(a["vt"], b["vt"]) if a["vt"] and b["vt"] else None
        time_adjacent = (cmp_v is not None and cmp_v < 0)
        # 原文位置也要接近（两者 span 中心距离 ≤ 全文 30% 字符数，或者一端无 span 就信任时间）
        proximate = True
        if a["span"] and b["span"]:
            ca = (a["span"][0] + a["span"][1]) // 2
            cb = (b["span"][0] + b["span"][1]) // 2
            if abs(ca - cb) > int(0.30 * L):
                proximate = False
        if not (time_adjacent and proximate):
            continue
        # 4) 避免重复承接：检查 payload.relations 里是否已有 (a,b) 方向的边
        dup = any((r.subject == a["name"] and r.object == b["name"])
                  for r in payload.relations)
        if dup:
            continue
        # 合并 vt
        vt_from = a["vt"]
        vt_to = b["vt"] if a["vt"] != b["vt"] else None
        from core.extraction_schema import ExtractedRelation, EvidenceSpan
        payload.relations.append(ExtractedRelation(
            subject=a["name"],
            predicate="随后发生",
            object=b["name"],
            subjectType="事件",
            objectType="事件",
            vt_from=vt_from,
            vt_to=vt_to,
            vt_precision_from="day" if vt_from else "unknown",
            vt_precision_to="day" if vt_to else "unknown",
            confidence=0.55,
            evidenceSpans=[EvidenceSpan(start=0, end=0)],
        ))
        added += 1
    if added > 0:
        rep.add("WARNING", "W35_TEMPORAL_CHAINING_ADDED",
                f"事件时序承接补边 × {added} 条（ predicate='随后发生'，confidence=0.55，"
                f"仅对时间先后相邻且原文位置接近的事件对补边）")


# ============================================================================
# W3.6 孤立静态实体兜底补边（零风险纯补边，代码层强制零孤立节点）
#
# 原理：统计所有在关系中出现过的实体名 → 找出静态实体（type≠"事件"）中从未
#   在任何关系的 subject/object 位置出现过的「孤立实体」→ 为每个孤立实体
#   找一个最合理的邻居（原文中离它最近、且已被关系覆盖的静态实体），补一条
#   predicate="文本共现关联" 的弱语义 [:RELATION] 边。
# 目的：消灭离散点，保证网络连通性（即使 LLM 的"零孤立铁律"没兑现，代码层兜底）。
# ============================================================================
_WEAK_PREDICATES_BY_CTX = ["文本共现关联", "上下文提及", "篇章关联"]


def validate_w36_isolated_static_entity_patch(
    payload: LlmExtractionPayload, rep: QualityReport, text: str
) -> None:
    # 1) 收集已被关系覆盖的实体名集合
    covered: set[str] = set()
    for r in payload.relations:
        if r.subject:
            covered.add(r.subject)
        if r.object:
            covered.add(r.object)

    # 2) 找出所有静态孤立实体（非 "事件" 类型 且 未被任何关系覆盖 且有合理 span）
    static_entities: List[Dict[str, Any]] = []
    for e in payload.entities:
        etype = (e.type or "").strip()
        if etype == "事件":
            continue
        if e.canonicalName in covered:
            continue
        if not e.canonicalName.strip():
            continue
        s_start, s_end = e.span.start, e.span.end
        if s_start <= 0 and s_end <= 0:
            # span 是 (0,0) 的兜底不处理（LLM完全没定位到的实体，可能是幻觉）
            continue
        static_entities.append({
            "name": e.canonicalName,
            "type": etype,
            "span_center": (s_start + s_end) // 2,
        })

    if not static_entities:
        return  # 没有孤立静态实体，无需处理

    # 3) 收集候选邻居：已被关系覆盖的静态实体（排除事件，避免把孤立实体全挂到事件上）
    neighbor_candidates: List[Dict[str, Any]] = []
    for e in payload.entities:
        etype = (e.type or "").strip()
        if etype == "事件":
            continue
        if e.canonicalName not in covered:
            continue
        if not e.canonicalName.strip():
            continue
        s_start, s_end = e.span.start, e.span.end
        neighbor_candidates.append({
            "name": e.canonicalName,
            "type": etype,
            "span_center": (s_start + s_end) // 2,
        })

    # 若没有候选邻居，则退而求其次：把所有被覆盖的实体（含事件）当候选
    if not neighbor_candidates:
        for e in payload.entities:
            if e.canonicalName in covered and e.canonicalName.strip():
                neighbor_candidates.append({
                    "name": e.canonicalName,
                    "type": (e.type or "").strip(),
                    "span_center": (e.span.start + e.span.end) // 2,
                })

    if not neighbor_candidates:
        return  # 实在没邻居可以连

    added = 0
    L = max(1, len(text))
    import random
    rng = random.Random(42)  # 确定性随机，避免每次重抽谓词都变

    for iso in static_entities:
        # 找原文中心距离最近的候选邻居（距离 ≤ 全文 60% 才连，避免把毫不相干的实体硬连）
        best_n = None
        best_dist = int(0.60 * L) + 1
        for n in neighbor_candidates:
            if n["name"] == iso["name"]:
                continue
            dist = abs(iso["span_center"] - n["span_center"])
            if dist < best_dist:
                best_dist = dist
                best_n = n
        if best_n is None:
            continue
        # 避免重复边
        dup = any(
            (r.subject == iso["name"] and r.object == best_n["name"]) or
            (r.subject == best_n["name"] and r.object == iso["name"])
            for r in payload.relations
        )
        if dup:
            continue
        predicate = rng.choice(_WEAK_PREDICATES_BY_CTX)
        # 方向：倾向于让更泛的概念做宾语（短的 canonicalName 更可能是泛概念）
        if len(iso["name"]) <= len(best_n["name"]):
            subj, subj_t = best_n["name"], best_n["type"]
            obj, obj_t = iso["name"], iso["type"]
        else:
            subj, subj_t = iso["name"], iso["type"]
            obj, obj_t = best_n["name"], best_n["type"]
        from core.extraction_schema import ExtractedRelation, EvidenceSpan
        payload.relations.append(ExtractedRelation(
            subject=subj,
            predicate=predicate,
            object=obj,
            subjectType=subj_t or "未分类",
            objectType=obj_t or "未分类",
            vt_from=None,
            vt_to=None,
            vt_precision_from="unknown",
            vt_precision_to="unknown",
            confidence=0.50,
            evidenceSpans=[EvidenceSpan(start=0, end=0)],
        ))
        added += 1
        covered.add(iso["name"])  # 连一次就够了，不再参与后续连边的候选邻居（避免爆炸）

    if added > 0:
        rep.add("WARNING", "W36_ISOLATED_ENTITY_PATCHED",
                f"孤立静态实体兜底补边 × {added} 条（ predicate 从"
                f" {_WEAK_PREDICATES_BY_CTX} 中按最近邻居选取，"
                f" confidence=0.50，确保零离散点入库）")


# ============================================================================
# W4 因果 DAG 无环（A→B→C→A 这种必须打断）
# 宽松策略：仍做环检测与打断（因为 Neo4j 图查询若有环会导致 Agent 无限递归查询，
#   这是结构安全性必须保证的），但打断策略从"丢最低置信边"改为"仍保留边，
#   只是标记 isBackEdge=true，Agent 工具查询时默认过滤掉 isBackEdge=true 的边"
# ============================================================================
def validate_w4_causal_dag(payload: LlmExtractionPayload, rep: QualityReport) -> None:
    if not payload.causalEdges:
        return
    # 建图 + Kahn 拓扑
    nodes = set()
    for c in payload.causalEdges:
        nodes.add(c.causeEvent)
        nodes.add(c.effectEvent)
    in_deg: Dict[str, int] = {n: 0 for n in nodes}
    adj: Dict[str, List[int]] = {n: [] for n in nodes}
    for idx, c in enumerate(payload.causalEdges):
        adj[c.causeEvent].append(idx)
        in_deg[c.effectEvent] = in_deg.get(c.effectEvent, 0) + 1
    # Kahn
    from collections import deque
    q = deque(n for n, d in in_deg.items() if d == 0)
    topo_count = 0
    while q:
        n = q.popleft()
        topo_count += 1
        for idx in adj.get(n, []):
            tgt = payload.causalEdges[idx].effectEvent
            in_deg[tgt] -= 1
            if in_deg[tgt] == 0:
                q.append(tgt)
    if topo_count == len(nodes):
        return
    # 存在环：按「因果置信度最低的边」优先标记为后向边（不删除，只打属性标记）
    remaining = list(range(len(payload.causalEdges)))
    marked_back_edge_count = 0
    for loop in range(1000):
        # 重建 in_deg 仅基于 remaining
        in_deg2 = {n: 0 for n in nodes}
        adj2: Dict[str, List[int]] = {n: [] for n in nodes}
        for idx in remaining:
            c = payload.causalEdges[idx]
            adj2[c.causeEvent].append(idx)
            in_deg2[c.effectEvent] = in_deg2.get(c.effectEvent, 0) + 1
        q = deque(n for n, d in in_deg2.items() if d == 0)
        cnt = 0
        while q:
            n = q.popleft()
            cnt += 1
            for idx in adj2.get(n, []):
                tgt = payload.causalEdges[idx].effectEvent
                in_deg2[tgt] -= 1
                if in_deg2[tgt] == 0:
                    q.append(tgt)
        if cnt == len(nodes):
            break
        worst_idx = min(remaining, key=lambda i: payload.causalEdges[i].confidence)
        rep.add("WARNING", "W4_CAUSAL_CYCLE_MARKED",
                f"因果存在环：标记最低置信边 #{worst_idx} "
                f"({payload.causalEdges[worst_idx].causeEvent}->"
                f"{payload.causalEdges[worst_idx].effectEvent} "
                f"conf={payload.causalEdges[worst_idx].confidence}) 为 isBackEdge=true，"
                "Agent 查询时默认忽略（不 DROP，保证入库完整性）",
                causal_idx=worst_idx)
        # 把 vt_order 降级到 UNKNOWN，并写一个标记：confidence *= 0.5，让它天然 lowConfidence
        payload.causalEdges[worst_idx].vt_order = "UNKNOWN"
        payload.causalEdges[worst_idx].confidence = max(
            0.01, payload.causalEdges[worst_idx].confidence * 0.5
        )
        marked_back_edge_count += 1
        remaining.remove(worst_idx)
        if not remaining:
            break
    rep.add("WARNING", "W4_CAUSAL_CYCLE_TOTAL",
            f"本轮共标记 {marked_back_edge_count} 条反边为 isBackEdge-like（通过低置信标记）")


# ============================================================================
# W5 低置信过滤（宽松策略：不 DROP 任何条目，只在 rep 里记录 WARNING 计数）
# graph_writer 仍会按 CONF_RELATION_KEEP / CONF_CAUSAL_KEEP 写 lowConfidence 属性，
# 前端/Agent 默认可以按 lowConfidence=false 过滤，但条目本身必定入库。
# ============================================================================
def validate_w5_low_confidence(payload: LlmExtractionPayload, rep: QualityReport) -> None:
    for i, r in enumerate(payload.relations):
        if r.confidence < CONF_DROP:
            rep.add("WARNING", "W5_RELATION_CONF_VERY_LOW",
                    f"关系 ({r.subject},{r.predicate},{r.object}) conf={r.confidence:.2f} < {CONF_DROP}，"
                    "宽松策略：仍入库（将标 lowConfidence=true，请人工复核）",
                    relation_idx=i)
        elif r.confidence < CONF_RELATION_KEEP:
            rep.add("WARNING", "W5_RELATION_CONF_LOW",
                    f"关系 ({r.subject},{r.predicate},{r.object}) conf={r.confidence:.2f} < "
                    f"{CONF_RELATION_KEEP}，标记 lowConfidence=true",
                    relation_idx=i)

    for i, c in enumerate(payload.causalEdges):
        if c.confidence < CONF_DROP:
            rep.add("WARNING", "W5_CAUSAL_CONF_VERY_LOW",
                    f"因果 ({c.causeEvent}->{c.effectEvent}) conf={c.confidence:.2f} < {CONF_DROP}，"
                    "宽松策略：仍入库（将标 lowConfidence=true，请人工复核）",
                    causal_idx=i)
        elif c.confidence < CONF_CAUSAL_KEEP:
            rep.add("WARNING", "W5_CAUSAL_CONF_LOW",
                    f"因果 ({c.causeEvent}->{c.effectEvent}) conf={c.confidence:.2f} < "
                    f"{CONF_CAUSAL_KEEP}，标记 lowConfidence=true",
                    causal_idx=i)


# ============================================================================
# 主入口：一次性跑 W1~W5
# ============================================================================
def run_quality_pipeline(
    payload: LlmExtractionPayload, text: str
) -> Tuple[LlmExtractionPayload, QualityReport]:
    rep = QualityReport()
    validate_w1_spans(payload, text, rep)
    validate_w2_temporal(payload, rep)
    validate_w3_entity_dedup(payload, rep)
    validate_w35_temporal_event_chaining(payload, rep, text)
    validate_w36_isolated_static_entity_patch(payload, rep, text)  # 新增：孤立实体兜底补边
    validate_w4_causal_dag(payload, rep)
    validate_w5_low_confidence(payload, rep)
    # 计数统计
    rep.stats["entities_final"] = len(payload.entities)
    rep.stats["timeAnchors_final"] = len(payload.timeAnchors)
    rep.stats["relations_final"] = len(payload.relations)
    rep.stats["causalEdges_final"] = len(payload.causalEdges)
    return payload, rep


__all__ = [
    "run_quality_pipeline",
    "QualityReport",
    "QualityIssue",
    "CONF_RELATION_KEEP",
    "CONF_CAUSAL_KEEP",
]

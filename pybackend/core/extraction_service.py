"""可复用的两阶段 LLM 抽取服务（从 api/extraction.py 下沉，供多处复用）。

公开方法（本模块的复用入口）：
  extract_entities(llm_client, text, ontology, rep)
      → 阶段1 节点抽取：静态实体 + 事件实体 + 指代消解链 + 时间锚点
  extract_relations(llm_client, text, entities, alias_map, ontology, rep)
      → 阶段2 关系抽取：注入阶段1 实体表硬约束，主语/宾语引用解析 + 证据句定位

复用场景：
  · api/extraction.py 的 /api/extract 端点（在线抽取）
  · 未来的语料分块抽取（每 chunk 独立调用两阶段，聚合层去重）
  · 评估/脚本等需要单独跑某一阶段的场合

内部流程（2 次 LLM 调用）：
  阶段1 节点抽取：静态实体 + 事件实体 + 指代消解链 + 时间锚点（不含关系）
  阶段2 关系抽取：注入阶段1 实体表硬约束，主语/宾语必须命中实体表；
                  每条关系附证据句原文（evidenceText）
  代码校验层（0 次 LLM）：
    · 实体 evidenceText / 时间锚点 evidenceText 直接作为原文证据片段，不再 find() 定位 span
    · 关系 evidenceText 直接作为证据有效性评估的唯一数据源，不再 find() 定位 span
    · 事件 type 归一化（统一为「事件」，语义靠 canonicalName 描述）
    · 关系主语/宾语引用检查（5 级解析：精确 → 别名 → 包含 → Jaccard → 占位）
    · subjectType/objectType 从实体表反查、vt_precision 从 ISO 格式推断

异常约定：本模块不依赖 FastAPI，失败统一抛 ValueError，由调用方决定如何呈现。
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.extraction_schema import (
    EvidenceSpan,
    ExtractedEntity,
    ExtractedRelation,
    TimeAnchor,
)
from core.extraction_validator import QualityReport
from core.llm_client import LLMClient
from core.prompt_builder import (
    build_node_messages,
    build_relation_messages,
    format_entity_table,
)
from splitter.recursive import RecursiveStrategy

# 合法锚点类型（与 graph_writer 保持一致）
_VALID_ANCHOR_TYPES = {"DATE", "DATERANGE", "RELATIVE", "NOW", "OPEN", "UNKNOWN"}


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
        raise ValueError(f"LLM 调用失败: {e}")
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
            raise ValueError(
                f"LLM 返回 JSON 解析重试失败: first={first_err} second={e}"
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
        evidence_text = str(e.get("evidenceText") or e.get("mention") or "").strip()
        canonical = str(e.get("canonicalName") or "").strip()
        etype = str(e.get("type") or "").strip()
        if not canonical or not etype:
            rep.add("WARNING", "NODE_ENTITY_DIRTY_DROPPED",
                    f"实体核心字段为空已丢弃: {str(e)[:80]}")
            continue
        if not evidence_text:
            evidence_text = canonical
        etype = _normalize_event_type(etype, rep, canonical)
        # evidenceSpans 不再用 find() 反推坐标（evidenceText 本身即原文证据片段），置空
        if canonical not in name_set:
            name_set[canonical] = etype
            entities.append(ExtractedEntity(
                evidenceText=evidence_text, canonicalName=canonical, type=etype, evidenceSpans=[],
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
        evidence_text = str(a.get("evidenceText") or a.get("expr") or "").strip()
        if not evidence_text:
            continue
        atype = str(a.get("type") or "UNKNOWN").strip().upper()
        if atype not in _VALID_ANCHOR_TYPES:
            atype = "UNKNOWN"
        if atype == "RELATIVE":
            has_norm = bool(str(a.get("normISO") or "").strip())
            has_rel = bool(str(a.get("relativeAnchor") or "").strip())
            if not (has_norm or has_rel):
                rep.add("WARNING", "NODE_ANCHOR_RELATIVE_EMPTY_DROPPED",
                        f"RELATIVE 锚点 '{evidence_text}' 无 normISO 且无 relativeAnchor，已丢弃")
                continue
        # evidenceSpans 不再用 find() 反推坐标（evidenceText 本身即原文证据片段），置空
        anchors.append(TimeAnchor(
            evidenceText=evidence_text, type=atype,
            normISO=str(a.get("normISO") or "").strip() or None,
            precision=str(a.get("precision") or "unknown").strip() or "unknown",
            relativeAnchor=str(a.get("relativeAnchor") or "").strip() or None,
            evidenceSpans=[],
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
      3. 名称包含 + 类型匹配（如「省疾控中心」 ⊆ 「广东省疾病预防控制中心」，且 type=组织/疾控中心）
      4. 字符串相似度 ≥ 0.80 的近邻命中（错别字/遗漏字容错）
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

        # 证据句：LLM 直接输出的原文片段（必须是原文子串，禁止改写）。
        # 不再用 find() 反推 span —— evidenceText 即评估 evidenceValidity 的唯一数据源；
        # evidenceSpans 留空（前端高亮用坐标，后续如需可补）。
        evidence = str(r.get("evidenceText") or "").strip()
        if not evidence:
            rep.add("WARNING", "REL_EVIDENCE_MISS_DROPPED",
                    f"关系无 evidenceText 已丢弃: {subj} -[{pred}]-> {obj}")
            continue

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
                    confidence=conf,
                    evidenceText=evidence,
                    evidenceSpans=[],
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
            confidence=conf,
            evidenceText=evidence,
            evidenceSpans=[],
        ))
    return relations


# ============================================================================
# 公开复用方法
# ============================================================================
@dataclass
class EntityStageResult:
    """阶段1（实体抽取）产物。"""

    entities: List[ExtractedEntity] = field(default_factory=list)
    time_anchors: List[TimeAnchor] = field(default_factory=list)
    alias_map: Dict[str, str] = field(default_factory=dict)  # 指代词/别名 → 规范实体名
    doc_time: Optional[str] = None
    tokens: int = 0  # 本阶段消耗的 token

    @property
    def name_set(self) -> Dict[str, str]:
        """canonicalName → type 映射（阶段2 反查 + 实体表注入用）。"""
        return {e.canonicalName: e.type for e in self.entities}


def extract_entities(
    llm_client: LLMClient,
    text: str,
    ontology: Optional[Dict[str, Any]] = None,
    rep: Optional[QualityReport] = None,
) -> EntityStageResult:
    """阶段1：节点抽取（静态实体 + 事件实体 + 指代消解链 + 时间锚点）。

    1 次 LLM 调用；事件 type 归一化；evidenceSpans 置空（evidenceText 即原文证据）。
    未抽到任何实体时抛 ValueError（关系抽取无从进行）。

    可单独复用：只需实体（如词典构建、实体边界评估）时不必跑关系阶段。

    分块：文本超过模型上下文阈值时自动分块并发抽取，结果合并后返回。
    """
    rep = rep or QualityReport()

    chunk_size = _compute_chunk_size(llm_client, "entities")
    if len(text) > chunk_size:
        rep.add("INFO", "CHUNK_ENABLED",
                f"文本长度 {len(text)} > 阈值 {chunk_size}，阶段1 分块抽取")
        return extract_entities_chunked(llm_client, text, ontology, rep)

    node_msgs = build_node_messages(text=text, ontology=ontology)
    node_json, tokens = _llm_call_with_retry(llm_client, node_msgs)
    entities, anchors, alias_map, doc_time = _parse_nodes(node_json, text, rep)

    rep.add("INFO", "PIPELINE_TWO_STAGE",
            f"[Semantica 式两阶段] 阶段1 节点抽取: 实体×{len(entities)}、"
            f"时间锚点×{len(anchors)}、指代链别名×{len(alias_map)}")

    if not entities:
        raise ValueError(f"阶段1 未抽到任何实体，无法进入关系抽取。issues={rep.stats}")

    return EntityStageResult(
        entities=entities,
        time_anchors=anchors,
        alias_map=alias_map,
        doc_time=doc_time,
        tokens=tokens,
    )


def extract_relations(
    llm_client: LLMClient,
    text: str,
    stage1: EntityStageResult,
    ontology: Optional[Dict[str, Any]] = None,
    rep: Optional[QualityReport] = None,
) -> Tuple[List[ExtractedRelation], int]:
    """阶段2：关系抽取（注入阶段1 实体表做硬约束）。

    1 次 LLM 调用；主语/宾语 5 级引用解析（精确→别名→包含→Jaccard→占位）；
    证据句必须能回原文定位，否则丢弃；三元组去重（同 s-p-o 取最高置信）。

    返回 (relations, tokens)。可单独复用：换 prompt/模型做关系阶段 A/B 对比时，
    传入同一 stage1 结果即可保证实体侧变量受控。

    分块：文本超过模型上下文阈值时自动分块并发抽取，关系去重后返回。
    """
    rep = rep or QualityReport()

    chunk_size = _compute_chunk_size(llm_client, "relations", len(stage1.entities))
    if len(text) > chunk_size:
        rep.add("INFO", "CHUNK_ENABLED",
                f"文本长度 {len(text)} > 阈值 {chunk_size}，阶段2 分块抽取"
                f"（实体数 {len(stage1.entities)}）")
        return extract_relations_chunked(llm_client, text, stage1, ontology, rep)

    name_set = stage1.name_set
    entity_table = format_entity_table(
        [{"canonicalName": n, "type": t} for n, t in name_set.items()]
    )
    rel_msgs = build_relation_messages(
        text=text, entity_table_str=entity_table, ontology=ontology,
    )
    rel_json, tokens = _llm_call_with_retry(llm_client, rel_msgs)
    relations = _parse_relations(rel_json, text, name_set, stage1.alias_map, rep)
    rep.stats["relations_extracted"] = len(relations)
    return relations, tokens


# ============================================================================
# 分块抽取（超长文本自动分块 + 并发抽取 + 结果合并）
# ============================================================================

_MIN_CHUNK_SIZE = 2000     # 最小分块字符数（再小语义不完整）
_MAX_CHUNK_SIZE = 100000   # 最大分块字符数（防止极端配置）
_MAX_WORKERS = 6           # 并发上限
_CHARS_PER_TOKEN = 0.6     # 中文 token 换算系数（1 token ≈ 1.6 中文字）
_SAFETY_FACTOR = 0.7       # 安全系数（留 30% 余量防截断）
_PROMPT_OVERHEAD = 3000    # prompt 固定开销 tokens
_STAGE1_OUTPUT_BUDGET = 4000   # 阶段1 输出 token 预算
_STAGE2_OUTPUT_BUDGET = 8000   # 阶段2 输出 token 预算
_ENTITY_TABLE_TOKENS_PER = 50  # 每个实体在实体表中占用的 tokens


def _compute_chunk_size(llm_client: LLMClient, stage: str, entity_count: int = 0) -> int:
    """根据模型上下文窗口动态计算分块大小（字符数）。

    chunk_size = (context_window - prompt_overhead - output_budget - entity_table_tokens)
                 × chars_per_token × safety_factor
    """
    context_window = getattr(llm_client, "context_window", 32000)
    output_budget = _STAGE1_OUTPUT_BUDGET if stage == "entities" else _STAGE2_OUTPUT_BUDGET
    entity_table_tokens = entity_count * _ENTITY_TABLE_TOKENS_PER if stage == "relations" else 0
    available_tokens = context_window - _PROMPT_OVERHEAD - output_budget - entity_table_tokens
    chunk_size = int(available_tokens * _CHARS_PER_TOKEN * _SAFETY_FACTOR)
    return max(_MIN_CHUNK_SIZE, min(_MAX_CHUNK_SIZE, chunk_size))


def _split_text(text: str, chunk_size: int) -> List[str]:
    """递归分块，10% overlap（最大 2000 字符）。"""
    overlap = min(int(chunk_size * 0.1), 2000)
    chunks = RecursiveStrategy().split(text, chunk_size, overlap)
    return [c.content for c in chunks]


def run_concurrent(fn: Callable, items: List[Any], *args, **kwargs) -> List[Any]:
    """并发执行 fn(item, *args, **kwargs)，按原始顺序返回结果。

    失败的 item 结果为 None，不阻塞其他 item。
    """
    results: List[Any] = [None] * len(items)
    if not items:
        return results
    with ThreadPoolExecutor(max_workers=min(len(items), _MAX_WORKERS)) as executor:
        future_to_idx = {
            executor.submit(fn, item, *args, **kwargs): i
            for i, item in enumerate(items)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                import traceback
                traceback.print_exc()
                results[idx] = None
    return results


def _extract_single_entity(
    chunk_text: str, llm_client: LLMClient, ontology: Optional[Dict[str, Any]],
) -> EntityStageResult:
    """单 chunk 阶段1 抽取（供并发调用）。"""
    rep = QualityReport()
    try:
        msgs = build_node_messages(text=chunk_text, ontology=ontology)
        node_json, tokens = _llm_call_with_retry(llm_client, msgs)
        entities, anchors, alias_map, doc_time = _parse_nodes(node_json, chunk_text, rep)
        return EntityStageResult(
            entities=entities, time_anchors=anchors,
            alias_map=alias_map, doc_time=doc_time, tokens=tokens,
        )
    except Exception:
        import traceback
        traceback.print_exc()
        return EntityStageResult(entities=[], time_anchors=[], alias_map={}, tokens=0)


def _extract_single_relation(
    chunk_text: str, llm_client: LLMClient, stage1: EntityStageResult,
    ontology: Optional[Dict[str, Any]],
) -> List[ExtractedRelation]:
    """单 chunk 阶段2 抽取（注入全局实体表，供并发调用）。"""
    try:
        name_set = stage1.name_set
        entity_table = format_entity_table(
            [{"canonicalName": n, "type": t} for n, t in name_set.items()]
        )
        msgs = build_relation_messages(
            text=chunk_text, entity_table_str=entity_table, ontology=ontology,
        )
        rel_json, _tokens = _llm_call_with_retry(llm_client, msgs)
        return _parse_relations(rel_json, chunk_text, name_set, stage1.alias_map, QualityReport())
    except Exception:
        import traceback
        traceback.print_exc()
        return []


def merge_stage1(chunk_results: List[EntityStageResult], rep: QualityReport) -> EntityStageResult:
    """合并多个 chunk 的阶段1 结果。

    · 实体：canonicalName 去重，evidenceText 用 | 拼接，type 冲突保留首次 + WARNING
    · 时间锚点：直接拼接
    · 指代链：别名取并集
    """
    merged_entities: Dict[str, ExtractedEntity] = {}
    merged_anchors: List[TimeAnchor] = []
    merged_alias_map: Dict[str, str] = {}
    total_tokens = 0

    for result in chunk_results:
        if result is None or result is None:
            continue
        total_tokens += result.tokens
        for e in result.entities:
            key = e.canonicalName
            if key not in merged_entities:
                merged_entities[key] = e
            else:
                existing = merged_entities[key]
                if e.type != existing.type:
                    rep.add("WARNING", "W3_TYPE_CONFLICT",
                            f"实体 '{key}' 类型冲突: {existing.type} vs {e.type}，"
                            f"保留 {existing.type}")
                if e.evidenceText and e.evidenceText not in existing.evidenceText.split(" | "):
                    existing.evidenceText = (
                        f"{existing.evidenceText} | {e.evidenceText}"
                        if existing.evidenceText else e.evidenceText
                    )
        merged_anchors.extend(result.time_anchors)
        for alias, canonical in result.alias_map.items():
            if alias not in merged_alias_map:
                merged_alias_map[alias] = canonical

    doc_time = next((r.doc_time for r in chunk_results if r and r.doc_time), None)
    return EntityStageResult(
        entities=list(merged_entities.values()),
        time_anchors=merged_anchors,
        alias_map=merged_alias_map,
        doc_time=doc_time,
        tokens=total_tokens,
    )


def merge_stage2(
    chunk_relations_list: List[List[ExtractedRelation]], rep: QualityReport
) -> List[ExtractedRelation]:
    """合并多个 chunk 的阶段2 关系。

    · 去重键：(subject, predicate, object)
    · confidence 取最大值
    · evidenceText 用 | 拼接
    · vt_from 取最早，vt_to 取最晚
    """
    merged: Dict[Tuple[str, str, str], ExtractedRelation] = {}
    for rels in chunk_relations_list:
        if not rels:
            continue
        for r in rels:
            key = (r.subject.strip(), r.predicate.strip(), r.object.strip())
            if key not in merged:
                merged[key] = r
            else:
                existing = merged[key]
                if r.confidence > existing.confidence:
                    existing.confidence = r.confidence
                if r.evidenceText and r.evidenceText not in existing.evidenceText:
                    existing.evidenceText = (
                        f"{existing.evidenceText} | {r.evidenceText}"
                        if existing.evidenceText else r.evidenceText
                    )
                if r.vt_from and (not existing.vt_from or r.vt_from < existing.vt_from):
                    existing.vt_from = r.vt_from
                if r.vt_to and (not existing.vt_to or r.vt_to > existing.vt_to):
                    existing.vt_to = r.vt_to
    return list(merged.values())


def extract_entities_chunked(
    llm_client: LLMClient,
    text: str,
    ontology: Optional[Dict[str, Any]],
    rep: QualityReport,
) -> EntityStageResult:
    """阶段1 分块并发抽取 + 合并。"""
    chunk_size = _compute_chunk_size(llm_client, "entities")
    chunks = _split_text(text, chunk_size)
    rep.add("INFO", "CHUNK_STAGE1",
            f"阶段1 分 {len(chunks)} 块并发抽取（chunk_size≈{chunk_size}）")

    chunk_results = run_concurrent(_extract_single_entity, chunks, llm_client, ontology)
    valid = [r for r in chunk_results if r is not None]
    if not valid:
        raise ValueError("所有 chunk 阶段1 抽取失败，请检查 LLM 连接")

    merged = merge_stage1(valid, rep)
    rep.add("INFO", "PIPELINE_TWO_STAGE",
            f"[分块] 阶段1 合并后: 实体×{len(merged.entities)}、"
            f"时间锚点×{len(merged.time_anchors)}、指代链别名×{len(merged.alias_map)}")

    if not merged.entities:
        raise ValueError(f"阶段1 分块抽取未得到任何实体。issues={rep.stats}")
    return merged


def extract_relations_chunked(
    llm_client: LLMClient,
    text: str,
    stage1: EntityStageResult,
    ontology: Optional[Dict[str, Any]],
    rep: QualityReport,
) -> Tuple[List[ExtractedRelation], int]:
    """阶段2 分块并发抽取（注入全局实体表）+ 关系去重合并。"""
    chunk_size = _compute_chunk_size(llm_client, "relations", len(stage1.entities))
    chunks = _split_text(text, chunk_size)
    rep.add("INFO", "CHUNK_STAGE2",
            f"阶段2 分 {len(chunks)} 块并发抽取（chunk_size≈{chunk_size}，"
            f"全局实体数 {len(stage1.entities)}）")

    chunk_relations = run_concurrent(
        _extract_single_relation, chunks, llm_client, stage1, ontology
    )
    relations = merge_stage2(chunk_relations, rep)
    rep.stats["relations_extracted"] = len(relations)
    # token 统计：阶段2 按 chunk 数估算（实际 tokens 在 _extract_single_relation 中未返回）
    estimated_tokens = 0
    return relations, estimated_tokens

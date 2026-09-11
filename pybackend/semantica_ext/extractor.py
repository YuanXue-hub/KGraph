"""Semantica 抽取封装 + KGraph schema 适配层。

运行环境：WarSee conda 环境（semantica / fastapi / uvicorn / pymysql）。
独立于主服务 8001 运行在 8002 端口，不写 Neo4j，仅返回可导出的 JSON。

适配原则（对比实验公平性）：
  · 两阶段流水线与 KGraph 同构：extract_entities_llm → extract_relations_llm
  · 开启 extract_temporal_bounds=True（Semantica 双时态扩展，映射为 vt_from/vt_to）
  · 实体类型使用与 KGraph 内置默认词表对齐的中文 9 类
  · span / 证据句由代码回原文 find() 定位（Semantica typed 模式不返回偏移，
    与 KGraph "LLM 零数字偏移输出"策略一致）
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

# 与 KGraph prompt_builder 内置默认实体词表对齐（9 类）
KG_ENTITY_TYPES = ["人物", "组织", "地点", "时间", "事件", "政策文件", "公司", "概念", "职位"]

# Semantica 默认英文标签 → 中文（未传 entity_types 时的兜底映射）
_LABEL_ZH = {
    "PERSON": "人物", "ORG": "组织", "ORGANIZATION": "组织", "GPE": "地点",
    "LOC": "地点", "DATE": "时间", "TIME": "时间", "EVENT": "事件",
    "PRODUCT": "产品", "CONCEPT": "概念", "COMPANY": "公司",
    "MISC": "概念", "WORK_OF_ART": "政策文件", "LAW": "政策文件",
}

_SENT_SPLIT = re.compile(r"[。！？；;!?\n]")


def _label_zh(label: str) -> str:
    """英文标签归一为中文，已是中文则原样返回。"""
    label = (label or "").strip()
    if not label:
        return "概念"
    return _LABEL_ZH.get(label.upper(), label)


def _find_span(text: str, needle: str, start_from: int = 0) -> Optional[Dict[str, int]]:
    """在原文中定位 needle，返回 {start, end}（闭区间），找不到返回 None。"""
    if not needle:
        return None
    pos = text.find(needle, start_from)
    if pos < 0:
        return None
    return {"start": pos, "end": pos + len(needle) - 1}


def _sentences(s: str) -> List[str]:
    """按中英文句末标点切句，保留非空句。"""
    return [p.strip() for p in _SENT_SPLIT.split(s or "") if p.strip()]


def _locate_evidence(text: str, context: str, subj: str, obj: str) -> List[Dict[str, Any]]:
    """从 Relation.context 切句选证据句，回原文定位 span。

    Semantica 的 context 是 LLM 返回的"上下文片段"（常为原文若干句拼接），
    本身不是精确证据句。策略：
      1. context 切句
      2. 优先选同时包含头尾实体（或其子串互含）的最短句
      3. 次选包含任一实体且包含谓词相关内容的句子（由调用方传谓词过滤）
      4. 候选句回原文 find() 定位；context 中的句子若非原文逐字（LLM 改写），
         find 失败则该关系无证据 span（评估侧自然无样本，符合 Semantica 无强制
         证据回溯机制的客观差异）
    """
    spans: List[Dict[str, Any]] = []
    if not text:
        return spans
    for sent in _sentences(context):
        has_subj = subj and (subj in sent or sent in subj)
        has_obj = obj and (obj in sent or sent in obj)
        if not (has_subj or has_obj):
            continue
        sp = _find_span(text, sent)
        if sp:
            spans.append({**sp, "text": sent})
        if len(spans) >= 2:
            break
    # 优先保留头尾都命中的句子
    both = [s for s in spans if (subj and subj in s.get("text", "")) and (obj and obj in s.get("text", ""))]
    return (both or spans)[:2]


def run_semantica_extraction(
    text: str,
    model_name: str,
    api_key: str,
    base_url: str,
    entity_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """两阶段 Semantica 抽取，返回 KGraph 兼容 schema。

    返回结构与 KGraph /api/extract 对齐：
      entities: [{name, mention, type, span}]
      relations: [{head, relation, tail, subjectType, objectType,
                  vt_from, vt_to, confidence, evidenceSpans}]
    """
    from semantica.semantic_extract.methods import (
        extract_entities_llm,
        extract_relations_llm,
    )

    t0 = time.time()
    types = entity_types or KG_ENTITY_TYPES
    provider_kwargs = {
        "api_key": api_key,
        "base_url": base_url,
        "entity_types": types,
    }

    # ---- 阶段1：实体抽取 ----
    t_stage = time.time()
    raw_ents = extract_entities_llm(
        text, provider="openai", model=model_name, **provider_kwargs,
    )
    stage1_ms = int((time.time() - t_stage) * 1000)

    entities: List[Dict[str, Any]] = []
    seen: set = set()
    for e in raw_ents:
        name = (e.text or "").strip()
        if not name:
            continue
        key = (name, e.label)
        if key in seen:
            continue
        seen.add(key)
        sp = _find_span(text, name)
        entities.append({
            "name": name,
            "mention": name,
            "type": _label_zh(e.label),
            "span": sp or {"start": 0, "end": 0},
            "confidence": round(float(e.confidence or 1.0), 4),
        })

    # ---- 阶段2：关系抽取（双时态扩展）----
    t_stage = time.time()
    raw_rels = extract_relations_llm(
        text, raw_ents, provider="openai", model=model_name,
        extract_temporal_bounds=True, **provider_kwargs,
    )
    stage2_ms = int((time.time() - t_stage) * 1000)

    relations: List[Dict[str, Any]] = []
    for r in raw_rels:
        subj = (r.subject.text or "").strip() if r.subject else ""
        obj = (r.object.text or "").strip() if r.object else ""
        pred = (r.predicate or "").strip()
        if not (subj and obj and pred):
            continue
        md = r.metadata or {}
        ev_spans = _locate_evidence(text, r.context or "", subj, obj)
        relations.append({
            "head": subj,
            "relation": pred,
            "tail": obj,
            "subjectType": _label_zh(r.subject.label) if r.subject else "概念",
            "objectType": _label_zh(r.object.label) if r.object else "概念",
            "vt_from": md.get("valid_from"),
            "vt_to": md.get("valid_until"),
            "vt_precision_from": "unknown",
            "vt_precision_to": "unknown",
            "confidence": round(float(r.confidence or 1.0), 4),
            "evidenceSpans": [{k: v for k, v in s.items() if k != "text"} for s in ev_spans],
            "evidenceText": ev_spans[0]["text"] if ev_spans else "",
        })

    return {
        "entities": entities,
        "relations": relations,
        "timeAnchors": [],   # Semantica 无独立时间锚点结构（时态在关系 metadata 上）
        "causalEdges": [],
        "tokenConsumed": 0,  # Semantica provider 不返回 usage，UI 显示 "—"
        "duration": int((time.time() - t0) * 1000),
        "stageTimings": {"entityStageMs": stage1_ms, "relationStageMs": stage2_ms},
        "extractor": "semantica",
        "model": model_name,
        "entityTypes": types,
    }

"""LLM 抽取输出的严格 Pydantic Schema（借鉴 Semantica 语义层结构化建模）。

注意：此处仅定义「输出格式」，不做抽取逻辑。真正的确定性校验（时态一致性、
DAG 无环、span 越界、证据对齐）放在 extraction_validator.py 里执行，遵循
Semantica「LLM 只负责抽取、Quality Layer 做确定性治理」的分层原则。
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, validator


# ============================================================================
# 基础类型常量 + 治理阈值（全链路唯一源，extraction_validator 和 graph_writer 都从此读取）
# ============================================================================
CAUSE_DIR = Literal["FORWARD", "PREVENT"]
ANCHOR_TYPE = Literal["DATE", "DATERANGE", "RELATIVE", "NOW", "OPEN", "UNKNOWN"]
PRECISION = Literal["day", "month", "quarter", "year", "decade", "unknown"]

# ---- Semantica Quality Layer 阈值（用户新原则：实体/关系尽量多，不过滤，保证图谱完整性）----
# 说明：用户要求"实体关系尽量多，不需要过滤啥的，要保证知识图谱网络的完整性"；
# 因此本版把硬丢弃线降为 0.0（即 0~1 置信度的断言均允许入库），
# 低置信的条目仍会打 lowConfidence=true 标签 + 质量报告 WARNING，但不会被 DROP。
CONF_RELATION_KEEP: float = 0.10   # 关系 lowConfidence 标记线（< 则标 lowConfidence=true）
CONF_CAUSAL_KEEP: float = 0.10     # 因果 lowConfidence 标记线
CONF_DROP: float = 0.00            # 硬丢弃线：0.00 表示理论上不丢弃任何一条断言


# ============================================================================
# 子结构：原文字符级证据 span
# ============================================================================
class EvidenceSpan(BaseModel):
    """单条证据在原文中的字符级闭区间 [start, end]，下标从 0 开始。"""

    start: int = Field(..., ge=0, description="起始字符下标（含）")
    end: int = Field(..., ge=0, description="结束字符下标（含）")

    @validator("end")
    def start_le_end(cls, v, values):  # noqa: N805
        if "start" in values and v < values["start"]:
            raise ValueError(f"end({v}) < start({values['start']})")
        return v


# ============================================================================
# 1. 实体（归一化 + 本体对齐 + 证据）
# ============================================================================
class ExtractedEntity(BaseModel):
    mention: str = Field(..., min_length=1, description="原文中出现的字面片段，如 '字节'")
    canonicalName: str = Field(
        ...,
        min_length=1,
        description="归一化后的标准名称，如 '字节跳动'；应与 mention 是同一实体，严禁跨实体编造",
    )
    type: str = Field(..., min_length=1, description="实体类型；优先匹配本体，缺失时自由推断")
    kosCategory: Optional[str] = Field(
        None, description="可选：KOS 三层路径，如 '信息技术/互联网公司/平台企业'"
    )
    span: EvidenceSpan = Field(..., description="mention 所对应的原文字符级 span")


# ============================================================================
# 2. 时间锚点（单独抽，避免和关系捆绑时 LLM 漏抽 / 编造时间）
# ============================================================================
class TimeAnchor(BaseModel):
    expr: str = Field(..., min_length=1, description="原文中出现的时间表达式，逐字来自原文")
    type: ANCHOR_TYPE = "UNKNOWN"
    normISO: Optional[str] = Field(
        None,
        description=(
            "标准化 ISO 时间字符串或范围。DATE='2024-03' 粒度用 precision 标注；"
            "DATERANGE='2020-07/2024-03'（ISO 8601 斜杠区间）；NOW=OPEN 时留空。"
            "只有原文出现明确绝对时间才填；RELATIVE 相对时间不要强行解析成绝对时间。"
        ),
    )
    precision: PRECISION = "unknown"
    relativeAnchor: Optional[str] = Field(
        None,
        description="RELATIVE 类型时说明依赖的锚点，如 'doc_time / 事件A开始'；其它类型留空",
    )
    span: EvidenceSpan


# ============================================================================
# 3. 关系断言（绑定时态 + 证据 + 置信度，借鉴 Semantica A-Box 双时态）
# ============================================================================
class ExtractedRelation(BaseModel):
    subject: str = Field(..., description="头实体，对应某个 Entity.canonicalName / 因果事件名")
    predicate: str = Field(..., min_length=1, description="关系谓词，动词短语或名词短语")
    object: str = Field(..., description="尾实体，对应某个 Entity.canonicalName")
    subjectType: Optional[str] = None
    objectType: Optional[str] = None
    # ---- 双时态：VT（有效时间）----
    vt_from: Optional[str] = Field(
        None,
        description="有效时间起点（ISO 字符串或空）。原文没提及且无可靠锚点就留空，不要猜。",
    )
    vt_to: Optional[str] = Field(
        None,
        description="有效时间终点。'至今 / 目前 / 现任' 等开放式留空；明确 '已离职 / 曾任' 时填锚点。",
    )
    vt_precision_from: PRECISION = "unknown"
    vt_precision_to: PRECISION = "unknown"
    confidence: float = Field(..., ge=0.0, le=1.0, description="断言置信度，LLM 自估")
    evidenceSpans: List[EvidenceSpan] = Field(
        ..., min_length=1, description="至少 1 处原文证据 span。没有证据的断言 LLM 应直接不输出。"
    )


# ============================================================================
# 4. 因果边（独立关系类型，借鉴 Semantica Decision Intelligence）
# ============================================================================
class CausalEdge(BaseModel):
    causeEvent: str = Field(
        ..., min_length=1, description="因事件（应在实体列表中出现，否则退回 T1 再补）"
    )
    causeType: Optional[str] = Field(None, description="因事件的实体类型，如 事件/政策/宏观因素")
    effectEvent: str = Field(..., min_length=1, description="果事件")
    effectType: Optional[str] = Field(None, description="果事件的实体类型")
    direction: CAUSE_DIR = Field(
        "FORWARD",
        description=(
            "FORWARD=正向因果（导致/使得/引发）；PREVENT=预防性因果（避免/抑制/降低了…风险）。"
            "一期只做这两类，反事实放 P2。"
        ),
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    signalWord: Optional[str] = Field(
        None,
        description="触发该因果边的原文信号词，如 导致/使得/归因于/result in/避免了/抑制。无信号词不输出本条。",
    )
    vt_order: Optional[Literal["CAUSE_BEFORE_EFFECT", "SAME_TIME", "UNKNOWN"]] = Field(
        None,
        description="能从时间锚点证明 cause.VT≤effect.VT 时标 CAUSE_BEFORE_EFFECT，其余 SAME_TIME/UNKNOWN",
    )
    evidenceSpans: List[EvidenceSpan] = Field(
        ..., min_length=1, description="至少 1 处原文证据 span，且必须包含 signalWord 所在片段"
    )


# ============================================================================
# 5. 整体抽取 Payload
# ============================================================================
class LlmExtractionPayload(BaseModel):
    docTime: Optional[str] = Field(
        None,
        description="文档成文时间（来自语料库 metadata，若没有则传空）。RELATIVE 时间锚点会参照它。",
    )
    entities: List[ExtractedEntity] = Field(default_factory=list)
    timeAnchors: List[TimeAnchor] = Field(default_factory=list)
    relations: List[ExtractedRelation] = Field(default_factory=list)
    causalEdges: List[CausalEdge] = Field(default_factory=list)

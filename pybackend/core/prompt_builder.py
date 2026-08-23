"""基于 Semantica 流水线思想的 LLM 知识抽取 Prompt（两阶段 · 2026-08-23 重构）。

架构（借鉴 Semantica 五步流水线，适配为 2 次 LLM 调用）：
  阶段1 build_node_messages：抽「节点」—— 静态实体 + 事件实体 + 指代消解链 + 时间锚点
         · 实体只填 mention/canonicalName/type，不填数字 span（span 由代码 find() 定位）
         · 事件实体 type 统一为「事件」（不细分枚举），语义全靠 canonicalName 自包含描述
         · 指代词（该院/该公司）不放 entities，放 coreferenceChains
  阶段2 build_relation_messages：抽「关系」—— 注入阶段1 实体表做硬约束
         · 主语/宾语必须从实体表中选（消除幻觉实体 → 消除孤立节点）
         · 每条关系附证据句原文 evidenceText（不填数字偏移，代码定位算 span）

设计原则（对照旧版 T1 单阶段的痛点）：
  1. 每次调用只做一类任务，注意力全部给当前子任务（关系密度↑）
  2. 关系抽取受实体表约束 + 代码二次校验未命中即丢（幻觉实体清零）
  3. 指代消解前置（"该院"归并到规范实体，孤立节点↓）
  4. 证据句原文代替数字偏移（span 幻觉问题结构性消除）
  5. causalEdges 因果边不做 LLM 抽取（等图谱构建完成后走图上离线推理）
"""
from __future__ import annotations

import json
from typing import Any, Dict, List


def _format_ontology(ontology: Dict[str, Any] | None) -> str:
    """把本体约束压成紧凑字符串（type 枚举优先，未命中才允许自定义）。"""
    if not ontology or not isinstance(ontology, dict):
        return "（无本体约束，type 自由推断）"
    items: List[str] = []
    for k, v in ontology.items():
        if isinstance(v, (str, int, float)):
            items.append(f"- {k}: {v}")
        elif isinstance(v, list):
            items.append(f"- {k}: {', '.join(str(x) for x in v[:12])}")
        elif isinstance(v, dict):
            items.append(f"- {k}: {json.dumps(v, ensure_ascii=False)[:150]}")
    return "\n".join(items[:20]) if items else "（无本体约束，type 自由推断）"


def format_entity_table(entities: List[Dict[str, Any]], max_items: int = 80) -> str:
    """把阶段1 的实体清单格式化为约束表，注入阶段2 Prompt。"""
    lines: List[str] = []
    for i, e in enumerate(entities, 1):
        name = str(e.get("canonicalName") or "").strip()
        etype = str(e.get("type") or "").strip()
        if not name:
            continue
        lines.append(f"{i}. {name} ｜ {etype}")
        if len(lines) >= max_items:
            break
    if not lines:
        return "（实体表为空）"
    return "\n".join(lines)


# ============================================================================
# 阶段1：节点抽取（静态实体 + 事件实体 + 指代消解链 + 时间锚点）
# ============================================================================
def build_node_messages(
    text: str,
    ontology: Dict[str, Any] | None = None,
) -> List[Dict[str, str]]:
    onto_str = _format_ontology(ontology)

    user_msg = f"""## 任务：从「待抽取文本」中抽取知识图谱的全部节点。只抽节点，不抽关系。

### 输出格式（严格只输出以下 JSON 一段，不要任何解释/markdown/思考过程）
```
{{
  "docTime": "文档成文时间 ISO 字符串或 null",
  "entities": [
    {{"mention": "原文片段", "canonicalName": "归一化标准名", "type": "实体类型"}}
  ],
  "coreferenceChains": [
    {{"canonicalName": "规范实体名（必须与 entities 中某条一致）", "aliases": ["指代词1", "指代词2"]}}
  ],
  "timeAnchors": [
    {{"expr": "原文时间表达式逐字", "type": "DATE|DATERANGE|RELATIVE|NOW|OPEN|UNKNOWN", "normISO": "标准ISO或null", "precision": "day|month|quarter|year|unknown", "relativeAnchor": "RELATIVE时写依赖锚点，否则null"}}
  ]
}}
```

### 实体抽取铁律
1. mention 必须逐字来自原文（代码会回原文定位校验）；canonicalName 是归一化名（机构全称/标准译名）。
2. 静态名词实体（人/机构/地点/疾病/药物/公司/概念/文件/数值指标）与动词事件实体都要抽，尽量全。
3. 事件实体：type 统一填「事件」两个字，不做细分；canonicalName 必须自包含描述清楚——用「主体+动作(+对象)」完整短语，如「广州市第八人民医院报告接诊聚集性发热病例」「康泰瑞普生物连续涨停」，禁止只写裸动词（如「报告接诊」「启动」）。
4. 指代词（该院、该公司、该病毒、其、他们）【不要】放进 entities，统一放 coreferenceChains 的 aliases。
5. 不确定成文的 docTime 写 null；timeAnchors 只抽原文真实出现的时间表达式。

### 本体约束（type 优先从下列选，未命中才自定义）
{onto_str}

## 待抽取文本
```
{text}
```
"""

    return [
        {"role": "system", "content": "你是严谨的中文知识图谱节点抽取工程师。只输出 JSON 本身，字段不留 null 占位（可空字段除外）。实体宁全勿漏，类型必须遵守枚举约束。"},
        {"role": "user", "content": user_msg},
    ]


# ============================================================================
# 阶段2：关系抽取（注入阶段1 实体表做硬约束 + 证据句原文）
# ============================================================================
def build_relation_messages(
    text: str,
    entity_table_str: str,
    ontology: Dict[str, Any] | None = None,
) -> List[Dict[str, str]]:
    onto_str = _format_ontology(ontology)

    user_msg = f"""## 任务：从「待抽取文本」中抽取实体之间的关系三元组。

### 实体表（关系的主语 subject 和宾语 object【只能】从下表的「实体名」中选，禁止编造表外实体）
{entity_table_str}

### 输出格式（严格只输出以下 JSON 一段）
```
{{
  "relations": [
    {{"subject": "实体表中的实体名", "predicate": "关系谓词", "object": "实体表中的实体名",
      "evidenceText": "支撑本关系的原文完整句子（必须逐字来自原文，代码会校验）",
      "vt_from": "关系有效起点 ISO 或 null", "vt_to": "关系有效终点 ISO 或 null",
      "status": "CURRENT|EXPIRED|NEGATED", "confidence": 0.0}}
  ]
}}
```

### 关系抽取铁律
1. subject / object 必须逐字命中实体表中的实体名——表外实体直接不输出该条。
2. evidenceText 必须是原文中的完整句子（含主谓宾），逐字复制，不要改写缩写。
3. status 语义：CURRENT=当前生效（默认）；EXPIRED=曾经生效现已失效（曾任/已离职）；NEGATED=原文明确否定（不再担任/排除/暂停）。
4. 时间绑定【必填】：凡原文给出了关系发生/生效时间（如「1月5日接诊」「1月13日发布」「当晚休市」），vt_from 必须填该时间 ISO；关系持续至今或事件性关系 vt_to 填 null。不要因为懒而全部填 null。
5. 参与者与事件之间【只输出一条边】：优先用语义动词谓词（接诊/启动/发布/休市/研发等，方向 主体-[动词]->事件）；仅当没有自然动词时才用 事件-[执行主体]->机构 或 事件-[对象]->实体。严禁同一对 (参与者, 事件) 同时输出「主体-动词->事件」和「事件-执行主体->主体」两条冗余边。
6. 每个事件实体至少挂 1 条论元关系（谁做的 / 对谁做的 / 作用于什么）；确实无证据时不硬凑。
7. 非事件对之间的关系同样要抽全：机构间从属/合作（疾控中心-上报->国家卫健委）、概念间同源/相似（CoV-N25-同源->RaTG13，87.6% 数值放 vt 或 confidence 之外可省）、产品与公司（mRNA疫苗-研发方->康泰瑞普生物）、政策与对象（通报-管理对象->CoV-N25）。
8. 原文中的否定/排除表述（如「排除了腺病毒的可能性」「暂停赴粤团队游」）必须输出 NEGATED 或语义谓词边，不要跳过。
9. confidence 如实标注：很有把握 0.9+，中等把握 0.6~0.8 也输出，仅把握极低(<0.5)才不输出——图谱构建宁要带置信标注的中等边，也不要丢边。
10. predicate 优先使用本体约束中的谓词（若有），否则用动词短语。

### 本体约束（谓词参考）
{onto_str}

## 待抽取文本
```
{text}
```
"""

    return [
        {"role": "system", "content": "你是严谨的中文知识图谱关系抽取工程师。只输出 JSON 本身。主语宾语必须来自给定实体表，每条关系必须有原文证据句。"},
        {"role": "user", "content": user_msg},
    ]

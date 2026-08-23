# 基于 LLM 的双时态动态本体与因果链抽取方案 —— 技术文档

> 版本：v1.0（2026-08-22） | 适用模块：知识抽取 → LLM 抽取 | 设计参考：Semantica 语义层分层思想（LLM 只负责抽取、Quality Layer 做确定性治理、A-Box 时态版本化累积）

---

## 0. 边界声明（严格遵守）

1. **仅改造 LLM 抽取链路**，KOS 抽取、深度学习抽取、结构化抽取三套实现 **零代码改动**；`graph_writer.write()`、`build_messages()` 等旧 API 完全保留兼容。
2. 先验注入思路：KOS / DL 抽取结果 **只读不写** —— 只把识别到的实体 mention + 类型作为「已知候选清单」拼入 T1 Prompt，绝不调用 KOS/DL 的 Neo4j 写库函数。
3. 不引入 LangGraph / LangChain / DSPy 等外部编排框架，全部基于 **自定义提示词 + Pydantic + 纯 Python 校验** 实现，依赖树保持极简。

---

## 1. 总体架构

```
输入文本 + 可选 KOS/DL 请求体
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 0 · 先验收集（只读）                                      │
│   _collect_prior_entities → {kos_extract, dl_extract} 尝试调用 │
│   失败记 WARNING，不阻塞主流程                                   │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 1 · T1 统一抽取（LLM 第一遍）                               │
│   build_t1_messages(text, ontology, prior, docMetadata)         │
│   → 实体归一化 + 时间锚点 + 时态绑定关系（不抽因果）               │
│   → Pydantic 解析失败自动结构修正重试 1 次                         │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 2 · 质量校验墙 W1~W5（第一遍）                              │
│   W1 span 合法性 + signalWord 对齐 → W2 时态一致 + 倒序交换       │
│   → W3 实体消歧去重 → W4 因果 DAG（无因果跳过）→ W5 低置信剔除      │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 3 · T2 因果专门抽取（LLM 第二遍，条件：len(text)≥12 且有实体） │
│   build_t2_messages(text, t1_payload)                           │
│   → 仅输出 causalEdges，必须带原文 signalWord 才输出              │
│   → 单条因果 schema 非法只丢该条；合并后再跑 W4+W5                 │
│   → T2 整体失败不阻塞 T1，记 ERROR 继续入库                       │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ Step 4 · 写入 Neo4j（graph_writer.write_llm_extracted）          │
│   实体 MERGE（保留所有 mentions）                                 │
│   关系 CREATE（**不 MERGE**，时态版本化累积）                      │
│   因果边 CREATE [:CAUSES]（独立关系类型，不混在 :RELATION）        │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
  ExtractionResult{entities, timeAnchors, relations, causalEdges,
                   qualityReport[], qualityStats, tokenConsumed,
                   duration, writeCount}
```

---

## 2. 数据模型（Pydantic Schema 单源定义）

文件：[`core/extraction_schema.py`](file:///Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend/core/extraction_schema.py)

### 2.1 证据 Span —— 闭区间语义
```python
class EvidenceSpan(BaseModel):
    start: int   # 含，≥ 0
    end: int     # 含，≥ start；切片语义：text[start : end+1]
```
> 本方案里 **所有 span 都用闭区间**。Quality Layer 的 W1 会强制执行：`0 ≤ start ≤ end < len(TEXT)`。这是和 Python 默认半开区间的关键差异。

### 2.2 四等公民模型

| 结构 | 核心字段 | 设计要点 |
|---|---|---|
| `ExtractedEntity` | `mention` / `canonicalName` / `type` / `kosCategory?` / `span` | 实体分字面 + 归一化两层；类型优先对齐本体 KOS；`kosCategory` 是 KOS 三层分类路径 |
| `TimeAnchor` | `expr` / `type ∈ {DATE,DATERANGE,RELATIVE,NOW,OPEN,UNKNOWN}` / `normISO?` / `precision` / `relativeAnchor?` / `span` | **时间锚点一等公民独立建模**，不和关系捆绑——避免 LLM 漏抽或瞎编。RELATIVE 只写依赖字符串，不强解析绝对时间 |
| `ExtractedRelation` | `(subject, predicate, object)` / `vt_from?` / `vt_to?` / `status ∈ {CURRENT, EXPIRED, NEGATED}` / `confidence` / `evidenceSpans[]` | `vt_from / vt_to` 原文没提就 **严格留空**，不准猜；`NEGATED` 不参与正向推理但必须入库（反事实证据） |
| `CausalEdge` | `(causeEvent, effectEvent)` / `direction ∈ {FORWARD, PREVENT}` / `signalWord` / `vt_order?` / `confidence` / `evidenceSpans[]` | 因果边和普通关系 **彻底分家**；`signalWord` 必须逐字来自原文证据片段，否则宁可不抽；`vt_order` 能证明 cause≤effect 时填 `CAUSE_BEFORE_EFFECT` |

### 2.3 阈值常量（全链路唯一源，避免分散定义）

| 常量 | 默认值 | 含义 |
|---|---|---|
| `CONF_RELATION_KEEP` | 0.60 | 普通关系：低于此值 Neo4j 属性 `lowConfidence=true`，默认查询过滤 |
| `CONF_CAUSAL_KEEP`   | 0.65 | 因果边：比关系略高（因果更易幻觉） |
| `CONF_DROP`          | 0.30 | **硬丢弃线**：低于此值直接 DROP，不入库 |

> 阈值迁移：P2 计划挪到 `config.json → extraction` 节点做可配置。

---

## 3. 双时态设计（VT / TT）

P1 只实现 **VT（有效时间，Valid Time = 事实在现实世界的生效时间）**，TT（事务时间 = 知识库录入时间）用 Neo4j 的 `createTime` 近似表达，P2 再上正式 `tt_from / tt_to` 双字段。

### 3.1 VT 语义矩阵

| `status`  | `vt_from` | `vt_to` | 含义 |
|---|---|---|---|
| `CURRENT` | 有则填，无则空 | **留空**（开放式至今） | 现任/目前/仍然有效 |
| `EXPIRED` | 起 | 止 | 曾任/已离职/曾成立 |
| `NEGATED` | 空 / 时间背景 | 空 / 同上 | 原文明确「不再、并非、没有…」，关系本身不成立但反事实保留 |

### 3.2 精度（precision）
`day / month / quarter / year / decade / unknown`，必须与 `normISO` 粒度匹配：
- `2020年7月` → `normISO="2020-07"`, `precision="month"`
- `2021年` → `normISO="2021"`, `precision="year"`
- `现任 / 至今` → `type="NOW"`, `normISO=None`, `precision="unknown"`

### 3.3 时态倒序自动修复（W2）
当 LLM 写出 `vt_from=2025-01 > vt_to=2022-01` 这种反常识情况：
- **不 DROP**（信息仍然有价值）
- 自动交换两端 + 交换对应 precision
- 同时发 `WARNING W2_RELATION_VT_INVERTED` 供审核视图提示

---

## 4. 因果链建模（FORWARD / PREVENT + DAG）

### 4.1 信号词驱动（防幻觉核心）
因果边 T2 阶段的 Prompt 明确写死：**没有原文信号词的因果关系严禁输出**。信号词白名单示例：
- FORWARD：导致、造成、使得、引发、促使、进而使得、result in、lead to
- PREVENT：避免、抑制、阻止、缓解、降低了…风险、prevent、mitigate

### 4.2 vt_order 三档
| 值 | 语义 | 判定方式（W2 因果子步骤） |
|---|---|---|
| `CAUSE_BEFORE_EFFECT` | cause.VT ≤ effect.VT | 两端锚点 normISO 可比且 cause ≤ effect |
| `SAME_TIME` | 同期发生 | 锚点完全相同的并列事件（T2 可直接填） |
| `UNKNOWN` | 不可比 / 缺锚点 | 默认兜底 |
> 如果 LLM 填了 `CAUSE_BEFORE_EFFECT` 但实际锚点比出来是 `cause > effect`，校验墙降级为 `UNKNOWN` 并发 `W2_CAUSAL_VT_ORDER_WRONG` 告警。

### 4.3 DAG 无环保证（W4）
因果图不允许存在环（A→B→C→A 这种「自证因果」是典型幻觉模式）。处理策略：
1. Kahn 拓扑排序，能全排序即 DAG
2. 存在环时，按「当前置信度最低的边」优先删除，重复直到 DAG
3. 每条被删除的边都记 `DROPPED W4_CAUSAL_CYCLE_BROKEN`

---

## 5. Prompt 两阶段设计（自定义提示词封装，不走 Function Calling）

文件：[`core/prompt_builder.py`](file:///Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend/core/prompt_builder.py)

### 5.1 设计原则
- 不依赖模型的 Tools/Function Calling：可移植到任何支持 JSON 输出的 LLM（包括本地部署）
- 两阶段拆分降复杂度：T1 一次 LLM 最多要管 ~30 字段，把因果单独挪给 T2 显著降低单条输出长度和漏抽率
- **先验注入**：T1 顶部直接列 KOS/DL 已经识别到的 40 个实体，让 LLM 「对齐已知结果 + 补时态 + 找细粒度关系」，而不是从零开始再识别一遍 → 减少不一致

### 5.2 T1 输出约束（强 Schema + Few-Shot 示例）
- 多时态任职 + NEGATED 示例 1 条
- 严格「仅此一段 JSON，不要任何解释、markdown、代码块、思考过程」
- 输出中强制 `causalEdges = []`（后端 `t1_json["causalEdges"]=[]` 再兜一层）

### 5.3 T2 输入构造
```
你是一个因果抽取专家。仅基于原文中明确的因果信号词输出因果边。
原文：<...>
T1 已识别的事件类实体：
  - 新冠疫情爆发（事件）
  - 全球供应链中断（事件）
  ...
严格要求：
  1) causeEvent / effectEvent 必须优先使用 T1 已有的 canonicalName
  2) signalWord 必须与原文逐字一致，且 evidenceSpans 必须包含该片段
  3) 原文没出现因果信号词时，请输出空数组 []，严禁杜撰
  4) 只输出 JSON，不要任何解释
```

---

## 6. 质量校验墙（W1~W5，Semantica 式确定性治理）

文件：[`core/extraction_validator.py`](file:///Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend/core/extraction_validator.py)

分层执行顺序：`W1 → W2 → W3 → W4 → W5`。每条规则都写入 `QualityReport.issues[]`，最终随 API 返回，用于前端「质量问题清单」审核视图。

| 步骤 | 规则 ID | 严重度 | 行为 |
|---|---|---|---|
| **W1 span 合法性** | `W1_ENTITY_SPAN_OOB` | DROPPED | 实体越界 → 删实体 |
| | `W1_ENTITY_MENTION_MISMATCH` | WARNING | mention 与切片不一致 → 修正 mention，保留 |
| | `W1_ANCHOR_SPAN_OOB` / `EXPR_MISMATCH` | WARNING | 锚点归零 / 修正 expr |
| | `W1_RELATION_SPAN_BAD` | DROPPED | 关系任一证据越界或空 → 整条关系删 |
| | `W1_CAUSAL_SPAN_BAD` | DROPPED | 因果证据越界或空 → 整条因果删 |
| | `W1_CAUSAL_SIGNAL_MISSING` | **DROPPED** | signalWord 逐字不在任何 evidence span 内 → 硬删（防幻觉关键墙） |
| **W2 时态一致** | `W2_RELATION_VT_INVERTED` | WARNING | vt_from>vt_to → 交换两端，保留 |
| | `W2_CAUSAL_VT_ORDER_WRONG` | WARNING | cause>effect → vt_order 降级 UNKNOWN |
| **W3 实体消歧** | `W3_ENTITY_DEDUP` | WARNING | canonical+type 全相同 → 合并 span |
| | `W3_ENTITY_NEAR_DUP` | WARNING | Jaccard≥0.85（开关可控 `ENABLE_NEAR_DUP`）→ 长名胜出，关系/因果同步做别名替换 |
| **W4 因果 DAG** | `W4_CAUSAL_CYCLE_BROKEN` | DROPPED | 存在环 → 反复删最低置信边直到 DAG |
| **W5 低置信** | `W5_RELATION_CONF_LOW` / `W5_CAUSAL_CONF_LOW` | DROPPED | confidence<0.30 → 硬丢弃 |

---

## 7. Neo4j 落盘设计

文件：[`core/graph_writer.py → write_llm_extracted()`](file:///Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend/core/graph_writer.py#L112-L292)

### 7.1 核心差异（和 KOS/DL 老 `write()` 的对比）

| 维度 | 老 `write()`（KOS/DL/结构化） | 新 `write_llm_extracted()`（LLM 专用） |
|---|---|---|
| 实体 | MERGE | MERGE on `(canonicalName, type, modelId)`；**追加** `mentions[]` / `mentionSpans[]` |
| 关系 | **MERGE**（会覆盖时态旧版本 ❌） | **CREATE**（时态版本化累积 ✅） |
| 因果 | 不支持，统一塞 `:RELATION` | 独立 `[:CAUSES]` 关系类型 ✅ |
| 时间锚点 | 不单独建节点，混在属性里 | 单独建 `:TimeAnchor` 一等公民节点 ✅ |
| 缺失节点 | 报错 | 自动补占位 + `autoCreated=true`，后端 `missing_nodes_created` 计数 |

### 7.2 属性字典（A-Box）

#### 节点 `:Entity{type}`
- 必需：`name, canonicalName, type, source='llm_extract', modelId, createTime, updateTime`
- 可选：`kosCategory, mentions[], mentionSpans[], autoCreated`

#### 节点 `:TimeAnchor`
- 必需：`expr, type, normISO, precision, mentionSpan, modelId, createTime`
- 可选：`relativeAnchor, docId`

#### 关系 `[:RELATION]`
- 双时态：`vt_from, vt_to, vt_precision_from, vt_precision_to`
- 状态：`status ∈ {CURRENT/EXPIRED/NEGATED}, negated(bool)`
- 质量：`confidence, lowConfidence(bool), evidence[] (span_list), source='llm_extract'`
- 溯源：`subjectType, objectType, docId, modelId, createTime`

#### 关系 `[:CAUSES]`
- 因果：`direction ∈ {FORWARD/PREVENT}, signalWord, vt_order`
- 质量：`confidence, lowConfidence, evidence[], source='llm_extract'`
- 溯源：`causeType, effectType, docId, modelId, createTime`

### 7.3 关键 Cypher 语义

```cypher
// 实体：MERGE 并追加 mentions（不覆盖已有）
MERGE (n:Entity:Person {canonicalName:'张三', type:'人物', modelId:1})
SET n.mentions = coalesce(n.mentions, []) +
    CASE WHEN '张三' IN coalesce(n.mentions, []) THEN [] ELSE ['张三'] END

// 关系：CREATE（绝不覆盖时态版本）
MATCH (s:Entity {canonicalName:'张三', modelId:1}),
      (o:Entity {canonicalName:'字节跳动', modelId:1})
CREATE (s)-[r:RELATION {predicate:'任职于', vt_from:'2020-07', vt_to:'2024-03',
                        status:'EXPIRED', confidence:0.99, ...}]->(o)

// 因果
CREATE (ca)-[c:CAUSES {direction:'FORWARD', signalWord:'导致', vt_order:'CAUSE_BEFORE_EFFECT',
                       confidence:0.96, evidence:['90,104']}]->(cb)
```

---

## 8. API 主流程编排

文件：[`api/extraction.py → POST /api/extract`](file:///Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend/api/extraction.py#L199-L307)

### 8.1 完整步骤

| Step | 动作 | 失败降级 |
|---|---|---|
| 0 | 调 `_collect_prior_entities()` 尝试 KOS+DL 先验 | 失败记 `PRIOR_*_SKIP` WARNING，不阻塞 |
| 1 | `build_t1_messages` → `_llm_call_with_retry` → `t1_json["causalEdges"]=[]` | 结构解析失败 → 带错误提示 2nd retry，仍失败 → 500 |
| 2 | `run_quality_pipeline(t1_payload, text)`（W1~W5 全跑） | 内置修复，不对外抛 |
| 3 | `len(text)≥12 且 T1 有实体` 时跑 T2 → 合并 causalEdges → 再跑 W4+W5 | T2 失败记 ERROR，T1 结果照常入库 |
| 4 | 先验失败合并到 qualityReport | - |
| 5 | `graph_writer.write_llm_extracted(payload, modelId, docId)` | 抛 500 Neo4j 写入失败 |
| 6 | `_to_api_payload` → 返回 ExtractionResult | - |

### 8.2 关键 Failsafe

- **T1/T2 输出都强制清 `causalEdges`**：避免 LLM 在 T1 自作主张抽因果导致和 T2 重复
- **Pydantic 双次兜底**：T1 解析失败会把 `last_error=「Pydantic 校验失败…请重新检查字段类型与取值范围」` 再塞一次 LLM，最多 2 次
- **T2 单条因果 schema 失败只丢本条**：`parsed_causes` 逐条 try/except，其他边照常合并
- **缺失节点自动补位**：`ensure_node()` 遇到 T2 引用了 T1 没识别到的新事件，自动 MERGE 占位（`autoCreated=true`），避免因缺节点整条关系/因果落不了库

### 8.3 ExtractionResult 新增字段
- `timeAnchors[]`：Pydantic 序列化后的锚点列表
- `causalEdges[]`：因果边列表（独立于 relations）
- `qualityReport[]`：Semantica 式 `{level, code, message, entity_idx?, relation_idx?, causal_idx?}`
- `qualityStats{}`：按规则 code 聚合的计数 + `entities_final / timeAnchors_final / relations_final / causalEdges_final`
- `tokenConsumed`：T1 + T2 累计
- `duration`：总耗时（ms）
- `writeCount{entities, timeAnchors, relations, causalEdges, missing_nodes_created}`

---

## 9. 动态本体演化（P1 已支持部分 / P2 规划）

### P1 已落地的「动态」能力
- **概念新增**：`autoCreated=true` 的占位节点 = 本体 Schema 里原来没定义过的类型自动新增，不阻塞 A-Box 入库
- **多版本累积（时态）**：关系 CREATE 不 MERGE → 同一 `(s,p,o)` 会有多个带不同 `vt_from/vt_to/status/createTime` 的边，完整记录任职 / 失效的历史时间线（Semantica 核心 A-Box 版本化）
- **实体别名合并**：W3 `ENABLE_NEAR_DUP` 对近邻错别字做 canonical 替换（字节→字节跳动），保留长名做权威名

### P2 规划（非本次交付，供后续演进）
- **概念拆分 / 合并 / 弃用**：T-Box 层的本体演化日志表（`onto_evolution_log`），配合 `owl:deprecated / sameAs` 语义
- **双时态 TT**：`tt_from / tt_to` 正式字段，支持「查询知识库在 2026-03 时点看到的版本」
- **置信度衰减**：长期不被新抽取命中的旧关系按时间窗降权
- **人工审核闭环**：质量问题清单前端勾选「已确认 / 已修复 / 误报」，回写 LLMExtractionPayload 做 LLM SFT 数据

---

## 10. 离线验证方案

文件：[`scripts/test_llm_extraction_quality.py`](file:///Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend/scripts/test_llm_extraction_quality.py)

> **零依赖**：不启动服务、不调 LLM、不连 Neo4j。纯 Python 调 Quality Pipeline + Pydantic，1 秒内出结果。
> 直接跑：`cd pybackend && python3 scripts/test_llm_extraction_quality.py`

### 10.1 构造场景（TEXT 总长 134 字符，所有 span.end ≤ 133）
```
张三于2020年7月加入字节跳动担任高级工程师，2024年3月从字节跳动离职，
不再担任任何字节跳动关联公司的职务；
他现任美团基础架构部首席架构师，负责分布式系统研发。
2020年初新冠疫情爆发导致全球供应链中断，
进而使得2021年全球芯片短缺，对汽车行业造成严重冲击。
```

### 10.2 正例覆盖（5+1+3 条）
- 任职两期：`张三-担任→高级工程师（EXPIRED 2020-07~2024-03）`、`张三-任职于→字节跳动（EXPIRED）`
- 现任两期：`张三-担任→首席架构师（CURRENT，VT 空）`、`张三-任职于→美团（CURRENT，VT 空）`
- NEGATED：`张三-担任→字节跳动关联公司职务（NEGATED，VT 空，不瞎填日期）`
- 因果链 3 跳：新冠 → 供应链中断 → 芯片短缺 → 汽车冲击（3 条，FORWARD，`vt_order=CAUSE_BEFORE_EFFECT`）

### 10.3 反例注入（故意构造，校验墙必须正确处理）
| 反例 | 触发规则 | 期望行为 |
|---|---|---|
| `张三-关注→分布式系统` 证据 span `[0,9999]` | W1 越界 | DROPPED，关系不存在 |
| `张三-任职于→创业公司A` `vt_from=2025 > vt_to=2022` | W2 倒序 | WARNING，交换两端保留，`vt_from ≤ vt_to` |
| `张三-认识→马化腾` `confidence=0.12` | W5 低置信 | DROPPED（CONF_DROP=0.30） |

### 10.4 7 条断言
1. NEGATED 必须保留 1 条
2. conf=0.12 低置信必须被 DROP
3. W1 越界那条必须被 DROP
4. W2 倒序那条必须不 DROP 且交换后 `vt_from ≤ vt_to`
5. 3 条因果边全保留，且 `vt_order == CAUSE_BEFORE_EFFECT`
6. 最终关系数 = 4 正常 + 1 NEGATED + 1 倒序修正 = 6
7. 美团 CURRENT 任职的 `vt_from/vt_to` 必须为空（严禁瞎填日期）

### 10.5 最新一次执行结果
```
== 清理后 == {
  n_entities: 9, n_anchors: 5, n_relations: 6, n_causal: 3,
  stats: { W1_RELATION_SPAN_BAD: 1, W2_RELATION_VT_INVERTED: 1, W5_RELATION_CONF_LOW: 1,
           entities_final: 9, timeAnchors_final: 5, relations_final: 6, causalEdges_final: 3 }
}
✅ 全部断言通过
```

---

## 11. 文件清单与变更面

| 文件 | 变更类型 | 职责 |
|---|---|---|
| `core/extraction_schema.py` | **新增** | Pydantic 结构 + 阈值常量（单源） |
| `core/prompt_builder.py` | **重写** | T1/T2 两阶段 Prompt，含先验注入 + Few-Shot + 强 JSON 约束 |
| `core/extraction_validator.py` | **新增** | W1~W5 质量校验墙 + QualityReport 语义 |
| `core/graph_writer.py` | **新增方法**（老 `write()` 不动） | `write_llm_extracted()` 双时态 + 因果 + 时态版本化 CREATE |
| `models/schemas.py` | 扩展字段 | ExtractionRequest 新增 `kosConfig/dlConfig/docId/docMetadata`；ExtractionResult 新增 `timeAnchors/causalEdges/qualityReport/qualityStats/tokenConsumed/duration/writeCount` |
| `api/extraction.py` | **重构主流程**（KOS/DL/结构化三分支零改动） | `/api/extract` LLM 分支走 T1→校验→T2→校验→写库；提供 `_collect_prior_entities` 只读先验 |
| `scripts/test_llm_extraction_quality.py` | **新增** | 离线端到端自测脚本（7 个断言全通过） |

---

## 12. 性能与 Token 预算建议

| 指标 | 建议值 | 备注 |
|---|---|---|
| 单文档 LLM 轮次 | 2（T1+T2） | 极端短文本（<12 字）自动省掉 T2 |
| T1 先验注入上限 | 40 条实体 | `_format_prior_priors(max_items=40)`，避免 prompt 膨胀 |
| Pydantic 结构修正重试 | 1 次（共 2 次机会） | `_llm_call_with_retry(last_error=...)` |
| span 校验开销 | O(N) 纯 Python | 文本 10k 级别可忽略 |
| W4 因果破环循环 | 上限 1000 次 | 实际几十跳因果链 < 1ms |
| Neo4j 写入 | N 次独立 Cypher（非批量） | P2 可改 `UNWIND` 批量，当前单文档 N<500 够用 |

---

## 13. 已知限制与 P2 路线图

1. **PREVENT 类因果**：当前 Schema 支持（direction=PREVENT），但 Few-Shot 暂缺 → P2 补 1 条医疗/政策类预防因果示例
2. **P1 VT-only，TT 未全量**：`createTime` 作为 TT 近似 → P2 加 `tt_from / tt_to` 字段 + 历史版本查询 API
3. **本体 T-Box 演化**：当前只有 A-Box 版本化 → P2 加 `onto_evolution_log` 表 + 概念拆分/合并/弃用操作
4. **W3 近邻消歧**：Jaccard 字符集（对「字节/字节跳动」这种长包含关系有效，但对字形错「腾迅/腾讯」效果弱）→ P2 接 pypinyin + edit distance
5. **批量抽取**：当前 `/api/extract` 单文档 → P2 批处理模式 + 异步任务队列 + 进度回调
6. **人工审核闭环**：qualityReport 目前只读 → P2 回写「已确认/误报」反馈 → LLM SFT 数据集

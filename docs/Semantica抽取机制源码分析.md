# Semantica 抽取机制源码分析

> 分析对象：`semantica/semantic_extract/` 模块（版本对应本地源码）
> 核心文件：`methods.py`（约 2600 行，全部 LLM 抽取实现）、`ner_extractor.py`、`relation_extractor.py`、`triplet_extractor.py`、`schemas.py`

***

## 1. 抽取在整体架构中的位置

Semantica 的知识图谱构建链路为：

```
数据源 (ingest/) → 解析 (parse/) → 分块 (split/) → 抽取 (semantic_extract/) → 去重/规范化 (deduplication/, normalize/) → 图存储 (graph_store/, triplet_store/)
```

`semantic_extract` 是核心语义层，提供五种抽取能力：

| 能力               | 入口类                                                                     | LLM 实现函数                |
| ---------------- | ----------------------------------------------------------------------- | ----------------------- |
| 命名实体识别（NER）      | `NERExtractor`                                                          | `extract_entities_llm`  |
| 关系抽取             | `RelationExtractor`                                                     | `extract_relations_llm` |
| RDF 三元组          | `TripletExtractor`                                                      | `extract_triplets_llm`  |
| 语义网络             | `SemanticNetworkExtractor`                                              | 组合调用上面两者                |
| 事件检测 / 共指消解 / 校验 | `event_detector.py`、`coreference_resolver.py`、`extraction_validator.py` | 辅助组件                    |

***

## 2. 抽取方法体系：多方法 + Fallback 链

每个抽取器在初始化时接受一个方法列表（如 `["pattern", "regex", "rules", "ml", "huggingface", "llm"]`），运行时按顺序尝试，形成 fallback 链（[ner\_extractor.py:364-437](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/ner_extractor.py#L364-L437)）：

1. 逐个方法调用 `get_entity_method(method_name)` 取出实现函数并执行；
2. 某方法失败（异常）→ 记 warning，继续下一个方法；
3. 某方法产出非空结果且**未开启 ensemble\_voting** → 直接返回第一个成功结果；
4. 开启 `ensemble_voting` → 收集所有方法结果做投票合并；
5. 结果按 `min_confidence` 过滤，若配置了 `entity_types` 还会做加权置信度重算（`calculate_weighted_confidence`）。

关系抽取支持的方法更丰富：`pattern / regex / cooccurrence / dependency / huggingface / llm`（[relation\_extractor.py:81-115](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/relation_extractor.py#L81-L115)），其中 `llm` 方法需要外部传入 LLM provider/model/api\_key。

***

## 3. LLM 抽取完整流程（以实体为例）

`extract_entities_llm`（[methods.py:970-1160](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/methods.py#L970-L1160)）的执行步骤：

```
缓存检查 → 文本预校验 → provider 校验（含 API key 环境变量回退）
→ 长文本分块判断 → 构造 prompt → llm.generate_typed(prompt, schema)
→ Pydantic 校验输出 → 转内部 Entity → 写缓存 → 返回
→ 失败时：若为截断错误则 chunk 减半重试；否则 silent_fail 或抛 ProcessingError
```

关键机制：

- **结果缓存**：`_result_cache.get/set`，缓存键包含 provider、model、max\_text\_length、entity\_types、温度等生成参数（[methods.py:995-1006](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/methods.py#L995-L1006)）。

- **API key 解析顺序**：显式参数 → 环境变量 `{PROVIDER}_API_KEY`。

- **长文本分块**：超过 `max_text_length` 时用 `TextSplitter(method="recursive", chunk_overlap=10%)` 切分，**并发**调用单块抽取（`ThreadPoolExecutor` + `resolve_max_workers`），最后把 chunk 偏移量加回实体 span（[methods.py:1169-1228](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/methods.py#L1169-L1228)）。默认上限按 provider 区分：groq/openai/gemini/anthropic/deepseek 为 64000 字符，其余 32000。

- **截断自适应重试**：LLM 报 `length/max_tokens` 错误时，`max_text_length` 减半后重新分块重试（最小 100 字符）。

- **Typed Generation**：所有 LLM 调用走 `llm.generate_typed(prompt, schema=...)`，由 instructor/Pydantic 强制结构化输出，而非裸 JSON 解析。

### 关系抽取的两个特殊处理

1. **Prompt 实体上限**：内部硬编码 `max_entities_prompt = 80`，超出时调用 `filter_entities_for_text` 按文本相关性筛选（[methods.py:1826-1837](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/methods.py#L1826-L1837)），防止 prompt 爆炸。
2. **实体回映射**：LLM 返回的 subject/object 是字符串，通过 `match_entity`（混合相似度匹配）映射回已有 `Entity` 对象；匹配失败则生成 `label="UNKNOWN", metadata={"synthetic": True}` 的合成实体，保证结果不丢失（[methods.py:2092-2108](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/methods.py#L2092-L2108)）。
3. **分块时的实体过滤**：每个 chunk 只传入 span 落在 chunk 边界 ±100 字符内的实体（[methods.py:2180-2184](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/methods.py#L2180-L2184)）。

### 输出解析的鲁棒性

`_parse_relation_result`（[methods.py:2055-2147](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/methods.py#L2055-L2147)）兼容多种 LLM 返回形态：list / dict（`relations`/`data`/`results` 键）/ 单对象；Pydantic schema 层还做了别名兼容（`source→subject`、`target→object`、`label→predicate`、`type→label`、`value/span→text`）和置信度钳制（0-1，字符串转 float 失败回退默认值）。

***

## 4. 抽取提示词原文

抽取主链路（4.1–4.4）的提示词均为 Python f-string 内联在 `methods.py` 中，由「固定指令骨架 + 动态类型指令 + 原文文本」三段拼接；4.5–4.6 为抽取链路之外的语义分块与图谱问答提示词，分别位于 `split/` 和 `context/` 模块。

### 4.1 实体抽取提示词

位置：[methods.py:1092-1115](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/methods.py#L1092-L1115)，schema 为 `EntitiesResponse`

```
Extract named entities from the provided text.
Return the result as a JSON object with an "entities" key containing the list of entities.
Each entity should have 'text', 'label', and 'confidence' fields.

IMPORTANT: 
- Return a FLAT LIST of entities. 
- DO NOT group entities by type.
- The output structure must exactly match: { "entities": [ { "text": "...", "label": "...", "confidence": ... }, ... ] }

Example output (JSON format only):
{
  "entities": [
    {"text": "Entity Name", "label": "CATEGORY", "confidence": 0.95},
    {"text": "Another Entity", "label": "OTHER_CATEGORY", "confidence": 0.90}
  ]
}

Instructions:
1. Extract entities ONLY from the text provided below.
2. Do not include any entities from the example above.
3. {entity_types_instruction}

Text to extract from:
{text}
```

其中 `entity_types_instruction` 有两种形态：

**用户指定了** **`entity_types`** **时：**

```
Preferred entity types: {类型列表}.
You may also use related or similar entity types if they better match the context (e.g., variations, synonyms, or domain-specific types).
If an entity doesn't fit any of the preferred types, use the most appropriate type from the preferred list or a closely related type.
```

**未指定时（默认，含 few-shot 类型示例）：**

```
Entity types should be one of: 
- PERSON (People, names, roles)
- ORG (Companies, organizations, institutions, brands)
- GPE (Countries, cities, states, locations)
- DATE (Dates, years, time periods)
- EVENT (Named events, conferences)
- PRODUCT (Software, hardware, vehicles)
- CONCEPT (Abstract ideas, technologies)

Use the most appropriate type for each entity.
Examples:
- 'Microsoft' is an ORG
- 'Satya Nadella' is a PERSON
- Job titles/roles like 'CEO', 'CTO', 'President', 'Engineer' are CONCEPT unless part of a person's name
- 'Python' is a PRODUCT or CONCEPT depending on context.
```

### 4.2 关系抽取提示词（基础版）

位置：[methods.py:1864-1884](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/methods.py#L1864-L1884)，schema 为 `RelationsResponse`

```
Extract relations between entities from the provided text.
Return the result as a JSON object with a "relations" key containing the list of relations.
Each relation must have 'subject', 'predicate', and 'object' fields.

Example output (JSON format only):
{
  "relations": [
    {"subject": "Entity A", "predicate": "related_to", "object": "Entity B", "confidence": 0.95},
    {"subject": "Subject Entity", "predicate": "action_verb", "object": "Object Entity", "confidence": 0.90}
  ]
}

Instructions:
1. Extract relations ONLY from the text provided below.
2. Do not include any relations from the example above.
3. Use the provided entities list as a reference for subjects and objects.
4. {relation_types_instruction}

Text to extract from:
{text}
Entities found in text: {entities_str}
```

`relation_types_instruction` 默认形态：

```
Extract meaningful relationships between entities. Use appropriate relation types that accurately describe how entities are connected.
Common relation types include: related_to, part_of, located_in, created_by, uses, depends_on, interacts_with, and similar variations.
```

（用户自定义时同实体的"Preferred relation types"句式。`entities_str` 格式为 `"文本 (LABEL), 文本 (LABEL), ..."`。）

### 4.3 关系抽取提示词（时间有效性扩展版）

位置：[methods.py:1887-1943](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/methods.py#L1887-L1943)，`extract_temporal_bounds=True` 时启用，schema 为 `RelationsWithTemporalResponse`。这是全库最精心设计的提示词，包含**置信度标定表**和 **5 个 few-shot 示例**：

```
Extract relations between entities from the provided text, along with temporal validity information for each relation.
Return the result as a JSON object with a "relations" key. Each relation must have:
'subject', 'predicate', 'object', 'confidence', 'valid_from', 'valid_until', 'temporal_confidence', 'temporal_source_text'.

TEMPORAL EXTRACTION RULES:
- valid_from: ISO 8601 date or exact phrase from the text for when this relation became valid. Set to null if no temporal signal is present.
- valid_until: ISO 8601 date or exact phrase for when this relation ceased. Set to null if open-ended or absent.
- temporal_confidence (float 0.0–1.0) — calibrated as follows:
    1.00 = full ISO date ("2022-03-15", "March 15, 2022")
    0.90 = explicit year + month ("March 2022", "2022-03")
    0.85 = explicit year only ("in 2022", "since 2021", "from 2019")
    0.75 = quarter ("Q3 2023", "Q2 2021")
    0.65 = named season or approximate range ("summer 2022", "early 2020s", "mid-2022")
    0.50 = vague relative with computable anchor ("last year", "three months ago")
    0.35 = highly vague relative ("recently", "years ago", "in the past")
    0.00 = no temporal signal present for this relation
- temporal_source_text: the EXACT verbatim substring from the source text that contains the temporal signal. Set to null when temporal_confidence is 0.0.

IMPORTANT: Do NOT invent or guess dates. If the text contains no temporal signal for a relation, set valid_from and valid_until to null and temporal_confidence to 0.0.

Few-shot examples (do NOT include these in your output):
  Text: "Apple acquired Beats in May 2014."
  → valid_from: "2014-05-01", valid_until: null, temporal_confidence: 0.90, temporal_source_text: "May 2014"

  Text: "The CEO has led the company since Q3 2020."
  → valid_from: "Q3 2020", valid_until: null, temporal_confidence: 0.75, temporal_source_text: "since Q3 2020"

  Text: "Last year, Google partnered with Samsung."
  → valid_from: "last year", valid_until: null, temporal_confidence: 0.50, temporal_source_text: "Last year"

  Text: "The firm was under enhanced supervision between Q2 and Q4 2021."
  → valid_from: "Q2 2021", valid_until: "Q4 2021", temporal_confidence: 0.75, temporal_source_text: "between Q2 and Q4 2021"

  Text: "Microsoft develops Windows."
  → valid_from: null, valid_until: null, temporal_confidence: 0.00, temporal_source_text: null

Example JSON output format:
{
  "relations": [
    {
      "subject": "Apple", "predicate": "acquired", "object": "Beats",
      "confidence": 0.97,
      "valid_from": "2014-05-01", "valid_until": null,
      "temporal_confidence": 0.90, "temporal_source_text": "May 2014"
    }
  ]
}

Instructions:
1. Extract relations ONLY from the text provided below.
2. Do not include any relations from the examples above.
3. Use the provided entities list as a reference for subjects and objects.
4. {relation_types_instruction}

Text to extract from:
{text}
Entities found in text: {entities_str}
```

解析侧对应处理：时间字段写入 relation metadata；`temporal_confidence < 0.5` 但仍有日期时打 warning 日志（不抑制结果）（[methods.py:2116-2135](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/methods.py#L2116-L2135)）。

### 4.4 RDF 三元组抽取提示词

位置：[methods.py:2490-2509](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/methods.py#L2490-L2509)，schema 为 `TripletsResponse`

```
Extract RDF triplets (subject-predicate-object) from the provided text.
Return the result as a JSON object with a "triplets" key containing the list of triplets.
Each triplet must have 'subject', 'predicate', and 'object' fields.

Example output (JSON format only):
{
  "triplets": [
    {"subject": "Subject", "predicate": "predicate_relation", "object": "Object", "confidence": 0.99},
    {"subject": "Concept A", "predicate": "is_a", "object": "Concept B", "confidence": 0.95}
  ]
}

Instructions:
1. Extract triplets ONLY from the text provided below.
2. Do not include any triplets from the example above.
3. Ensure subjects and objects are substrings from the text.
4. {triplet_types_instruction}

Text to extract from:
{text}
```

`triplet_types_instruction` 默认形态：

```
Extract meaningful triplets (subject-predicate-object). Use appropriate predicates that accurately describe the relationship.
Common predicates include: is_a, part_of, has_property, related_to, caused_by, etc.
```

### 4.5 语义分块提示词（LLM 辅助切分）

位置：[split/methods.py:768-775](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/split/methods.py#L768-L775)，函数 `split_llm`

**执行流程**：先用 `split_recursive` 做粗切分（无 overlap），再对每个粗块调用 LLM 寻找更优的语义切分点。这是全库唯一走 `llm_provider.generate()`（纯文本生成）而非 `generate_typed()`（结构化生成）的提示词，输出解析用逗号分隔整数索引，解析失败则回退使用粗块。

提示词源码原文：

```python
prompt = f"""Analyze the following text and identify the best split points 
(sentence boundaries) that would create semantically coherent chunks of approximately 
{chunk_size} characters. Return only the indices where splits should occur, 
separated by commas:

{rough_chunk.text[:2000]}

Split indices:"""
```

说明：

- `{chunk_size}`：目标块大小（默认 1000 字符）；

- 输入文本截断为前 2000 字符；

- 期望输出：逗号分隔的切分位置索引，如 `156, 423, 891`；

- 容错链：LLM 失败 → 回退 recursive 分块（[split/methods.py:792-796](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/split/methods.py#L792-L796)）。

当前实现的一个局限：`split_indices` 解析成功后实际仍 append 原粗块（`refined_chunks.append(rough_chunk)`，[split/methods.py:786](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/split/methods.py#L786)），即 LLM 返回的切分索引尚未真正用于重切，属于占位实现。

### 4.6 图谱问答提示词（检索增强生成）

位置：[context/context\_retriever.py:1461-1477](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/context/context_retriever.py#L1461-L1477)，`query_with_reasoning` 链路的最终生成步骤

**执行流程**：`retrieve()` 检索上下文 → 构建多跳推理路径（实体 `--[关系类型]-->` 实体的链式表达）→ 拼装以下提示词 → `llm_provider.generate()` 生成自然语言答案。这是抽取的反方向：把图中抽取出的实体和关系重新组装成答案。

提示词源码原文：

```python
prompt = f"""You are a knowledge graph reasoning assistant. Answer the user's question based on the retrieved context and reasoning paths from the knowledge graph.

User Question: {query}

{temporal_header}Retrieved Context:
{context_text}

{reasoning_text}

Instructions:
1. Answer the question using the retrieved context and reasoning paths
2. Cite specific entities and relationships from the reasoning paths
3. Explain the multi-hop connections when relevant
4. Be concise but comprehensive
5. If information is not available in the context, say so

Answer:"""
```

动态拼装部分：

| 占位符                 | 内容    | 构造逻辑                                                                                                                                                                                                                                                                                      |
| ------------------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `{query}`           | 用户问题  | 原样注入                                                                                                                                                                                                                                                                                      |
| `{temporal_header}` | 时间快照头 | 仅 `at_time` 参数存在时生成，默认模板 `[Graph context valid as of: {at_time} UTC \| Source: {source}]`；用 `str.replace` 而非 `.format()` 做占位符替换，防止注入（[context\_retriever.py:1425-1432](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/context/context_retriever.py#L1425-L1432)） |
| `{context_text}`    | 检索上下文 | 最多取前 5 条，格式 `Context {i} (Score: {分数}):\n{内容}`                                                                                                                                                                                                                                            |
| `{reasoning_text}`  | 推理路径  | 最多 3 条多跳路径，格式 `Path {i}: 实体A --[关系]--> 实体B --[关系]--> 实体C`                                                                                                                                                                                                                                 |

防幻觉设计：

- 指令 2 要求引用推理路径中的具体实体和关系（强制溯源）；

- 指令 5 要求上下文缺失时明说，不许编造；

- LLM 生成失败时回退为返回检索上下文摘要而非错误（[context\_retriever.py:1482-1485](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/context/context_retriever.py#L1482-L1485)）。

***

## 5. 输出 Schema（Pydantic 强约束）

定义在 [schemas.py](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/schemas.py)，四个顶层包装类：

| Schema                          | 字段                                         | 用途     |
| ------------------------------- | ------------------------------------------ | ------ |
| `EntitiesResponse`              | `entities: List[EntityOut]`                | 实体抽取   |
| `RelationsResponse`             | `relations: List[RelationOut]`             | 关系抽取   |
| `TripletsResponse`              | `triplets: List[TripletOut]`               | 三元组抽取  |
| `RelationsWithTemporalResponse` | `relations: List[RelationWithTemporalOut]` | 时间扩展关系 |

Schema 层的鲁棒性设计（以 `EntityOut` 为例）：

- `extra="ignore"`：忽略 LLM 多输出的字段；

- 别名归一（`model_validator`）：`type→label`、`value/span→text`、`source→subject`、`target→object`、`label→predicate`；

- 置信度清洗：字符串转 float、钳制到 \[0,1]、失败回退 0.9；

- 文本清洗：`text.strip()`。

内部数据结构为 dataclass 三元组 `Entity / Relation / Triplet`（[types.py:12-52](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/types.py#L12-L52)），metadata 中统一记录 `provider / model / extraction_method` 溯源信息。

***

## 6. 从抽取到图谱

`SemanticNetworkExtractor`（[semantic\_network\_extractor.py:327-564](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/semantic_network_extractor.py#L327-L564)）串联全流程：

1. 未提供实体/关系时，自动实例化 `NERExtractor` + `RelationExtractor` 先行抽取；
2. 实体 → `SemanticNode`，关系 → `SemanticEdge`；
3. 记录网络元数据（节点/边数量、实体类型分布、关系类型分布），供下游 `graph_store` 落库和 `deduplication` 去重使用。

***

## 7. 关键配置项

[config.py:50-65](file:///Users/Yuan/xy_workspace/7.downloads/service/semantica/semantica/semantic_extract/config.py#L50-L65)：

| 配置                                                        | 作用                                 |
| --------------------------------------------------------- | ---------------------------------- |
| `max_workers` / `resolve_max_workers()`                   | 分块并发抽取的线程数                         |
| `enable_batching` / `batch_size` / `max_tokens_per_batch` | 批量文本抽取的吞吐优化                        |
| `min_confidence`                                          | 抽取器级置信度过滤阈值                        |
| `ensemble_voting`                                         | 是否聚合多方法结果投票                        |
| `max_entities_prompt = 80`                                | 关系抽取 prompt 中实体数上限（硬编码）            |
| `max_text_length`                                         | 分块阈值，provider 相关（主流 64k 字符，其余 32k） |
| `extract_temporal_bounds`                                 | 是否启用时间有效性扩展抽取                      |

***

## 8. 设计要点总结

1. **提示词极简 + Schema 强约束**：prompt 只给任务描述、输出格式示例和 3-4 条指令，结构正确性完全交给 instructor/Pydantic typed generation 保障，而非在 prompt 中堆 JSON 修复指令。
2. **三段式动态拼装**：固定骨架 + 可替换的类型指令（用户自定义优先，否则用内置默认类型集）+ 原文文本；三种抽取任务的骨架高度一致，降低维护成本。
3. **默认类型体系**：实体 7 类（PERSON/ORG/GPE/DATE/EVENT/PRODUCT/CONCEPT，OntoNotes 风格）；关系开放词表（related\_to/part\_of/located\_in/created\_by/uses/depends\_on/interacts\_with）；三元组谓词开放词表（is\_a/part\_of/has\_property/related\_to/caused\_by）。
4. **多层容错**：方法级 fallback 链 → 截断自动减半重试 → 实体回映射失败合成 UNKNOWN 实体 → schema 别名/钳制清洗 → `silent_fail` 开关。
5. **时间抽取是唯一带标定体系的提示词**：8 档置信度标定表 + 5 个覆盖不同时间粒度的 few-shot，配合"禁止编造日期"的硬性约束，是防幻觉的代表性设计。


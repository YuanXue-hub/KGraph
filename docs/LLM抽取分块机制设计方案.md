# LLM 抽取分块机制设计方案

> 参考 Semantica 长文本兜底分块机制，结合 KGraph 两阶段流水线特性设计。

## 一、背景

### 1.1 现状

KGraph 当前 LLM 抽取流水线为**两阶段单调用**：

```
阶段1：全文 → LLM → 实体 + 时间锚点 + 指代链
阶段2：全文 + 实体表 → LLM → 关系
```

文本直接整段传给 LLM，**无分块机制**。当文本超过 LLM 上下文窗口时：
- LLM 直接截断（丢失尾部信息）
- 或报 `max_tokens` / `length` 错误
- 长文本中实体和关系召回率显著下降

### 1.2 Semantica 方案回顾

Semantica 采用 **"全流程分块 + 并发抽取 + 结果合并"**：

```
全文 → 递归分块(10% overlap) → 并发抽取(N chunk × 2阶段) → 结果合并 → overlap二次抽取补关系
```

## 二、Semantica 分块机制的缺点分析

### 2.1 跨 chunk 实体不一致

同一现实实体在不同 chunk 可能：
- `canonicalName` 不同（chunk1 抽 "字节跳动"，chunk2 抽 "字节"）
- `type` 不同（chunk1 标 "公司"，chunk2 标 "组织"）

合并时以 `(canonicalName, type)` 为键去重，导致**同一实体产生多个节点**。

### 2.2 跨 chunk 关系丢失

每个 chunk 独立抽关系，关系的 subject/object 只能引用当前 chunk 的实体表。实体 A 在 chunk1，实体 B 在 chunk2，关系 A→B **必然丢失**。Semantica 用 overlap 区域二次抽取补全，但仅覆盖边界附近，**中段跨 chunk 关系仍丢失**。

### 2.3 overlap 二次抽取成本高

每对相邻 chunk 的 overlap 区域都要再调一次 LLM 抽关系，N 个 chunk 需要 N-1 次额外调用，token 成本和延迟显著增加。

### 2.4 指代消解跨 chunk 断裂

指代词（如"该公司"）和其先行词可能在不同 chunk，导致解析失效。

### 2.5 事件时序跨 chunk 丢失

事件实体的 `vt_from` 基于 chunk 内时间锚点推断，无法跨 chunk 排序。

### 2.6 置信度无法聚合

同一关系在多个 chunk 被抽出时不合并，全部保留，导致图谱重复边 + 评估虚高。

## 三、KGraph 分块设计方案

### 3.1 核心思路：两阶段都分块，阶段2注入全局实体表

阶段1分块的前提是文本超长，因此阶段2给全文也必然超长，**两阶段都必须分块**。

与 Semantica 的关键区别：**阶段2每个 chunk 注入的是阶段1合并后的全局实体表**，而非 chunk 内实体。

```
阶段1：全文 → 分块 → 并发抽实体 → 合并全局实体表
阶段2：全文 → 分块 → 并发抽关系(每个chunk注入全局实体表) → 合并关系(去重)
```

**为什么跨 chunk 关系不会丢失**：
- Semantica：chunk2 的关系 subject/object 只能引用 chunk2 内的实体 → 跨 chunk 关系丢失
- KGraph：每个 chunk 抽关系时都能看到**全局实体表**，只要关系描述（evidenceText）在某个 chunk 中出现，subject/object 就能解析到全局实体 → 跨 chunk 关系不丢失

### 3.2 上下文窗口限制：三层防护

#### 第一层：预计算 chunk_size（主防护）

分块前根据模型上下文窗口动态计算 chunk_size：

```
chunk_size = (context_window - prompt_overhead - output_budget - entity_table_tokens) × chars_per_token × safety_factor
```

| 参数 | 含义 | 取值 |
|------|------|------|
| `context_window` | LLM 上下文窗口（tokens） | 按模型配置：Ollama 32K / DeepSeek 64K / Qwen 128K / GLM 128K / OpenAI 128K |
| `prompt_overhead` | prompt 固定开销 | 阶段1: 3K tokens，阶段2: 3K tokens |
| `output_budget` | 输出 token 预算 | 阶段1: 4K tokens，阶段2: 8K tokens |
| `entity_table_tokens` | 阶段2注入的全局实体表占用 | 实体数 × 50 tokens |
| `chars_per_token` | 中文 token 换算系数 | 0.6（1 token ≈ 1.6 中文字） |
| `safety_factor` | 安全系数 | 0.7（留 30% 余量） |

```python
def _compute_chunk_size(llm_client, stage: str, entity_count: int = 0) -> int:
    context_window = get_context_window(llm_client)
    prompt_overhead = 3000
    output_budget = 4000 if stage == "entities" else 8000
    entity_table_tokens = entity_count * 50 if stage == "relations" else 0
    available_tokens = context_window - prompt_overhead - output_budget - entity_table_tokens
    chunk_size = int(available_tokens * 0.6 * 0.7)
    return max(2000, min(100000, chunk_size))  # 边界：2K~100K 字符
```

**阶段1 vs 阶段2 阈值不同**：阶段2要注入全局实体表，阈值更小。

数值示例（DeepSeek-V3，64K context）：

| 阶段 | chunk_size |
|------|-----------|
| 阶段1 | ≈ 24K 字符 |
| 阶段2(50实体) | ≈ 21K 字符 |
| 阶段2(200实体) | ≈ 18K 字符 |

#### 第二层：截断自适应重试（兜底）

预计算的 chunk_size 仍可能因 prompt 估算不准而超限。LLM 报 `length` / `max_tokens` 错误时，**当前 chunk 减半重试**（最多3次）：

```python
def extract_with_retry(llm_client, chunk, ...):
    current = chunk
    for attempt in range(3):
        try:
            return do_extract(llm_client, current, ...)
        except LLMError as e:
            if "length" in str(e).lower() or "max_tokens" in str(e).lower():
                current = current[:len(current)//2]
                if len(current) < 1000:
                    raise
                continue
            raise
```

#### 第三层：max_tokens 限制

调用 LLM 时显式设置 `max_tokens`（推理模型 32768，普通 16384），避免输出过长挤占输入空间。

### 3.3 模型上下文窗口来源

**默认不需要用户配置**，系统按供应商自动给默认值；支持手动覆盖。

```python
PROVIDER_CONTEXT_DEFAULTS = {
    "deepseek": 64000,
    "qwen": 128000,
    "glm": 128000,
    "openai": 128000,
    "ollama": 32000,
}

def get_context_window(model_config) -> int:
    # 1. 优先用数据库 llm_model.context_window 字段（手动配置覆盖）
    if model_config.get("context_window"):
        return model_config["context_window"]
    # 2. NULL 时按供应商默认值兜底（大部分场景走这里，无需用户配置）
    return PROVIDER_CONTEXT_DEFAULTS.get(model_config["provider"], 32000)
```

#### 数据库字段

`llm_model` 表新增可空字段：

```sql
ALTER TABLE llm_model ADD COLUMN context_window INT DEFAULT NULL COMMENT '上下文窗口(tokens)，NULL则按供应商默认';
```

| 字段值 | 行为 |
|--------|------|
| NULL（默认） | 用供应商默认值，无需用户配置 |
| 有值（如 128000） | 用用户填的值，覆盖默认 |

#### 各供应商默认值

| 供应商 | 默认 context_window | 说明 |
|--------|-------------------|------|
| deepseek | 64000 | DeepSeek Chat 默认 64K |
| qwen | 128000 | Qwen 系列默认 128K |
| glm | 128000 | GLM 系列默认 128K |
| openai | 128000 | GPT-4o 默认 128K |
| ollama | 32000 | Ollama 模型不固定，保守 32K |
| 未知 | 32000 | 兜底 |

#### 何时需要手动配置

| 场景 | 操作 |
|------|------|
| 用默认模型 | 不用管，自动用默认值 |
| 用了更大窗口的模型（如 deepseek-v4-pro 128K） | 填 128000 覆盖 |
| 用了更小窗口的模型 | 填实际窗口大小 |
| Ollama 跑小模型（如 8K） | 填 8000，避免分块过大 |

### 3.4 分块策略

复用 KGraph 已有的 `RecursiveSplitter`：

```python
splitter = RecursiveSplitter(
    chunk_size=chunk_size,
    chunk_overlap=min(int(chunk_size * 0.1), 2000),  # 10% 重叠，最大 2000 字符
    separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", " ", ""],
)
chunks = splitter.split(text)
```

### 3.5 触发条件

```python
if len(text) <= chunk_size:
    # 未超阈值：直接单调用，无分块、无并发、无合并开销
    return extract_entities(llm_client, text, ...)
else:
    # 超阈值：分块流程
    ...
```

两个阶段独立判断，可能出现"阶段1单调用、阶段2分块"（阶段2阈值更小）。

### 3.6 并发抽取

```python
def run_concurrent(fn, chunks, *args, **kwargs):
    results = [None] * len(chunks)
    with ThreadPoolExecutor(max_workers=min(len(chunks), 6)) as executor:
        future_to_idx = {executor.submit(fn, chunk, *args, **kwargs): i for i, chunk in enumerate(chunks)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = None  # 失败标记，不阻塞其他
    return results
```

### 3.7 阶段1合并（实体 + 锚点 + 指代链）

```python
def merge_stage1(chunk_results, rep):
    merged_entities = {}   # canonicalName → ExtractedEntity
    merged_anchors = []
    merged_alias_map = {}

    for result in chunk_results:
        if result is None:
            continue
        # 实体：canonicalName 去重，evidenceText 用 | 拼接
        for e in result.entities:
            key = e.canonicalName
            if key not in merged_entities:
                merged_entities[key] = e
            else:
                existing = merged_entities[key]
                if e.type != existing.type:
                    rep.add("WARNING", "W3_TYPE_CONFLICT", f"类型冲突: {existing.type} vs {e.type}")
                if e.evidenceText and e.evidenceText not in existing.evidenceText.split(" | "):
                    existing.evidenceText = f"{existing.evidenceText} | {e.evidenceText}"
        # 锚点：直接拼接
        merged_anchors.extend(result.time_anchors)
        # 指代链：别名取并集
        for alias, canonical in result.alias_map.items():
            if alias not in merged_alias_map:
                merged_alias_map[alias] = canonical

    return EntityStageResult(
        entities=list(merged_entities.values()),
        time_anchors=merged_anchors,
        alias_map=merged_alias_map,
        doc_time=chunk_results[0].doc_time if chunk_results[0] else None,
    )
```

| 元素 | 合并方式 | 理由 |
|------|---------|------|
| 实体 | canonicalName 去重，evidenceText 拼接 | 保留所有表述 |
| 时间锚点 | 直接拼接 | 多次出现是多次证据 |
| 指代链 | 别名取并集 | 别名汇总 |
| type 冲突 | 保留首次 + WARNING | 不丢弃，供人工审核 |

### 3.8 阶段2合并（关系去重）

```python
def merge_stage2(chunk_relations_list, rep):
    merged = {}  # (subject, predicate, object) → ExtractedRelation
    for rels in chunk_relations_list:
        if rels is None:
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
                    existing.evidenceText = f"{existing.evidenceText} | {r.evidenceText}"
                if r.vt_from and (not existing.vt_from or r.vt_from < existing.vt_from):
                    existing.vt_from = r.vt_from
                if r.vt_to and (not existing.vt_to or r.vt_to > existing.vt_to):
                    existing.vt_to = r.vt_to
    return list(merged.values())
```

| 字段 | 合并方式 | 理由 |
|------|---------|------|
| confidence | 取最大值 | 最可信的那次 |
| evidenceText | ` \| ` 拼接 | 多 chunk 证据汇总 |
| vt_from | 取最早 | 有效时间起点 |
| vt_to | 取最晚 | 有效时间终点 |

### 3.9 失败处理

| 场景 | 处理 |
|------|------|
| 单个 chunk 失败 | 同步重试1次（退避1秒），仍失败则记录 ERROR 跳过 |
| 全部 chunk 失败 | 抛 RuntimeError |
| 部分失败导致实体缺失 | 阶段2关系中引用缺失实体的关系被丢弃，记 WARNING |

### 3.10 质量报告合并

每个 chunk 的 QualityReport 合并时，给 issue 加 `[chunkN]` 前缀方便定位。

### 3.11 完整流程图

```
                    ┌─────────────────┐
                    │  计算 chunk_size  │ ← 模型 context_window
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │  len(text) > ?   │
                    └───┬─────────┬───┘
                   是  │         │  否
                       ▼         ▼
              ┌────────────┐  ┌────────────┐
              │  分块(N)    │  │  单调用      │
              └─────┬──────┘  └─────┬──────┘
                    ▼               ▼
              ┌─────────────────────────┐
              │  阶段1并发抽实体          │
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │  阶段1合并               │
              │  ·实体去重(evidenceText拼)│
              │  ·锚点拼接               │
              │  ·指代链合并             │
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │  计算阶段2 chunk_size    │ ← 实体数 × 50 tokens
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │  阶段2分块抽关系          │
              │  (注入全局实体表)         │
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │  阶段2合并               │
              │  ·关系去重               │
              │  ·evidenceText拼接       │
              │  ·confidence取max        │
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │  W1-W5 校验管道           │
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │  写入 Neo4j               │
              └─────────────────────────┘
```

## 四、与 Semantica 对比

| 维度 | Semantica | KGraph |
|------|-----------|--------|
| 分块范围 | 阶段1 + 阶段2 | 阶段1 + 阶段2 |
| 阶段2实体表 | chunk 内实体 | **全局实体表** |
| 跨 chunk 关系 | overlap 二次抽取（不全） | 全局实体表，**不丢失** |
| 实体去重键 | (canonicalName, type) | canonicalName |
| 关系去重 | 不去重 | (subject, predicate, object) |
| evidenceText 合并 | 各自保留 | ` \| ` 拼接 |
| confidence 聚合 | 不处理 | 取 max |
| span 偏移回加 | 需要 | 不需要（弃用 span） |
| 指代消解 | 跨 chunk 断裂 | 合并后全局 alias_map |
| 失败处理 | 抛异常中断 | 记录 ERROR 跳过 |
| LLM 调用次数 | 2N + (N-1) | **2N** |

## 五、实施计划

### P0：基础分块（本次实现）

1. `llm_model` 表加 `context_window` 字段 + 预设值
2. `extraction_schema.py` 的 `LlmExtractionPayload` 已有 `aliasMap`
3. `extraction_service.py` 新增 `_compute_chunk_size()`、`run_concurrent()`、`merge_stage1()`、`merge_stage2()`
4. 阶段1/阶段2 入口加 `should_chunk` 判断
5. 复用 `RecursiveSplitter` 分块
6. 截断自适应重试
7. 质量管道不变

### P1：优化项

1. 分块阈值/并发度前端可配置
2. type 冲突时用 LLM 二次判定
3. Ollama 动态查询 `num_ctx`
4. 分块抽取进度 SSE 上报

## 六、风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 并发导致 LLM API 限流 | max_workers=6 + 指数退避重试 |
| 实体 type 冲突 | 保留首次 + WARNING，人工审核 |
| 单个 chunk 失败导致实体缺失 | 同步重试1次；关系引用缺失实体时丢弃 + WARNING |
| 并发结果顺序错乱 | 按 chunk_idx 归位后再合并 |
| evidenceText 拼接过长 | Neo4j 写入时截断 1000 字符 |

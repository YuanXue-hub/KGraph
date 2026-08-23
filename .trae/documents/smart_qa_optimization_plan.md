# 智能问答模块优化方案

## 一、代码库调研结论（现状分析）

### 1.1 全链路架构

```
前端 (Chat.vue)         Java (ChatController/Service)      Python (chat_agent.py)
    │                          │                                    │
    │  fetch('/api/v1/...')    │  WebClient SSE Proxy               │  LangGraph Agent
    │ ──────────────────────► │ ──────────────────────────────►   │
    │  SSE text/event-stream  │  Flux<ServerSentEvent<String>>     │  astream_events v2
    │ ◄────────────────────── │ ◄──────────────────────────────   │
    │                          │                                    │
```

### 1.2 各模块职责

| 模块 | 位置 | 现状 |
|---|---|---|
| 前端 Chat.vue | `frontend/src/views/Chat.vue` | 会话列表 + 消息流 + 打字机 + SSE 解析。已有：思考区、工具调用卡片、新建/切换/删除会话、模型选择、快捷问题卡片 |
| Java ChatController | `src/main/java/.../ChatController.java:67-86` | SSE 接口入口，鉴权取 userId，兼容 Long→String modelId |
| Java ChatServiceImpl | `src/main/java/.../service/Impl/ChatServiceImpl.java:32-60` | WebClient 透传 Python SSE，60s 硬超时，无 retry/背压/重试 |
| Python chat_agent.py | `pybackend/api/chat_agent.py` | LangGraph + astream_events v2 分 thinking/tool_call/answer 三阶段 SSE，直答 + on_chain_end 兜底保存记忆 |
| Agent 工具集 agent_tools.py | `pybackend/core/agent_tools.py:41-200` | 6 个 Neo4j 查询工具：search/getDetail/getRelations/getEntitiesByType/listEntityTypes/getGraphStats |
| 记忆管理 memory_manager.py | `pybackend/core/memory_manager.py` | Redis（TTL=次日 0 点）+ MySQL 双层，已做 userId 隔离 |
| KOS 词表 | `pybackend/core/kos_extractor.py` | 5 大范畴 1125 术语 + 71 组织/45 专家/49 期刊，抽词接口在 `/api/kos/extract`，**但未接入问答链路** |

### 1.3 已识别的问题与可优化点（按 P0→P3 排序）

#### P0 —— 体验与效果硬伤

| # | 问题 | 影响 | 根因 |
|---|---|---|---|
| **P0-1** | **KOS 词表与实体识别能力**完全未接入问答环节 | Agent 查询实体完全依赖 LLM 自己提取关键词到 `search_entities(model_id, keyword)`，LLM 容易把多字词拆错（如"杂交水稻"只搜"水稻"，"钟南山院士"搜"钟南山院士"整句），KOS 扩充的 1125 词 + 165 NER 完全未用 | chat_agent.py 从未 `from core.kos_extractor import ...` |
| **P0-2** | **SSE 超时 60s 硬断**，长思考（deep-reasoning 大模型 + 多次工具调用）会被 Java 层截断 | 问题较深时 LLM 思考 + Neo4j 查询 + 总结很容易超过 60s，用户看到半断的流，且记忆保存是 `finally` 里走但在 SSE 断开后 Python 可能收到 CancelledError 导致记忆丢失 | ChatServiceImpl.java:57 `Duration.ofSeconds(60)` |
| **P0-3** | **会话标题不智能**，新建后显示 sessionId 或默认"新对话"  | 从列表里完全无法区分内容；必须等第一次回答完成后自动生成标题才好看 | 创建会话接口直接返回时间戳随机串，没有"自动生成标题"流程 |
| **P0-4** | **工具调用结果不进记忆**，历史上下文里只有"user + ai 回答"，**缺少 tool_call 过程** | 跨轮对话时 Agent 看到历史里的"回答"但不知道这个回答是通过什么工具查到的，可能重复调工具或得出矛盾结论 | memory_manager.add_memory 只写 role=user / role=ai，tool_call 事件未序列化写入 |

#### P1 —— 问答质量提升

| # | 问题 | 影响 |
|---|---|---|
| **P1-1** | 图谱检索**只做 `name CONTAINS keyword`**，没有按实体类型/别名/向量相似度召回 | 同义表述、简称、名字写错一点就查不到 |
| **P1-2** | System Prompt 是**硬编码静态 Prompt**，与当前选中的图谱模型元数据（类型、关系、规模）**完全解耦** | Agent 不知道这个模型里有哪些类型可以选，瞎调用 `get_entities_by_type("人物")` 但模型里可能没有"人物"类型，只有"专家学者" |
| **P1-3** | 无**多轮上下文引用能力**：用户说"它的作者是谁"，Agent 容易找不到"它"的指代 | 复杂多轮体验差 |
| **P1-4** | 工具调用次数硬限 3 次且**无结构化规划**，Agent 经常漏查关系或属性 | 复杂问题回答信息不全 |
| **P1-5** | **无"引用来源"**，回答后无法告诉用户"这个信息来自图谱中哪 3 个实体 / 哪几条关系" | 知识溯源为零，用户不信任 |

#### P2 —— 稳定性与性能

| # | 问题 | 影响 |
|---|---|---|
| **P2-1** | WebClient SSE proxy：无 reconnect 机制，前端断一次就永远停住 | 网络抖动体验差 |
| **P2-2** | `neo4j driver.session()` **每次查询都开新 session**，没有 session 池化 | 并发高时资源吃紧 |
| **P2-3** | 历史消息全量塞入 prompt（无长度裁剪），消息多了会超 token 上限，或效果急剧下降 | 长会话容易崩 |
| **P2-4** | 删除会话：Java 层直接代理到 Python，Java 自身的 `ChatHistoryMapper.xml / ChatHistoryService` **可能没有生效**（删除 / 列表 / 消息全走 Python 绕过了 Java 存储层），双层存储概念上"Java 也有表"但全链路只有 Python 在用 MySQL 表 | 架构不一致，未来做 Java 端数据看板 / 审计无数据源 |

#### P3 —— 产品体验与交互

| # | 问题 | 影响 |
|---|---|---|
| **P3-1** | 输入框**不支持 Enter 发送 / Shift+Enter 换行**（需要看 Chat.vue 实际实现），**无 Markdown 代码高亮**，**无数学公式渲染**，**无复制按钮** | 交互体验与主流 AI 产品有差距 |
| **P3-2** | 快捷问题卡片是**硬编码 3 个通用问题**，与所选图谱模型无关 | 对具体模型没启发作用 |
| **P3-3** | **无停止按钮**：一旦点了发送必须等整个流程跑完，后悔也停不掉 | 浪费 token 与时间 |
| **P3-4** | 思考区默认展开占满视野，**无法一键折叠/展开** | 长思考时用户很难看答案 |
| **P3-5** | 工具调用的 **input/output 是 JSON 字符串** 直接显示，没有做格式化/语法高亮/折叠 | 非技术用户看不懂 |

---

## 二、建议优化项（按优先级分档）

### 方案 A：P0 必做（投入少、收益大）

| 编号 | 优化项 | 内容要点 | 涉及文件 |
|---|---|---|---|
| **A-1** | **KOS + NER 接入问答：意图理解前置预处理** | 在 `chat_agent.py` 接收用户问题后，先走 `kos_extractor.extract_terms` + `extract_named_entities`，把抽取出的"术语 + 候选实体"拼到 System Prompt 的 `<CONTEXT>` 里，给 Agent 2-3 个"建议搜索关键词"，甚至可以把"找到的专家学者/组织机构/期刊"直接提示 Agent 去 `get_entity_detail`。| `chat_agent.py`（新增预处理步骤）、`kos_extractor.py`（暴露轻量抽取接口，不写图谱） |
| **A-2** | **Java SSE 超时放宽 + 心跳保活** | ① 把 60s 改为 600s；② Python 端在 20s 没有产出时主动推 `event: ping` 心跳，前端忽略；③ Java SSE proxy 用 `Flux.mergeWith(Flux.interval(...).map(heartbeat))` 或直接放宽 readTimeout。| `ChatServiceImpl.java`、`chat_agent.py` |
| **A-3** | **会话自动生成标题** | 第一轮"user + ai_answer"完成后（`finally` 记忆保存后），异步调用一次轻量 LLM 生成 ≤15 字的标题并更新到会话表。列表刷新时显示标题。| `chat_agent.py`（新增 `_generate_title`）、`mysql_client.py`（新增 update_session_title）、`Chat.vue`（onDone 时刷新当前会话标题） |
| **A-4** | **工具调用写入记忆** | 在 `on_tool_end` 和工具结果整理后，追加 `ToolMessage` / `AIMessage(tool_calls)` 到记忆里；同时 MySQL `chat_history` 表新增一列 `meta JSON` 或在 content 里写入 `[TOOL_CALL]...[/TOOL_CALL]` 结构。LangChain 的历史才是完整 ReAct 轨迹，跨轮引用更准。| `memory_manager.py`、`mysql_client.py` / SQL 表、`chat_agent.py`（on_tool_start/on_tool_end 追加写入）|

### 方案 B：P1 推荐做（问答质量提升）

| 编号 | 优化项 | 内容要点 | 涉及文件 |
|---|---|---|---|
| **B-1** | **图谱检索增强：引入实体类型/别名/模糊匹配** | `search_entities` 除了 `name CONTAINS`，再加 `any label type = X` 过滤、别名字段（如新增 `aliases` 属性查询）、`toLower(name)` 容错、对 keyword 做"KOS 同义词扩展"查询（多个关键词 UNION）。| `agent_tools.py` 的 `search_entities` / `get_entity_detail` |
| **B-2** | **System Prompt 注入图谱元数据** | 调用 Agent 前，先拿 `list_entity_types` + `get_graph_stats` 的结果拼成"当前图谱包含 X 类实体：专家学者(300)、组织机构(200)…" 放进 System Prompt，Agent 选工具时不再瞎蒙类型名。注意只在会话首轮或换模型时查一次并缓存到 Redis。| `chat_agent.py`（新增 `_build_graph_meta_context`，结果缓存）、`memory_manager.py`（可选，存 graph_meta）|
| **B-3** | **回答带引用 / 来源卡片** | 工具调用完成后，把命中的实体 name/type/relation 记录下来；回答完成时推一个 `citations` 事件，前端在 AI 消息底部渲染"参考实体 1、2、3"卡片，点击跳图谱探索页。| `chat_agent.py`（工具调用阶段收集 hit 实体 → citations）、`Chat.vue`（新增 citations 渲染区 + 跳转 Explore 按钮）|
| **B-4** | **多轮指代消解** | 在 SYSTEM_PROMPT 中明确要求 Agent"如果用户使用代词，请先基于历史上下文确定指代实体，再调用工具"，并在 A-4 完成（tool_message 入记忆）后自动生效。 | `chat_agent.py` 优化 prompt |
| **B-5** | **历史消息滑动窗口 + 摘要裁剪** | `get_langchain_memory` 时只取最近 N 轮（N=10）。超过时用 LLM 把更早的摘要成一段 `SystemMessage(history_summary)`，保证 prompt 长度上限可控。| `memory_manager.py`（新增 summarize 方法）、`llm_client.py`（新增轻量摘要调用）|

### 方案 C：P2 稳定性

| 编号 | 优化项 | 内容要点 | 涉及文件 |
|---|---|---|---|
| **C-1** | **前端 SSE 自动重连（仅 thinking/answer 阶段做增量恢复）** | `fetch` 断了时，前端用 `Last-Event-ID` 或 `sessionId + sinceEventIdx` 拉一下"已完成的工具"和"已有回答片段"，继续渲染而不是让用户重发。| `Chat.vue`、`ChatController.java`（可选新增 resume 接口）、`chat_agent.py`（可选加恢复逻辑）|
| **C-2** | **Neo4j driver session 复用 + 查询超时** | `_Neo4jToolContext` 用 `context = driver.session(database=...)` 做成 `async` with 上下文，或 driver 配置 max_connection_pool_size。每个查询加 `session.run(...).consume()` 超时。| `agent_tools.py` |
| **C-3** | **厘清数据层职责：Java 也能做审计与查询**（可选） | 目前 Java 的 `ChatHistoryService / ChatHistoryMapper` 似乎和 Python 的 `mysql_client` 双写互不相干。若后续要做运营看板/管理员审计，必须统一。可做一次确认：到底谁是唯一真源，然后把冗余的一端停掉或做只读同步。| `ChatServiceImpl.java`、`ChatHistoryMapper.xml`、`mysql_client.py` 三者对齐 |

### 方案 D：P3 体验交互

| 编号 | 优化项 | 内容要点 | 涉及文件 |
|---|---|---|---|
| **D-1** | **停止按钮 / 中止流式** | 输入框右侧加"停止"图标，`AbortController` 中断 `fetch`；SSE 中止后：① Python 侧 `CancelledError` 捕获并写入半完成记忆；② 前端把消息标记为"已停止"，允许用户继续追问。| `Chat.vue`（新增 abortController，sendMessage 时挂载）、`chat_agent.py`（`except CancelledError` 正确写入已有回答到记忆）|
| **D-2** | **智能快捷问题（按所选图谱模型生成）** | 用户选完模型后，Java/Python 端拿 `get_graph_stats` 生成 4 条该模型上的示例问题（例如"有哪些专家学者？""哪个机构发文最多？""X 和 Y 有什么关系？"），替换硬编码的 quickQuestions。| `Chat.vue`（onModelChange 拉取 prompt）、新增接口或直接复用 `get_graph_stats` 前端生成 |
| **D-3** | **工具调用卡片 JSON 美化 + 折叠 + 语法高亮** | 把 `tool_call.input / output` 做 JSON.stringify(..., 2) + `highlight.js` 或纯 CSS 缩进；默认折叠 output，展开看原文。 | `Chat.vue` tool-call-card 样式改造 |
| **D-4** | **思考区一键折叠** | 思考标题栏加 `▽/▷` 折叠按钮；消息流底部渲染完后，新 token 追加自动折叠的话不强制滚到底部。| `Chat.vue` 样式 + 状态管理 |
| **D-5** | **Markdown 渲染 + 代码高亮 + 数学公式** | 用 `marked` + `highlight.js`（或 `@kangc/v-md-editor` 轻量版）渲染 AI 回答内容；支持复制块代码、复制整条消息；数学公式用 `katex`。| `Chat.vue` 消息渲染、`package.json`（确认/添加依赖，已有的话不需要）|

---

## 三、修改文件清单

### 第一阶段（P0 必做）预计涉及 6 个文件

1. `pybackend/api/chat_agent.py`
   - 新增 KOS/NER 问题预处理
   - 新增 SSE ping 心跳
   - 新增工具调用入记忆
   - 新增会话标题自动生成
2. `pybackend/core/kos_extractor.py`
   - 暴露 `extract_terms` + `extract_named_entities` 两个"只抽不写"函数（已有，需调用时确认不依赖 req.ontology）
3. `pybackend/core/memory_manager.py`
   - 支持 tool_call 消息持久化
4. `pybackend/utils/db/mysql_client.py` + `sql/chat_history.sql`
   - chat_history 表加 meta/json 列 / 或使用 content 前缀标注
   - 新增 `update_session_title(session_id, title, user_id)`
5. `src/main/java/com/yuan/seedboot/service/Impl/ChatServiceImpl.java`
   - timeout 60s → 600s，添加心跳透传（或干脆去掉中间层的 readTimeout 限制）
6. `frontend/src/views/Chat.vue`
   - 标题刷新、停止按钮、onDone 回调

### 第二阶段（P1 质量）预计再涉及 4 个文件

7. `pybackend/core/agent_tools.py`（B-1 检索增强）
8. `frontend/src/views/Chat.vue`（B-3 citations + D-1~D-5 交互）
9. `pybackend/core/memory_manager.py`（B-5 摘要裁剪）
10. `pybackend/core/llm_client.py`（摘要 / 标题生成轻量调用封装）

---

## 四、风险与注意事项

| 风险 | 说明 | 规避 |
|---|---|---|
| **LLM 成本增加** | 标题生成 + 历史摘要会多调用 1-2 次 LLM | 标题生成只用 1 轮；摘要裁剪只在 >10 轮触发，或用非流式 temperature=0 的便宜小模型 |
| **KOS 抽词噪声** | 把"中国""北京"这种停用词当术语塞给 Agent，反而干扰 | 在预处理函数中做过滤：`len(term) < 2` 丢弃；排除词表（"问题""什么""请""的"）；只取 TF-IDF 前 Top-3 + NER 命中结果注入，不要一股脑塞 |
| **记忆结构变更兼容性** | 老会话（历史里没有 tool_call）读回来时 memory_manager._to_langchain_messages 要兼容 | ToolMessage 识别不到就当普通 AI 消息，不影响历史读取 |
| **Java 超时改长**可能"挂住线程" | WebFlux Netty 是异步非阻塞，600s 不会挂线程；但要配置正确的 `response-timeout` 与 Netty `idleState` | 加 ping 心跳，中间代理（Nginx/Vite 等）不会因空闲而关连接 |
| **chat_history 表结构变更** | `ALTER TABLE` 要兼容线上已有数据 | meta 列允许为 NULL；title 列有默认值"新对话"；不要删老列 |

---

## 五、推荐的执行顺序

1. **先做 P0（A-1 ~ A-4）**：投入最小（约 1-2 天），直接解决"查不到实体"和"长对话断"两个最痛的点
2. **再做 P1 中的 B-2（System Prompt 注入图谱元数据）+ B-3（引用来源）**：对回答质量提升肉眼可见
3. **P2/P3 作为后续迭代**，按实际使用体验挑优先级

执行时建议先按 P0 落地并验证，确认效果后再推进 P1/P2/P3。

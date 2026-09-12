# KGraph 知识图谱管理系统

> 基于 Vue 3 + Spring Boot + FastAPI 的知识图谱构建、管理、训练和问答的一体式平台，支持通过 MinerU 解析 PDF/Word 文档构建语料并提供四种策略的文本切分（防止 LLM 上下文超限），提供结构化抽取、KOS 抽取、深度学习抽取、LLM 抽取四种知识抽取方式，集成 Neo4j 图数据库与 G6 可视化。

---

## 系统截图

### 首页 Dashboard

展示系统总览：项目/模型/实体/抽取任务统计、核心功能矩阵、最近抽取任务列表。
![系统首页](assets/images/系统首页.png)
<!-- TODO: 待补充截图 - 首页看板 -->
![首页看板](assets/%E9%A6%96%E9%A1%B5%E7%9C%8B%E6%9D%BF.png)

### 图谱探索

基于 AntV G6 的交互式图谱可视化，支持节点拖拽、缩放、双击展开邻居、单击查看属性。三栏布局：左侧控制面板、中间画布、右侧节点详情（点击节点时挤压中间图谱区域，关闭详情恢复原宽）。
![图谱探索](assets/images/图谱探索.png)

### 语料管理与文本分块

语料管理页面：列表展示（标题/来源/状态/创建时间），支持文本输入与文档上传（MinerU 解析），操作栏含「分块」按钮。
![语料管理](assets/%E8%AF%AD%E6%96%99%E7%AE%A1%E7%90%86.png)

文本分块配置对话框：双栏布局，左侧选择切分策略（定长滑窗/句子感知/递归分割/结构优先）并配置块大小/重叠/分隔符参数，右侧实时预览分块效果（块序号、原文偏移、内容）。
![语料分块](assets/%E8%AF%AD%E6%96%99%E5%88%86%E5%9D%97.png)

### 知识抽取（KOS 抽取）

KOS 抽取页面：左侧配置区（项目/模型选择、语料来源、11 项 KOS 参数）+ 右侧结果区（实体列表、关系列表、历史记录）。
![KOS抽取](assets/KOS%E6%8A%BD%E5%8F%96.png)


### 深度学习抽取 - 模型训练

模型训练页面：训练任务列表、训练配置表单、训练曲线监控（Loss 曲线 + P/R/F1 曲线分图展示）。
![深度学习抽取](assets/%E6%B7%B1%E5%BA%A6%E5%AD%A6%E4%B9%A0%E6%8A%BD%E5%8F%96.png)
![模型训练](assets/%E6%A8%A1%E5%9E%8B%E8%AE%AD%E7%BB%83.png)


### LLM抽取

LLM抽取页面：双 Tab（知识抽取 / 质量评估）。知识抽取含抽取配置（实体关系配置、抽取配置）与结果展示；质量评估支持选择历史抽取结果与语料进行内在指标 + LLM-as-Judge 评估。
![LLM抽取](assets/LLM%E6%8A%BD%E5%8F%96.png)
LLM 抽取质量评估：内在指标（孤立实体率/平均度/证据覆盖率/低置信率等）+ LLM-as-Judge 五大裁判指标（三元组忠实度/谓词合理性/双时态正确性/证据句有效性/实体边界正确性），支持 SSE 流式出分与进度条。
![质量评估](assets/%E8%B4%A8%E9%87%8F%E8%AF%84%E4%BC%B0.png)
![评估对比](assets/%E8%AF%84%E4%BC%B0%E5%AF%B9%E6%AF%94.png)

### 智能问答（流式输出）

对话式知识查询页面：极简界面布局，支持 LLM 思维链流式展示、工具调用卡片、正式回答逐字打字机效果。基于 LangGraph Agent + 图谱工具（搜索实体、获取详情、关系查询、图谱统计、按类型查询实体等）+ SSE 全链路流式推送。支持会话管理与右下角 LLM 模型选择（DeepSeek 系列，llm_model 表配置）。
![智能问答](assets/%E6%99%BA%E8%83%BD%E9%97%AE%E7%AD%94.png)

### 模型管理与调用监控

模型管理页面：模型列表（Ollama/OpenAI/Qwen/DeepSeek预设供应商），支持新增/编辑/删除，模型按用户配置隔离（未配置不可见不可用）。
模型调用监控：统计卡片（总调用次数/Token 总消耗/使用模型数）+ 每日调用次数与 Token 消耗双轴图 + 各模型调用占比饼图，支持近 7/14/30 天切换；下方每个模型一行展示调用次数折线图与 Token 消耗柱状图。
![模型管理](assets/%E6%A8%A1%E5%9E%8B%E7%AE%A1%E7%90%86.png)

## 项目简介

KGraph 是一个面向知识图谱构建、管理、训练和问答的一体式平台，覆盖从知识抽取、本体建模、图谱可视化到模型训练的完整链路。系统采用三层混合架构：

| 层级 | 技术栈 | 职责 |
|------|--------|------|
| 前端 | Vue 3 + Element Plus + Vite + TypeScript + marked（Markdown 渲染） | UI 交互、图可视化（G6）、图表展示（ECharts）、SSE 流式接收 + 打字机动效 |
| Java 主服务 | Spring Boot + MyBatis-Plus + MySQL + Neo4j + MinIO + WebFlux（`Flux<ServerSentEvent>` SSE 代理） | 业务编排、权限管理、结构化抽取、图谱 CRUD、MinerU 文档解析调度、流式事件透传 |
| Python 微服务 | FastAPI + OpenAI SDK + LangGraph（Agent 编排） + `StreamingResponse`（SSE） | LLM 抽取、KOS 抽取、深度学习抽取、模型训练、智能问答 Agent（流式工具调用） |
| **MCP Server** | **MCP Python SDK（`mcp>=2.2`）** | **知识抽取 + 质量评估 Tool，供 Trae/Claude Desktop 等 LLM 客户端调用，支持 stdio/SSE/streamable-http 三种传输层** |
| 外部服务 | MinerU v3.4.5（文档解析） | PDF/Word → Markdown 转换，独立进程运行 |

### 核心功能

- **项目管理**：多项目隔离，每个项目可创建多个图谱模型
- **本体建模**：自定义实体类型、关系类型、属性，支持多模型 schema 隔离
- **语料管理**（含 MinerU 文档解析 + 文本切分）：
  - 文本输入：手动输入文本内容直接入库
  - 文档上传：PDF/Word 上传到 MinIO，`@Async` 异步调用 MinerU 解析为 Markdown 入库，前端轮询感知解析状态
  - 支持解析失败后重新触发解析
  - **文本切分**：四种策略（定长滑窗 / 句子感知合并 / 递归字符分割 / 结构优先切分），支持预览与执行；切分结果存入 `corpus_chunk` 表，保留原文偏移（`startOffset`/`endOffset`）确保可溯源；编辑语料内容时自动清空失效分块
- **知识抽取**（四种方式）：
  - 结构化抽取：Excel/CSV 字段映射
  - KOS 抽取：领域词表 + TF-IDF 统计 + 三层结构（范畴→概念→术语）
  - 深度学习抽取：词典匹配 + CRF 约束 + 规则细分（22 种实体类型）
  - LLM 抽取：两阶段流水线（Semantica 风格）—— 阶段1 抽节点（实体/事件/指代消解/时间锚点）→ 阶段2 以实体表为硬约束抽关系（附证据句），支持双时态关系（CURRENT/EXPIRED/NEGATED）
- **图谱探索**：G6 交互式可视化，三栏布局，点击节点挤压中间图谱区域展示详情
- **实体关系管理**：CRUD 操作，分页展示
- **模型训练**：训练任务管理、曲线监控、模型效果评估
- **数据标注**：标注任务管理，支持 BIO 标签体系
- **智能问答（LangGraph Agent · SSE 流式）**：基于 LangGraph v2 事件体系编排 Agent，内置 9 个图谱工具（`search_entities`、`get_entity_detail`、`get_entity_relations`、`get_graph_stats`、`list_entity_types`、`get_entities_by_type`、`get_entities_by_name`、`get_causal_chain`、`get_entity_neighborhood`）。通过 Python→Java→前端 全链路 SSE 增量推送，配合前端打字机缓冲队列实现：① 思考过程流式展示 ② 工具调用执行状态实时卡片 ③ 正式回答逐字 Markdown 渲染输出
- **智能问答 · 模型选择与会话管理**：
  - 右下角模型选择器（Trae Work 风格）：模型清单由 `llm_model` 表维护（DeepSeek 系列，可扩展千问/GLM），`GET /api/chat/llm-models` 动态拉取；上次选择存 localStorage，首次使用默认 deepseek-chat
  - 图谱模型（顶部下拉）选择持久化 localStorage，刷新/切换菜单后自动恢复
  - 会话管理：新建/切换/删除会话，历史消息 MySQL 持久化 + Redis 缓存（次日 0 点过期）
  - 会话标题：首轮问答完成后异步调用 LLM 生成 ≤20 字标题（不截断），先发 `done` 恢复输入框、再补发 `title` 事件实时替换会话项标题；短路优化 + 规则兜底降级
- **LLM 抽取质量评估**：抽取页"质量评估"Tab，支持从抽取历史选择结果与语料一键评估；内在指标（孤立实体率/平均度/证据覆盖率/低置信率等）+ LLM-as-Judge 抽样评估（G-Eval 风格，三元组忠实度/谓词合理性/双时态正确性/证据句有效性/实体边界正确性）
- **MCP Server（LLM 客户端接入）**：将知识抽取和质量评估能力包装为 MCP Tool，支持 stdio/SSE/streamable-http 三种传输层。**薄包装零漂移**——直接 `import core.extraction_service` / `core.evaluation_core`，与主服务 HTTP 端点共用同一份实现，口径 100% 一致。运行期唯一外部依赖为 LLM API，可部署为 Docker 服务供远程 Agent 集群调用

---

## 技术栈

### 前端

- Vue 3（Composition API）
- Element Plus
- Vite + TypeScript
- AntV G6（图可视化）
- ECharts（训练曲线/指标图表）
- Pinia（状态管理）
- Axios（HTTP 请求）
- marked（Markdown 渲染，智能问答回答展示）

### Java 主服务

- Spring Boot 3
- MyBatis-Plus
- MySQL 8
- Neo4j 5
- MinIO（对象存储）
- Spring WebFlux（`Flux<ServerSentEvent>` SSE 流式代理）
- Knife4j（API 文档）

### Python 微服务

- FastAPI
- OpenAI Python SDK
- Neo4j Python Driver
- LangChain / LangGraph（智能问答 Agent 编排 + 工具调用生命周期事件）
- langchain-openai（ChatOpenAI 流式）
- **MCP Python SDK（`mcp>=2.2`，MCP Server 传输层与 Tool 注册）**

---

## 项目结构

```
KGraph/
├── frontend/                    # 前端
│   ├── src/
│   │   ├── api/                 # API 封装
│   │   ├── components/          # 通用组件
│   │   │   ├── dl/              # 深度学习模块组件
│   │   │   └── ExtractionLayout.vue
│   │   ├── layouts/             # 布局组件
│   │   ├── router/              # 路由配置
│   │   ├── stores/              # Pinia 状态管理
│   │   └── views/               # 页面
│   │       ├── platform/        # 平台管理
│   │       ├── Home.vue         # 首页
│   │       ├── Explore.vue      # 图谱探索
│   │       ├── Chat.vue         # ⭐ 智能问答（流式）
│   │       ├── Extraction.vue   # LLM 抽取
│   │       ├── KosExtraction.vue# KOS 抽取
│   │       ├── DlExtraction.vue # 深度学习抽取
│   │       ├── StructureExtraction.vue
│   │       ├── Corpus.vue       # 语料管理
│   │       ├── Model.vue        # 模型管理
│   │       └── Project.vue      # 项目管理
│   └── package.json
│
├── src/main/java/.../seedboot/  # Java 主服务
│   ├── annotation/              # 权限注解
│   ├── aop/                     # AOP 切面
│   ├── config/                  # 配置类（含 PythonServiceClient、CustomChatMemoryRepository）
│   ├── controller/              # 控制器（含 ChatController 流式路由）
│   ├── mapper/                  # MyBatis Mapper
│   ├── model/                   # 数据模型
│   │   ├── entity/              # 实体类
│   │   ├── request/             # 请求对象
│   │   └── vo/                  # 视图对象
│   ├── service/                 # 业务逻辑（ChatService 返回 Flux<ServerSentEvent>）
│   │   └── Impl/                # 实现类
│   └── SeedBootApplication.java
│
├── pybackend/                   # Python 微服务
│   ├── api/                     # FastAPI 路由
│   │   ├── chat_agent.py        # ⭐ 智能问答 SSE Agent 流式接口
│   │   ├── extraction.py        # LLM 抽取 + 质量评估
│   │   ├── evaluation.py        # 评估端点（内在指标 + LLM-as-Judge）
│   │   └── splitter.py          # ⭐ 文本切分接口（4 策略）
│   ├── core/                    # 核心算法
│   │   ├── agent_tools.py       # ⭐ Agent 图谱工具集（8个工具）
│   │   ├── llm_client.py        # LLM 调用封装
│   │   ├── prompt_builder.py    # Prompt 构造
│   │   ├── kos_extractor.py     # KOS 抽取
│   │   ├── dl_extractor.py      # 深度学习抽取
│   │   ├── trainer.py           # 模型训练
│   │   ├── graph_writer.py      # Neo4j 写入
│   │   ├── extraction_validator.py  # 抽取校验 + 后处理补边
│   │   └── evaluation_core.py   # ⭐ 评估核心（内在指标 + G-Eval 裁判，无 FastAPI 依赖，HTTP/MCP 共用）
│   ├── splitter/                # ⭐ 文本切分策略包
│   │   ├── base.py              # Chunk 数据类 + SplitStrategy 抽象基类
│   │   ├── fixed.py             # 定长滑窗分块
│   │   ├── sentence.py          # 句子感知合并分块
│   │   ├── recursive.py         # 递归字符分割
│   │   ├── structure.py         # 结构优先切分（Markdown/中文标题）
│   │   └── __init__.py          # 策略注册表 STRATEGY_REGISTRY
│   ├── models/                  # Pydantic 模型
│   ├── text_processor/          # 文本处理工具
│   ├── config.example.json      # 配置模板
│   ├── main.py                  # FastAPI 入口
│   ├── mcp_server.py            # ⭐ MCP Server（kg_extract_full + kg_evaluate 两个 Tool）
│   └── requirements.txt
│
├── sql/                         # 数据库脚本
│   ├── kgraph.sql               # 主业务表
│   ├── graph.sql                # 图谱相关表
│   ├── user.sql                 # 用户表
│   ├── chat_history.sql         # 对话历史表
│   ├── chat_session.sql         # 会话元数据表（AI 生成标题）
│   ├── llm_model.sql            # LLM 模型配置表（智能问答模型选择）
│   └── log.sql                  # 日志表
│
└── pom.xml                      # Maven 配置
```

---

## 快速开始

### 环境要求

- JDK 17+
- Node.js 18+
- Python 3.10+
- MySQL 8+
- Neo4j 5+
- Redis 7+
- MinIO（语料文件存储）
- MinerU v3.4.5（PDF/Word 文档解析，独立进程）

### 1. 克隆项目

```bash
git clone https://github.com/reponsee/KGraph.git
cd KGraph
```

### 2. 初始化数据库

```bash
# 创建 MySQL 数据库
mysql -u root -p -e "CREATE DATABASE seedboot DEFAULT CHARACTER SET utf8mb4;"

# 导入表结构
mysql -u root -p seedboot < sql/kgraph.sql
mysql -u root -p seedboot < sql/user.sql
mysql -u root -p seedboot < sql/chat_history.sql
mysql -u root -p seedboot < sql/llm_model.sql   # 智能问答模型选择（导入后替换 api_key）
mysql -u root -p seedboot < sql/log.sql

# Neo4j 约束/索引（可选，提升查询性能并保证实体唯一性）
# 将 sql/graph.sql 内容在 Neo4j Browser 中执行
```

### 3. 启动 MinerU 文档解析服务

MinerU 是独立的 Python 进程，提供 `/file_parse` HTTP 接口把 PDF/Word 转换为 Markdown。

```bash
# 安装 MinerU（详细步骤见官方文档）
pip install -U magic-pdf[full]

# 启动 API 服务（默认端口 8000）
mineru-api --port 8000
```

服务启动在 `http://localhost:8000`，健康检查可访问 `http://localhost:8000/docs`。

### 4. 配置 Java 主服务

```bash
# 复制配置模板
cp src/main/resources/application-local.example.yml src/main/resources/application-local.yml

# 编辑配置，填入你的数据库、Neo4j、MinIO、MinerU、LLM API Key
vim src/main/resources/application-local.yml
```

关键配置项：

```yaml
minio:
  endpoint: http://localhost:9000
  access-key: your-access-key
  secret-key: your-secret-key
  bucket: kgraph

# MinerU 文档解析服务
mineru:
  base-url: http://localhost:8000
```

### 5. 启动 Java 主服务

```bash
./mvnw spring-boot:run
```

服务启动在 `http://localhost:8888/api`

### 6. 配置 Python 微服务

```bash
cd pybackend

# 复制配置模板
cp config.example.json config.json

# 编辑配置，填入你的 LLM API Key 和 Neo4j 密码
vim config.json

# 安装依赖
pip install -r requirements.txt
```

### 7. 启动 Python 微服务

```bash
cd pybackend
python main.py
```

服务启动在 `http://localhost:8001`

### 8. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端启动在 `http://localhost:5173`

### 9. 启动 MCP Server（可选，供 LLM 客户端调用）

MCP Server 是独立进程，**不需要启动 Java 主服务或 Python 微服务**，运行期只依赖 LLM API。

```bash
cd pybackend

# 方式一：stdio（推荐 Trae/Claude Desktop 本地接入，客户端自动拉起子进程）
python mcp_server.py --transport stdio

# 方式二：streamable-http（远程 Agent 集群 / Docker 部署）
python mcp_server.py --transport streamable-http --host 0.0.0.0 --port 8003

# 方式三：SSE（兼容旧客户端）
python mcp_server.py --transport sse --host 0.0.0.0 --port 8003
```

#### Trae 配置示例（stdio 模式）

Trae → 设置 → MCP → 手动添加（原始 JSON）：

```json
{
  "mcpServers": {
    "kgraph": {
      "command": "/path/to/python3",
      "args": ["/path/to/KGraph/pybackend/mcp_server.py", "--transport", "stdio"],
      "cwd": "/path/to/KGraph/pybackend"
    }
  }
}
```

#### Docker 部署（生产环境）

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pybackend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir "mcp>=2.2,<3"
COPY pybackend/ .
EXPOSE 8003
CMD ["python", "mcp_server.py", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8003"]
```

```bash
docker build -t kgraph-mcp .
docker run -d -p 8003:8003 -e DEEPSEEK_API_KEY=sk-xxx kgraph-mcp
```

#### 提供的 Tool

| Tool | 说明 |
|------|------|
| `kg_extract_full` | 两阶段 LLM 抽取 + W1-W5 质量管道，输出实体/关系/时间锚点 |
| `kg_evaluate` | 内在指标 + G-Eval 五维 LLM-as-Judge 裁判，对抽取结果打分 |

---

## 配置说明

> **重要**：以下文件包含敏感信息，已被 `.gitignore` 排除，不会提交到 GitHub：

| 文件 | 说明 | 模板 |
|------|------|------|
| `src/main/resources/application-local.yml` | Java 主服务配置（数据库、Neo4j、MinIO、API Key） | `application-local.example.yml` |
| `pybackend/config.json` | Python 微服务配置（LLM API Key、Neo4j） | `config.example.json` |
| `pybackend/prompt.json` | LLM Prompt 模板 | - |

请复制对应的 `.example` 模板文件并填入你的配置。

---

## API 文档

Java 主服务启动后，访问 Knife4j API 文档：

```
http://localhost:8888/api/doc.html
```

Python 微服务启动后，访问 FastAPI 自动文档：

```
http://localhost:8001/docs
```

---

## 关键设计

### Neo4j 多模型隔离

每个图谱模型的实体和关系通过 `modelId` 字段隔离，Cypher 查询时通过 `WHERE n.modelId = $modelId` 过滤。约束 `(name, type, modelId)` 三元组唯一，避免不同模型间同名实体冲突。

### 关系类型存储

Neo4j 关系使用固定的 relationship type（`RELATED` / `RELATION`），业务关系名存储在 `relationType` 属性中，避免属性覆盖问题。查询时优先读取 `relationType`，旧数据兼容 `type` 字段。

### MinerU 文档解析集成

- **MinIO SDK 直连下载**：Java 端通过 `minioClient.getObject()` 下载文件再交给 MinerU，绕开预签名 URL 的鉴权问题
- **异步 + 轮询模式**：`@Async` 注解保证上传接口即时返回，前端轮询 corpus 列表感知解析状态
- **响应格式兼容层**：`extractMarkdown()` 兼容 MinerU v3.4.5（`results.<filename>.md_content`）、旧版 `md` 字段、JSON 数组、纯文本四种返回结构
- **失败重试**：失败记录（status=2）可通过重新解析接口再次触发 MinerU 调用

### 抽取任务记录

所有抽取任务记录到 `extraction_task` 表，包含抽取类型、模型 ID、耗时、状态等信息，支持历史查询。

### 前后端数据格式兼容

前端封装 `extractRecords` 函数，兼容后端返回的 `records` / `list` / 数组等多种格式。

---

## License

MIT

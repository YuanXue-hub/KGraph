# KGraph MCP Server 技术方案

> 让 KGraph 的**知识抽取 + 质量评估**两个能力被任何支持 MCP 的 LLM 客户端直接调用

## 一、背景与目标

KGraph 目前通过 Java 后端 + Python 微服务（端口 8001）提供 HTTP API，但消费方必须自己组装 HTTP 调用、处理 JSON 反序列化、理解抽取参数含义。MCP（Model Context Protocol）把这些包装成 **tool** 原语，让 LLM 客户端（Trae、Claude Desktop、Cursor、AutoGPT…）可以直接发现能力并调用。

**目标**：一行命令启动 KGraph MCP Server，任何 MCP 客户端即可自动获取以下两个能力：

| 能力 | 形式 | 示例调用 |
|---|---|---|
| 两阶段知识抽取（实体/关系/时间锚点 + 质量管道） | tool | "从这段俄乌战争文本里抽知识图谱" |
| G-Eval 风格质量评估（内在指标 + LLM-as-Judge 五维裁判） | tool | "评估一下刚才那次抽取的质量" |

两个 Tool 天然衔接：`kg_extract_full` 返回的 entities/relations 数组可直接作为 `kg_evaluate` 的入参，Agent 无需任何格式转换。

## 二、架构

```
┌─────────────────────────────────────────────────────────┐
│                  MCP Client 层                          │
│  Trae / Claude Desktop / Cursor / AutoGPT / LangGraph   │
└────────────────────────┬────────────────────────────────┘
                         │ MCP Protocol (stdio / SSE / streamable-http)
                         ▼
┌─────────────────────────────────────────────────────────┐
│              mcp_server.py（2 个 Tool）                  │
│  ┌─ TOOLS ─────────────────────────────────────────┐    │
│  │  kg_extract_full  两阶段 LLM 抽取 + W1-W5 管道   │    │
│  │  kg_evaluate       内在指标 + 五维裁判           │    │
│  └─────────────────────────────────────────────────┘    │
└────────────────────────┬────────────────────────────────┘
                         │ 直接 import 复用（无 HTTP 跳变）
                         ▼
┌─────────────────────────────────────────────────────────┐
│          pybackend/core/（已存在，零改动）                │
│  extraction_service.py   extract_entities / extract_rels │
│  extraction_validator.py run_quality_pipeline            │
│  extraction_schema.py    Pydantic payload 定义            │
│  llm_client.py           LLM 调用（temp=0 硬编码）        │
│  prompt_builder.py       两阶段 Prompt 构造               │
│  evaluation_core.py      评估核心（本次从 api/ 抽出）      │
└────────────────────────┬────────────────────────────────┘
                         ▼
                  ┌──────────────┐
                  │ DeepSeek API │   （唯一运行期外部依赖）
                  └──────────────┘
```

### 关键设计决策

1. **只提供抽取 + 评估两个 Tool**：不做图谱查询（Cypher）、不做语料/模型元数据、不做图谱统计——这些依赖 Neo4j/MySQL，剥离后 MCP Server 只依赖 DeepSeek API，可部署在任意有外网访问的机器上。
2. **MCP Server 直接 import core 模块，不调 HTTP**：主服务 8001 和 MCP Server 共享同一套 `extraction_service.py` / `evaluation_core.py`，没有中间网络跳变。
3. **评估核心下沉到 `core/evaluation_core.py`**：原 `api/evaluation.py` 的裁判逻辑与 FastAPI 耦合（模块级 `APIRouter()` 在当前 fastapi/starlette 版本下 import 即崩，无法被 MCP 复用）。本次把 criteria 词表、内在指标计算、G-Eval 裁判、抽样、证据切片抽成无 FastAPI 依赖的 core 模块，HTTP 端点与 MCP Tool 共用同一套实现，**口径零漂移**。
4. **LLM Client 懒加载**：首次调用时才创建，避免启动时 LLM API Key 失效导致 MCP Server 启动失败。
5. **评估不写 request_log 用量表**：MCP 是独立进程，不向主服务 MySQL 埋点；裁判模型选择用模型名（`judge_model_name`）而非主服务的 `llmModelId`（数据库 id），彻底去掉 MySQL 依赖。

## 三、实现细节

### 3.1 文件清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `pybackend/mcp_server.py` | **重构** | MCP Server，只含 kg_extract_full + kg_evaluate |
| `pybackend/core/evaluation_core.py` | **新增** | 评估核心（从 api/evaluation.py 抽出，无 FastAPI 依赖） |
| `pybackend/api/evaluation.py` | **瘦身** | 只保留 HTTP 层（请求模型 + 事件 generator + 两个端点 + 埋点），逻辑改从 core 导入，行为不变 |

### 3.2 依赖

```
mcp>=2.2,<3       # MCP SDK（MCPServer + stdio/SSE/streamable-http 传输）
```

不再依赖 `neo4j` / `pymysql`（查询/元数据/埋点工具已随功能一并移除）。

### 3.3 Tool 一览（共 2 个）

#### kg_extract_full —— 知识抽取

| 入参 | 类型 | 说明 |
|---|---|---|
| text | str | 待抽取原文（建议 ≤ 8000 字，超过先分片） |
| model_name? | str | 覆盖默认模型（如 "deepseek-v4-pro" / "deepseek-v4-flash"） |
| ontology? | str | JSON 字符串，自定义实体/关系类型约束（同 Java buildOntology 格式），空则默认词表 |
| skip_pipeline? | bool | True = 纯 LLM 原生输出（对比实验口径）；默认 False = 走 W1-W5 正式链路 |

返回：`entities`（name/mention/type/span）+ `relations`（head/relation/tail/vt_from/vt_to/confidence/evidenceSpans）+ `timeAnchors` + `qualityReport`。

#### kg_evaluate —— 质量评估

| 入参 | 类型 | 说明 |
|---|---|---|
| text | str | 被抽取的原文（必须与抽取时同一段） |
| entities | str | 实体列表 JSON（kg_extract_full 返回的 entities 字段） |
| relations | str | 关系列表 JSON（kg_extract_full 返回的 relations 字段） |
| sample_size? | int | 每指标抽样条数；正数=随机抽样，0/负数=全量（默认 30） |
| judge_model_name? | str | 裁判模型名覆盖（默认用服务配置模型） |
| metrics? | str | 逗号分隔指标 key，留空=全部。可选：tripleFaithfulness / predicateReasonableness / bitemporalCorrectness / evidenceValidity / entityCorrectness |

返回（与主服务 `/api/evaluate` 同结构）：`intrinsic`（实体数/关系数/孤立实体率/平均度/证据覆盖率/低置信率，0 次 LLM）+ `llmJudge`（每指标 score 0-1 + reason + 逐条 verdict）+ `overall`（综合得分）+ 统计字段。

**与主服务 /api/evaluate 的差异**（均为去依赖简化）：
- 裁判模型选择：模型名（`judge_model_name`）替代数据库 id（`llmModelId`）；
- 不写 request_log 用量表（MCP 独立进程，用量由调用方客户端自行记录）。

### 3.4 传输层

```bash
# 方式1：stdio（本地 CLI，IDE 场景）
# Agent 启动 MCP Server 子进程，用 JSON-RPC 走 stdin/stdout
python mcp_server.py --transport stdio

# 方式2：streamable-http（远端服务，Agent 集群场景）
# 暴露 HTTP endpoint，支持多客户端并发
python mcp_server.py --transport streamable-http --host 0.0.0.0 --port 8003

# 方式3：sse（传统 HTTP + SSE，兼容旧客户端）
python mcp_server.py --transport sse --port 8003
```

## 四、客户端接入示例

### 4.1 Claude Desktop（stdio）

在 `claude_desktop_config.json` 中加：

```json
{
  "mcpServers": {
    "kgraph": {
      "command": "/Users/Yuan/xy_workspace/1.dev_env/conda_envs/WarSee/bin/python3",
      "args": [
        "/Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend/mcp_server.py",
        "--transport", "stdio"
      ],
      "cwd": "/Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend",
      "env": {
        "PYTHONPATH": "/Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend"
      }
    }
  }
}
```

### 4.2 Trae（MCP 配置界面）

添加 MCP Server：
- Name: `kgraph`
- Command: `/Users/Yuan/xy_workspace/1.dev_env/conda_envs/WarSee/bin/python3`
- Args: `["/Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend/mcp_server.py", "--transport", "stdio"]`
- Working Directory: `/Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend`

### 4.3 LangGraph（streamable-http）

```python
from langchain_mcp_adapters.client import MultiMCPClient

async with MultiMCPClient({
    "kgraph": "http://localhost:8003/mcp",
}) as client:
    tools = client.get_tools()
    # 直接调用 kg_extract_full / kg_evaluate
```

## 五、验证

### 5.1 导入 + 工具注册

```bash
cd pybackend
python -c "import mcp_server"          # 预期无报错
python -c "
import asyncio, mcp_server
tools = asyncio.get_event_loop().run_until_complete(mcp_server.kgraph._tool_manager.list_tools())
print([t.name for t in tools])         # 预期 ['kg_extract_full', 'kg_evaluate']
"
```

### 5.2 端到端冒烟（抽取 → 评估串联，2026-09-12 实测通过）

```bash
python -c "
import json
import mcp_server
text = '2024年6月，弗拉基米尔·普京在莫斯科与白俄罗斯总统卢卡申科会晤……'
ext = json.loads(mcp_server.kg_extract_full(text=text, skip_pipeline=True))
ev = json.loads(mcp_server.kg_evaluate(
    text=text,
    entities=json.dumps(ext['entities'], ensure_ascii=False),
    relations=json.dumps(ext['relations'], ensure_ascii=False),
    sample_size=2, metrics='tripleFaithfulness,entityCorrectness',
))
print(ev['intrinsic']['entityCount'], ev['overall'])
"
```

实测结果：抽取 48.8s（13 entities / 14 relations），评估 10.6s（tripleFaithfulness=1.0、entityCorrectness=1.0，overall=1.0，3180 tokens）。

### 5.3 本地启动（HTTP 版）

```bash
python mcp_server.py --transport streamable-http --port 8003 &
mcp inspect http://localhost:8003/mcp
```

## 六、与现有主服务的关系

```
                    ┌─────────────────┐
                    │  Java 后端      │
                    │  (端口 8080)    │
                    └────────┬────────┘
                             │ HTTP POST
                    ┌────────▼────────┐
                    │  Python 主服务   │
                    │  (端口 8001)    │
                    │  Neo4j / MySQL  │
                    └────────┬────────┘
                             │ import
              ┌──────────────┼──────────────┐
              ▼                             ▼
     mcp_server.py                 core/ 抽取+评估模块
     (独立进程，只连                (两处共享，
      DeepSeek API)                 零漂移)
```

**零冲突**：MCP Server 不启动 FastAPI、不连 Neo4j/MySQL、不写任何库。主服务和 MCP Server 各自独立启动，共享 Python 包目录但不共享进程。MCP 启动硬依赖只有 `config.json` + `mcp` SDK；DeepSeek API 为首次调用时才触发的运行期依赖。

## 七、后续可扩展方向

| 方向 | 价值 | 工作量 |
|---|---|---|
| 因果边抽取 Tool | Agent 可直接调用 `kg_extract_causal`（目前因果边走图上离线推理，可封装成独立 Tool） | 中 |
| 向量检索 Tool | 对实体 canonicalName / 事件描述做 embedding 相似检索 | 中（需引入 sentence-transformers） |
| 图谱查询 Tool | 若 Agent 需要查 Neo4j，可重新引入只读 Cypher 查询（会恢复 Neo4j 依赖，按需开启） | 低 |
| 分片抽取 Tool | 传入长文本自动分片 + 结果聚合（Java 端分片逻辑已实现，Python 可复制） | 低 |

> 评估 Tool 已于本次完成（原列于扩展方向，通过 `core/evaluation_core.py` 下沉实现）。

## 八、风险与约束

| 风险 | 应对 |
|---|---|
| LLM 调用耗时（抽取两阶段 ≈ 50s / 百字级文本；全量评估最多 5 次裁判调用） | 单次 Tool 调用同步返回，Agent 需耐心等待；评估可用 sample_size 抽样 + metrics 子集控制 |
| v4-pro 推理模型非确定性 | prompt 硬编码 temp=0；建议同一语料跑多次取并集 |
| DeepSeek API 不可用 / Key 失效 | 懒加载 + try/except 返回错误 JSON，MCP Server 本身不崩 |
| 长文本超出 LLM 上下文窗口 | 提示 Agent 分片；后续可封装分片 Tool |
| 评估与主服务口径漂移 | 两处 import 同一个 `core/evaluation_core.py`，结构性消除 |

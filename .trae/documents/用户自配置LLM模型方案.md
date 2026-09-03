# 用户自配置 LLM 模型方案（CherryStudio 风格）

> 结论：**完全可实现**。现有 `llm_model` 表结构天然支持，用户体系（Session 登录 + 权限拦截）完备，动态 LLMClient 构造已在抽取/评估链路验证通过。表结构几乎零改动，主要工作是 CRUD 接口 + 管理页面。

## 一、现状分析

| 项              | 现状                                                                                                                             | 评估               |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------ | ---------------- |
| 表结构            | `llm_model` 已含 `provider/model_name/display_name/base_url/api_key/is_reasoner/temperature/enabled/sort_order/userId/isDeleted` | ✅ 零改动即可支撑        |
| userId 字段      | 已预留（BIGINT NULL），当前全部为 NULL（全局共享）                                                                                              | ✅ 语义即"NULL=系统预设" |
| 用户体系           | user 表 + Session 登录态（`UserService.getLoginUser`）+ `AuthInterceptor` + 前端路由守卫                                                   | ✅ 多用户基础齐全        |
| 模型查询           | `get_llm_models()` 仅过滤 `isDeleted=0 AND enabled=1`，无 userId 隔离                                                                 | ⚠️ 需改造           |
| 调用链            | 前端 → Java `ChatController`（WebClient 纯代理）→ Python `/api/chat/llm-models` → MySQL                                               | ✅ 改造点集中          |
| 动态构造 LLMClient | 抽取（extraction.py）/ 评估（evaluation.py）已按模型配置动态构造                                                                                 | ✅ 模式可复用          |

## 二、设计决策（已确认）

1. **可见性**：`自己的 + 系统预设` — 每个用户看到 `userId IS NULL`（管理员维护的公共模型）∪ `userId=自己` 的模型。现有 3 个全局模型无缝保留为系统预设。
2. **结构层级**：**单层模型列表** — 不引入供应商表，每条模型记录自带 provider 名称 + base\_url + api\_key（与当前表结构一致，改动最小）。

## 三、改动方案

### 3.1 表结构（`sql/llm_model.sql`）

**零新增字段**。仅明确约定：

- `userId IS NULL` → 系统预设（仅管理员可增删改）

- `userId = <uid>` → 该用户的个人模型

- 删除一律逻辑删除（`isDeleted=1`），已有字段

可选补充索引：`ALTER TABLE llm_model ADD INDEX idx_user (userId, isDeleted);`（数据量小，非必需）

### 3.2 Python 端（pybackend）

**mysql\_client.py** 新增/改造：

```python
def get_llm_models(self, user_id: int | None = None, enabled_only=True):
    # WHERE isDeleted=0 AND (userId IS NULL OR userId=%s)
    # ORDER BY sort_order, id

def create_llm_model(self, data: dict, user_id: int) -> int: ...
def update_llm_model(self, model_id: int, data: dict, user_id: int, is_admin: bool): ...
    # 非管理员只能改 userId=自己的行
def delete_llm_model(self, model_id: int, user_id: int, is_admin: bool): ...
    # 逻辑删除 isDeleted=1
```

**chat\_agent.py** 新增路由（`/api/chat/llm-models` 系）：

| 路由                               | 方法     | 说明                                                    |
| -------------------------------- | ------ | ----------------------------------------------------- |
| `/api/chat/llm-models`           | GET    | 加 `userId` 参数过滤（NULL ∪ 自己）                            |
| `/api/chat/llm-models`           | POST   | 新增个人模型（userId=传入值）                                    |
| `/api/chat/llm-models/{id}`      | PUT    | 更新（仅自己的；系统预设仅 admin）                                  |
| `/api/chat/llm-models/{id}`      | DELETE | 逻辑删除（同上权限）                                            |
| `/api/chat/llm-models/{id}/test` | POST   | 测试连接：用该配置构造 LLMClient 发一条极简消息（max\_tokens=8），返回连通性+延迟 |

**安全约定**：Python 为内网服务，`userId/is_admin` 由 Java 鉴权后传入（请求头或 body），Python 不做二次鉴权。

**api\_key 打码**：列表/详情接口返回 `apiKey: "sk-****abcd"` 形式，不回传完整 key；更新时 apiKey 传空表示"不修改"。

### 3.3 Java 端（纯透传 + 鉴权）

**ChatController.java** 新增端点，全部加 `@AuthCheck`：

- `GET /v1/chat/llm-models` — 从 Session 取当前用户，userId 拼到转发参数

- `POST/PUT/DELETE /v1/chat/llm-models/**` — 取当前用户 id + 角色，透传 Python

- PythonServiceClient 增加对应 doPut/doDelete/doPost 转发方法

### 3.4 前端

**新页面** **`/llm-model`（LLM 模型管理）**，挂到侧边菜单：

- **列表**：显示名 / 供应商 / model\_name / base\_url / 启用开关 / 来源标签（`系统预设` / `个人`）/ 操作（测试连接、编辑、删除 — 系统预设仅管理员可见操作）

- **新增/编辑弹窗**：displayName、provider、modelName、baseUrl、apiKey（编辑时不回显，留空=不修改）、temperature、isReasoner、sortOrder

- **测试连接**：按钮 → 调 test 接口 → 成功显示延迟，失败显示错误信息（key 无效/URL 不通）

**联动收益（无需额外改动）**：智能问答模型选择、知识抽取"抽取模型"、评估"裁判模型"均走 `GET /api/chat/llm-models`，个人模型添加后自动出现在所有下拉框，localStorage 持久化的模型 id 继续有效。

### 3.5 抽取/评估链路适配

extraction.py / evaluation.py 中按 `llmModelId` 动态构造 LLMClient 的逻辑不变（`get_llm_model_by_id` 已过滤 isDeleted=0）。可选增强：校验该模型属于当前用户或为系统预设，防止越权引用他人模型。

## 四、工作量评估

| 模块     | 内容                                | 预估      |
| ------ | --------------------------------- | ------- |
| Python | mysql\_client CRUD + 5 个路由 + 测试连接 | \~0.5 天 |
| Java   | Controller 透传 + Session 取用户       | \~0.5 天 |
| 前端     | 管理页面（列表+弹窗+测试）+ 菜单路由              | \~1 天   |
| 联调验证   | 三端联调 + 权限场景测试                     | \~0.5 天 |

## 五、验证步骤

1. admin 登录 → 模型管理页可见 3 个系统预设（可编辑），新增一个个人模型 → 智能问答/抽取/评估下拉中出现
2. user 登录 → 看见 3 个系统预设（只读）+ 自己的模型；新增/编辑/删除自己的模型正常，操作系统预设被拒（403）
3. 测试连接：填错误 key → 明确报错；正确配置 → 显示延迟
4. apiKey 安全：接口响应中不出现完整 key；编辑留空不覆盖原 key
5. 逻辑删除后各下拉不再出现该模型；重新添加同名模型不冲突

## 六、后续可选扩展（本期不做）

- 供应商预设模板（一键填充 DeepSeek/OpenAI/硅基流动的 base\_url）

- 模型用量统计（token 消耗按 userId 汇总）

- api\_key 加密存储（AES，密钥走配置）


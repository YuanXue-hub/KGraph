# KGraph Docker 部署指南

> 面向 KGraph（Vue 3 前端 + Spring Boot Java 主服务 + FastAPI Python 微服务）的容器化部署方案。
> **一键启动只部署应用层**（`frontend` / `java` / `pybackend`）；MySQL、Neo4j、Redis、MinIO 等**有状态基础服务由外部提供**（已有实例、宿主机或单独容器），不在默认启动范围内。
> 本文档含全部可直接复制的 `Dockerfile`、`docker-compose.yml`、`nginx.conf` 与配置模板，可作为 README「部署」章节的素材。

---

## 一、部署架构

### 1.1 容器拓扑

```
   ┌───────────────────────── 一键启动（docker compose up -d）─────────────────────────┐
   │                                                                                  │
   │   ┌──────────────────────┐          ┌──────────────────────┐                     │
   │   │ frontend（nginx:80）  │──/api/──▶│ java（Spring Boot）   │                     │
   │   │ · 托管 Vue 静态产物    │          │ :8888  context=/api  │                     │
   │   └──────────────────────┘          └───┬─────────────┬────┘                     │
   │                                          │ HTTP        │ HTTP                     │
   │                                          ▼             ▼                          │
   │                                  ┌──────────────┐  ┌──────────────┐               │
   │                                  │ pybackend:8001│ │ minio:9000   │               │
   │                                  │ FastAPI 抽取/评估│ │ 语料文件存储 │               │
   │                                  └───────┬──────┘  └──────▲───────┘               │
   └──────────────────────────────────────────┼────────────────┼─────────────────────┘
                                              │                │
                     ┌────────────────────────┼────────────────┼──────────────────┐
                     │  外部基础设施（自带，不在启动范围）                            │
                     │  MySQL:3306  Neo4j:7687  Redis:6379  MinIO:9000/9001        │
                     │  MinerU:8000（可选）     LLM API（DeepSeek/Qwen/GLM）         │
                     └─────────────────────────────────────────────────────────────┘
```

### 1.2 应用容器清单（compose 管理，默认启动）

| 容器 | 镜像/构建 | 端口 | 职责 |
|------|-----------|------|------|
| `frontend` | `nginx:1.27-alpine` | 80（宿主机 `WEB_PORT`） | 静态资源托管 + `/api/` 反向代理 |
| `java` | `eclipse-temurin:21-jre` | 8888（`context-path=/api`） | 主服务：业务编排/权限/CRUD/SSE 透传 |
| `pybackend` | `python:3.11-slim` | 8001 | LLM/KOS/DL 抽取、质量评估、Agent 问答 |
| `mcp`（可选） | 见第十三章 | 8003 | MCP Server（独立进程） |

### 1.3 外部基础设施（需自备，默认不启动）

| 服务 | 默认端口 | 用途 | 是否必需 |
|------|----------|------|----------|
| MySQL 8+ | 3306 | 业务数据（用户/项目/模型/语料/抽取任务/评估记录/LLM 调用日志） | ✅ |
| Neo4j 5+ | 7474 / 7687 | 图谱数据（实体节点 + 关系边，按 `modelId` 隔离） | ✅ |
| Redis 7+ | 6379 | Spring Session + 会话缓存 | ✅ |
| MinIO | 9000 / 9001 | 语料文件（PDF/Word）存储，需存在 `kgraph` 桶 | ✅（仅文档上传功能需要） |
| MinerU | 8000 | PDF/Word → Markdown 解析 | ⭕ 可选 |
| LLM API | 443 | DeepSeek / Qwen / GLM | ✅ |

> 若希望这些基础服务也由容器托管，可使用第七章 `--profile infra` 模式（单机全栈），或自行编排；默认路径假设这些服务已可从宿主机访问。

### 1.4 服务间寻址

| 调用方 | 被调方 | 地址 |
|--------|--------|------|
| frontend(nginx) | java | `http://java:8888/api/`（同一 compose 网络） |
| java | pybackend | `http://pybackend:8001`（同一 compose 网络） |
| java / pybackend | MySQL / Neo4j / Redis / MinIO | **外部地址**，见第八章「基础设施寻址」 |

> **容器内 `localhost` 陷阱**：容器里的 `localhost` 指容器自身。访问宿主机上的基础服务必须用 `host.docker.internal`（macOS/Windows 原生支持；Linux 由 compose 的 `extra_hosts: host-gateway` 支持），或直接填数据库所在机器的局域网 IP / 托管域名。

---

## 二、前置条件

- Docker Engine 20.10+、Docker Compose v2（`docker compose` 命令）
- 已就绪且可从宿主机访问的 **MySQL / Neo4j / Redis / MinIO**（连接信息齐全）
- 一个可用的 LLM API Key（DeepSeek / Qwen / GLM 任一）
- 应用层内存建议 ≥ 2G 可用（基础设施资源另行评估）

---

## 三、部署目录准备

在项目根目录（`/Users/Yuan/xy_workspace/2.projects/java/KGraph`）下新增：

```
KGraph/
├── Dockerfile                      # Java 主服务镜像（上下文=项目根）
├── docker-compose.yml              # 编排文件（应用层默认启动，基础设施挂 infra profile）
├── .env                            # 端口/时区等变量（勿提交）
├── .env.example                    # 环境变量模板（可提交）
├── frontend/
│   ├── Dockerfile                  # 前端镜像
│   └── nginx.conf                  # nginx 配置
├── pybackend/
│   └── Dockerfile                  # Python 镜像
└── docker/
    └── config/
        ├── application-local.yml    # Java 配置（外部基础设施地址）
        └── config.json              # Python 配置（外部基础设施地址）
```

创建骨架目录：

```bash
cd /Users/Yuan/xy_workspace/2.projects/java/KGraph
mkdir -p docker/config
```

> 与传统全栈方案不同：**不需要** `docker/mysql/init` 目录——MySQL 建表由你在外部实例上手动导入（见第十章）。

---

## 四、关键前置代码改动（1 处）

> **必做**，否则同源反代方案下前端所有请求都会打到浏览器本机的 `localhost:8888`，远程部署直接失效。

前端 [request.ts](file:///Users/Yuan/xy_workspace/2.projects/java/KGraph/frontend/src/api/request.ts) 中 axios 的 `baseURL` 是硬编码绝对地址：

```ts
const service: AxiosInstance = axios.create({
  baseURL: 'http://localhost:8888/api',   // ← 改为相对路径
  ...
```

改为相对路径 `/api`（开发环境 vite 已配置 `/api` 代理到 `localhost:8888`，因此改后**开发与生产均可正常工作**）：

```ts
const service: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 60000,
  withCredentials: true
})
```

> 也可写作 `baseURL: import.meta.env.VITE_API_BASE_URL || '/api'` 以保留可配置性。推荐先用最简单的 `/api`。

---

## 五、Dockerfile

### 5.1 Java 主服务 —— `./Dockerfile`

> `.gitignore` 排除了 `maven-wrapper.jar`，因此**不要**在镜像里用 `./mvnw`，直接使用官方 maven 镜像。

```dockerfile
# ---------- 构建阶段 ----------
FROM maven:3.9-eclipse-temurin-21 AS builder
WORKDIR /build
# 先拷 pom 预热依赖，利用 Docker 层缓存加速后续构建
COPY pom.xml .
RUN mvn -B -q dependency:go-offline
COPY src ./src
RUN mvn -B -q clean package -DskipTests \
    && mv target/KGraph-0.0.1-SNAPSHOT.jar /build/app.jar

# ---------- 运行阶段 ----------
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=builder /build/app.jar /app/app.jar
EXPOSE 8888
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
```

> 若 `pom.xml` 的 `artifactId`/`version` 变更，需同步修正 `mv target/...jar` 的文件名；也可用 `RUN cp $(ls target/*.jar | grep -v original | head -1) /build/app.jar` 自动择取。

### 5.2 Python 微服务 —— `./pybackend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8001
CMD ["python", "main.py"]
```

> `requirements.txt` 只覆盖主服务；`mcp` SDK 仅 MCP Server 需要（见第十三章）。

### 5.3 前端 —— `./frontend/Dockerfile`

```dockerfile
# ---------- 构建阶段 ----------
FROM node:18-alpine AS builder
WORKDIR /build
COPY package*.json ./
RUN npm ci
COPY . .
# npm run build = vue-tsc --noEmit && vite build
RUN npm run build

# ---------- 运行阶段 ----------
FROM nginx:1.27-alpine
COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

> 若 `vue-tsc` 因存量类型报错中断构建，可临时降级为 `RUN npx vite build`（跳过类型检查）。

---

## 六、nginx.conf —— `./frontend/nginx.conf`

> SSE 是关键：**必须关闭代理缓冲**，否则智能问答与流式评估的逐字/逐指标推送会被 nginx 攒成整包，前端打字机效果失效。

```nginx
server {
    listen 80;
    server_name _;

    # 匹配后端 100MB 上传上限
    client_max_body_size 100m;

    root /usr/share/nginx/html;
    index index.html;

    # SPA 前端路由回退
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Java 主服务反向代理（context-path 即 /api）
    location /api/ {
        proxy_pass http://java:8888/api/;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection        "";

        # SSE 流式必备：禁用缓冲 + 拉长超时（后端评估超时 600s）
        proxy_buffering   off;
        proxy_cache       off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        chunked_transfer_encoding on;
    }
}
```

---

## 七、docker-compose.yml —— `./docker-compose.yml`

**默认只启动应用层三件套**；基础设施已用 `profiles: ["infra"]` 隔离，只有显式加 `--profile infra` 才会一并启动。

```yaml
name: kgraph

services:
  # ==================================================================
  # 应用层（默认启动：docker compose up -d）
  # ==================================================================
  pybackend:
    build:
      context: ./pybackend
      dockerfile: Dockerfile
    image: kgraph/pybackend:latest
    container_name: kgraph-pybackend
    restart: unless-stopped
    ports:
      - "8001:8001"
    volumes:
      # 配置只读挂载，密钥不进镜像
      - ./docker/config/config.json:/app/config.json:ro
    extra_hosts:
      # 让容器可用 host.docker.internal 访问宿主机上的基础服务（Linux 必需）
      - "host.docker.internal:host-gateway"

  java:
    build:
      context: .
      dockerfile: Dockerfile
    image: kgraph/java:latest
    container_name: kgraph-java
    restart: unless-stopped
    depends_on:
      pybackend:
        condition: service_started
    ports:
      - "8888:8888"
    environment:
      SPRING_PROFILES_ACTIVE: local
      # 从挂载目录加载 application-local.yml
      SPRING_CONFIG_ADDITIONAL_LOCATION: file:/app/config/
      TZ: ${TZ}
    volumes:
      - ./docker/config/application-local.yml:/app/config/application-local.yml:ro
    extra_hosts:
      - "host.docker.internal:host-gateway"

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    image: kgraph/frontend:latest
    container_name: kgraph-frontend
    restart: unless-stopped
    depends_on:
      - java
    ports:
      - "${WEB_PORT:-80}:80"

  # ==================================================================
  # 基础设施（默认不启动，需 --profile infra；单机全栈时使用）
  # 应用容器通过「宿主机端口」访问它们，与外部实例口径一致
  # ==================================================================
  mysql:
    image: mysql:8.0
    container_name: kgraph-mysql
    profiles: ["infra"]
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: seedboot
      TZ: ${TZ}
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --default-time-zone=+08:00
    ports:
      - "${MYSQL_PORT:-3306}:3306"
    volumes:
      - mysql-data:/var/lib/mysql

  neo4j:
    image: neo4j:5
    container_name: kgraph-neo4j
    profiles: ["infra"]
    restart: unless-stopped
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_server_memory_heap_max__size: 2G
      NEO4J_server_memory_pagecache_size: 1G
      TZ: ${TZ}
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j-data:/data
      - neo4j-logs:/logs

  redis:
    image: redis:7-alpine
    container_name: kgraph-redis
    profiles: ["infra"]
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes"]
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis-data:/data

  minio:
    image: minio/minio:latest
    container_name: kgraph-minio
    profiles: ["infra"]
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio-data:/data

  minio-init:
    image: minio/mc:latest
    container_name: kgraph-minio-init
    profiles: ["infra"]
    depends_on:
      - minio
    entrypoint: >
      /bin/sh -c "
      sleep 5;
      mc alias set local http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD} &&
      mc mb --ignore-existing local/kgraph &&
      echo 'MinIO bucket [kgraph] ready';
      "

volumes:
  mysql-data:
  neo4j-data:
  neo4j-logs:
  redis-data:
  minio-data:
```

### 两种启动方式

```bash
# ① 默认：只启动应用层（frontend + java + pybackend）
docker compose up -d

# ② 单机全栈：连基础设施一起启动（含 minio-init 自动建桶）
docker compose --profile infra up -d

# 只起基础设施（例如先备好库再起应用）
docker compose --profile infra up -d mysql neo4j redis minio minio-init
```

> 两种模式下，应用容器一律通过宿主机地址（`host.docker.internal:端口` 或局域网 IP）访问基础设施，配置模板无需改动。

---

## 八、配置文件

### 8.1 `.env.example`（复制为 `.env`）

> 默认模式下应用容器不读写 `.env` 中的基础设施密码——这些密码直接写在两个配置文件里。`.env` 仅在 `--profile infra` 时被 compose 用于创建基础容器。

```dotenv
# 时区：须与外部 MySQL 的时区一致（用 SELECT @@system_time_zone 核对）
TZ=Asia/Shanghai

# 应用层端口
WEB_PORT=80

# ↓ 仅 --profile infra 模式需要（与配置文件中的密码保持一致）
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=change-me-mysql-root
NEO4J_PASSWORD=change-me-neo4j
REDIS_PORT=6379
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=change-me-minio
```

```bash
cp .env.example .env
vim .env
```

### 8.2 基础设施寻址对照

两个配置文件里的**数据库/Neo4j/Redis/MinIO 地址**按你的部署形态填写：

| 场景 | 填什么 | 示例 |
|------|--------|------|
| 基础设施跑在**宿主机**（本机开发） | `host.docker.internal` | `jdbc:mysql://host.docker.internal:3306/seedboot` |
| 基础设施在**局域网另一台机器** | 该机 IP | `bolt://192.168.1.20:7687` |
| **云托管/内网域名** | 托管地址 | `mysql://rds-xxx.internal:3306` |
| ⚠️ 切勿填 `localhost` | — | 容器内 `localhost` = 容器自身，连不上宿主机 |

> Linux 宿主机场景已由 compose 的 `extra_hosts: host-gateway` 支持 `host.docker.internal`。

### 8.3 Java 配置 —— `./docker/config/application-local.yml`

> 结构同 [application-local.example.yml](file:///Users/Yuan/xy_workspace/2.projects/java/KGraph/src/main/resources/application-local.example.yml)，仅把连接地址改为外部基础设施。

```yaml
spring:
  datasource:
    # serverTimezone 必须与外部 MySQL 实际时区一致（SELECT @@system_time_zone 核对）
    url: jdbc:mysql://host.docker.internal:3306/seedboot?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai&characterEncoding=utf-8
    username: root
    password: change-me-mysql-root
    driver-class-name: com.mysql.cj.jdbc.Driver
  data:
    redis:
      host: host.docker.internal
      port: 6379
      database: 0
  neo4j:
    uri: bolt://host.docker.internal:7687
    authentication:
      username: neo4j
      password: change-me-neo4j
  ai:
    openai:
      base-url: https://api.deepseek.com
      api-key: sk-your-llm-api-key
      chat:
        options:
          model: deepseek-chat
          temperature: 0.7
    chat:
      memory:
        repository:
          jdbc:
            initialize-schema: never

mybatis-plus:
  configuration:
    map-underscore-to-camel-case: false
    log-impl: org.apache.ibatis.logging.stdout.StdOutImpl
  global-config:
    db-config:
      table-underline: false
      logic-delete-field: isDelete
      logic-delete-value: 1
      logic-not-delete-value: 0

python:
  service:
    url: http://pybackend:8001

minio:
  endpoint: http://host.docker.internal:9000
  access-key: minioadmin
  secret-key: change-me-minio
  bucket: kgraph

mineru:
  # MinerU 跑在宿主机：http://host.docker.internal:8000
  # MinerU 已容器化并公布端口：按其地址填写
  base-url: http://host.docker.internal:8000

server:
  port: 8888
  servlet:
    context-path: /api
```

### 8.4 Python 配置 —— `./docker/config/config.json`

> 结构同 [config.example.json](file:///Users/Yuan/xy_workspace/2.projects/java/KGraph/pybackend/config.example.json)，仅替换主机名。
> **注意**：该文件是纯 JSON，不支持环境变量替换，需直接写外部地址。

```json
{
  "model": {
    "model_name": "deepseek-chat",
    "api_key": "sk-your-llm-api-key",
    "base_url": "https://api.deepseek.com/v1"
  },
  "neo4j": {
    "username": "neo4j",
    "password": "change-me-neo4j",
    "url": "bolt://host.docker.internal:7687"
  },
  "memory": {
    "mysql": {
      "host": "host.docker.internal",
      "port": 3306,
      "user": "root",
      "password": "change-me-mysql-root",
      "database": "seedboot"
    },
    "redis": {
      "host": "host.docker.internal",
      "port": 6379,
      "db": 0,
      "max_messages": 50
    }
  }
}
```

> **关于 `prompt.json`**：源码中仅 `utils/read/read_config.py` 的 `read_prompt()` 读取它，运行时调用链未使用，因此**不是运行必需**；compose 未挂载它，无需准备。

### 8.5 LLM API Key 的三处落点

| 位置 | 用途 | 是否必填 |
|------|------|----------|
| `docker/config/config.json` → `model.api_key` | Python 抽取/评估/问答默认模型 | ✅ 必填 |
| `docker/config/application-local.yml` → `spring.ai.openai.api-key` | Java 侧 Spring AI 配置 | ✅ 建议填 |
| `llm_model` 表 `api_key` 字段 | 智能问答模型选择器按 `llmModelId` 解析 | ✅ 首次入库后需更新 |

---

## 九、启动步骤

```bash
cd /Users/Yuan/xy_workspace/2.projects/java/KGraph

# 0) 确认外部基础设施已就绪且可从宿主机连通
#    （MySQL / Neo4j / Redis / MinIO 已建库建桶、账号密码齐全）

# 1) 准备配置
cp .env.example .env && vim .env
# 编辑 docker/config/application-local.yml 与 docker/config/config.json：
#   填入外部基础设施的真实地址与密码、LLM API Key

# 2) 导入 MySQL 表结构（首次，见第十章）
# 3) 执行 Neo4j 约束脚本（首次，见第十章）

# 4) 构建应用镜像（首次较慢：Maven 依赖 + npm 依赖 + pip 依赖）
docker compose build

# 5) 一键启动应用层（不含 MySQL/Redis 等基础服务）
docker compose up -d

# 6) 查看状态与日志
docker compose ps
docker compose logs -f java pybackend
```

---

## 十、外部基础设施初始化（手动一次性）

基础设施不在一键启动范围内，首次部署需在**外部实例**上完成以下初始化。

### 10.1 MySQL：建库 + 导入表结构

```bash
# 建库
mysql -h <mysql-host> -P 3306 -uroot -p \
  -e "CREATE DATABASE IF NOT EXISTS seedboot DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 按序导入（chat_session.sql 为会话标题表，勿漏）
cd /Users/Yuan/xy_workspace/2.projects/java/KGraph
for f in sql/kgraph.sql sql/user.sql sql/chat_history.sql sql/chat_session.sql sql/llm_model.sql sql/log.sql; do
  mysql -h <mysql-host> -P 3306 -uroot -p seedboot < "$f"
done
```

> 脚本内均为 `CREATE TABLE IF NOT EXISTS`，可重复执行。

### 10.2 更新 `llm_model` 表的 API Key

[llm_model.sql](file:///Users/Yuan/xy_workspace/2.projects/java/KGraph/sql/llm_model.sql) 中三条初始记录的 `api_key` 为占位符 `REPLACE_ME`，不更新则智能问答无法调用模型：

```bash
mysql -h <mysql-host> -P 3306 -uroot -p seedboot \
  -e "UPDATE llm_model SET api_key='sk-your-llm-api-key';"
```

### 10.3 Neo4j：执行约束/索引脚本

[sql/graph.sql](file:///Users/Yuan/xy_workspace/2.projects/java/KGraph/sql/graph.sql) 是 Cypher 脚本（建唯一约束与索引），**不是** MySQL 脚本：

```bash
cypher-shell -a bolt://<neo4j-host>:7687 -u neo4j -p <neo4j-password> -f sql/graph.sql
```

> 也可打开 Neo4j Browser（`http://<neo4j-host>:7474`）手动粘贴执行。脚本内均为 `IF NOT EXISTS`，可重复执行。

### 10.4 MinIO：建桶

```bash
# 使用 mc 客户端
mc alias set kg http://<minio-host>:9000 <access-key> <secret-key>
mc mb --ignore-existing kg/kgraph

# 或直接打开控制台 http://<minio-host>:9001 手动创建桶 kgraph
```

> 使用 `--profile infra` 全栈模式时，`minio-init` 容器会自动建桶，本节可跳过。

---

## 十一、验证清单

| 检查项 | 命令 / 地址 | 期望 |
|--------|-------------|------|
| 容器状态 | `docker compose ps` | `frontend` / `java` / `pybackend` 均 `Up` |
| 基础设施连通 | 由宿主机分别 `telnet <host> 3306/7687/6379/9000` | 端口可通 |
| Java 接口文档 | `http://<host>:8888/api/doc.html` | Knife4j 页面可打开 |
| Python 文档 | `http://<host>:8001/docs` | Swagger 页面可打开 |
| 前端页面 | `http://<host>:${WEB_PORT}` | 出现登录页 |
| 同源反代 | 浏览器打开前端后登录 | 请求命中 `http://<host>/api/...`，无跨域报错 |
| MySQL 表 | 外部实例执行 `show tables;` | 含 `user`、`graph_project`、`llm_model` 等 |
| Neo4j 约束 | Neo4j Browser 执行 `SHOW CONSTRAINTS;` | 含 `entity_unique` |
| MinIO 桶 | 控制台 `http://<minio-host>:9001` | 存在 `kgraph` 桶 |
| 一次冒烟抽取 | 前端「LLM 抽取」选模型+语料 → 开始抽取 | 返回实体/关系，Neo4j 出现节点 |
| 流式问答 | 前端「智能问答」提问 | 思考/工具/回答逐字流式，无整包卡顿 |

---

## 十二、MinerU（可选）

MinerU 是独立进程，提供 `/file_parse` 把 PDF/Word 转为 Markdown。**未部署不影响文本输入类功能**，仅「文档上传 → 自动解析」不可用。

### 方案 A：宿主机运行（推荐）

```bash
pip install -U "magic-pdf[full]"   # 或按 MinerU 官方文档安装
mineru-api --port 8000
```

`application-local.yml` 中设 `mineru.base-url: http://host.docker.internal:8000`（compose 已注入 `host.docker.internal`）。

### 方案 B：独立容器

MinerU 官方无长期稳定的通用镜像，可基于其官方 Dockerfile 自行构建，并**必须挂载模型缓存目录**（首次运行会下载数 GB 模型）：

```yaml
  mineru:
    build:
      context: ./docker/mineru      # 基于 MinerU 官方 Dockerfile
    container_name: kgraph-mineru
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - mineru-models:/root/.cache   # 持久化模型，避免每次重启重下
```

> 容器化时 `mineru.base-url` 填 `http://host.docker.internal:8000`（若公布宿主机端口），或将其加入应用 compose 网络后填服务名。

---

## 十三、MCP Server（可选）

MCP Server 独立进程，**只依赖 LLM API**，不连 Neo4j/MySQL，可与主服务并行部署：

```dockerfile
# ./pybackend/Dockerfile.mcp
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install -r requirements.txt && pip install "mcp>=2.2,<3"
COPY . .
EXPOSE 8003
CMD ["python", "mcp_server.py", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8003"]
```

```yaml
  mcp:
    build:
      context: ./pybackend
      dockerfile: Dockerfile.mcp
    container_name: kgraph-mcp
    restart: unless-stopped
    ports:
      - "8003:8003"
    volumes:
      - ./docker/config/config.json:/app/config.json:ro
```

> stdio 模式不适合容器化（需与客户端同进程交互），容器场景请用 `streamable-http` 或 `sse`。详见 [MCP_SERVER_TECHNICAL_SOLUTION.md](file:///Users/Yuan/xy_workspace/2.projects/java/KGraph/MCP_SERVER_TECHNICAL_SOLUTION.md)。

---

## 十四、日常运维

```bash
# 停止（保留数据） / 删除容器（保留数据卷）
docker compose stop
docker compose down

# 重建某服务并重启
docker compose build java && docker compose up -d java

# 查看日志（最近 200 行）
docker compose logs --tail=200 pybackend

# 进入应用容器
docker compose exec java   sh
docker compose exec pybackend bash

# 全栈模式（含基础设施）启停
docker compose --profile infra up -d
docker compose --profile infra down
```

### 数据备份（针对外部实例）

```bash
# MySQL
mysqldump -h <mysql-host> -uroot -p --databases seedboot > backup_seedboot_$(date +%F).sql

# Neo4j（停止写入后执行）
neo4j-admin database dump neo4j --to-path=/tmp
# 或通过 Neo4j Browser / Bolt 导出

# MinIO：使用 mc mirror 到本地或另一桶
mc mirror kg/kgraph ./backup_minio_$(date +%F)
```

---

## 十五、常见问题排查

| 现象 | 原因 | 处理 |
|------|------|------|
| 前端所有请求命中 `localhost:8888`，报跨域/连接失败 | 未做第四章的 `baseURL` 改动 | 将 `request.ts` 的 `baseURL` 改为 `/api` 后重新构建前端 |
| Java/Python 连不上数据库，报连接被拒 | 配置里误填 `localhost` | 改为 `host.docker.internal`（宿主机）或真实 IP/域名（跨机/托管） |
| 智能问答/评估「攒包」输出，无逐字效果 | nginx 缓冲未关闭 | 确认 `nginx.conf` 含 `proxy_buffering off` 与 `proxy_read_timeout 600s`，重建前端镜像 |
| Java 连接 MySQL 报 `Public Key Retrieval is not allowed` / 连接不稳 | 缺 `allowPublicKeyRetrieval=true` | 已在 8.3 模板中补上；确认使用该模板 |
| 时间整体偏移 8 小时 | `serverTimezone` 与外部 MySQL 时区不一致 | 用 `SELECT @@system_time_zone` 核对，把 JDBC `serverTimezone` 与配置文件的 `TZ` 对齐 |
| 上传 > 1MB 文件报 413 | nginx 默认上限 1MB | `nginx.conf` 设 `client_max_body_size 100m` |
| Python 启动报 `No module named 'fitz'` / `pymupdf` | `requirements.txt` 未显式列出 PDF 解析库 | 在 `pybackend/Dockerfile` 追加 `RUN pip install pymupdf` |
| `pybackend` 报 `FileNotFoundError: config.json` | 挂载路径或文件名不匹配 | 确认挂载到 `/app/config.json` |
| Java 启动报缺少 `application-local.yml` | profile 与挂载文件不匹配 | 保持 `SPRING_PROFILES_ACTIVE=local`，文件名为 `application-local.yml`，`SPRING_CONFIG_ADDITIONAL_LOCATION=file:/app/config/` |
| Java 启动因基础设施不可用而反复重试/退出 | 外部依赖未就绪 | 先确保 MySQL/Neo4j/Redis 可连；必要时用 compose `restart: unless-stopped` 等待其恢复 |
| 语料上传成功但解析一直「处理中」 | MinerU 未部署或地址不通 | 部署 MinerU 并核对 `mineru.base-url` |
| `--profile infra` 下建桶失败 | `minio-init` 早于 minio 就绪 | compose 内已加 `sleep 5` 兜底；仍失败则手动执行 `docker compose --profile infra up -d minio-init` |
| 镜像构建失败于 `vue-tsc` 类型检查 | 存量类型错误 | 将构建命令改为 `npx vite build` 跳过类型检查 |
| 首次构建 `mvn dependency:go-offline` 超时 | 网络慢 | 配置 Maven 镜像源（如阿里云）后重试 |

---

## 附：端口与版本速查

| 项 | 值 |
|----|-----|
| 应用容器（一键启动） | `frontend:80` / `java:8888(/api)` / `pybackend:8001` |
| 外部基础设施 | `MySQL:3306` / `Neo4j:7474+7687` / `Redis:6379` / `MinIO:9000+9001` |
| 可选服务 | `MinerU:8000` / `MCP:8003` |
| 版本 | JDK 21 / Node 18 / Python 3.11 / MySQL 8+ / Neo4j 5+ / Redis 7+ |
| 镜像基底 | `maven:3.9-eclipse-temurin-21`、`eclipse-temurin:21-jre`、`node:18-alpine`、`nginx:1.27-alpine`、`python:3.11-slim` |

-- ======================================================================
-- Neo4j 图谱数据库脚本
-- ----------------------------------------------------------------------
-- 说明：Neo4j 使用图模型而非关系表，此处脚本用于初始化约束、索引，
--       以及提供常用查询/清理示例。本系统所有节点统一打标签 :Entity，
--       关系统一使用 :RELATED 类型，业务类型存储在 type/relationType 属性中，
--       并通过 modelId 属性实现多模型图谱实例隔离。
-- ======================================================================

-- ----------------------------------------------------------------------
-- 1. 约束与索引（首次部署执行一次即可）
-- ----------------------------------------------------------------------

-- 实体唯一性约束：(name, type, modelId) 三元组唯一，避免同模型下重复节点
CREATE CONSTRAINT entity_unique IF NOT EXISTS
FOR (n:Entity) REQUIRE (n.name, n.type, n.modelId) IS UNIQUE;

-- modelId 索引：加速按模型隔离的查询过滤（最常用的 WHERE 条件）
CREATE INDEX entity_modelId_idx IF NOT EXISTS
FOR (n:Entity) ON (n.modelId);

-- type 索引：加速按实体类型筛选
CREATE INDEX entity_type_idx IF NOT EXISTS
FOR (n:Entity) ON (n.type);

-- 关系 modelId 索引：加速关系按模型过滤
CREATE INDEX related_modelId_idx IF NOT EXISTS
FOR ()-[r:RELATED]-() ON (r.modelId);

-- 关系 relationType 索引：加速按业务关系类型筛选
CREATE INDEX related_relationType_idx IF NOT EXISTS
FOR ()-[r:RELATED]-() ON (r.relationType);

-- ----------------------------------------------------------------------
-- 2. 节点 Schema 示例（参考结构，实际数据由抽取流程写入）
-- ----------------------------------------------------------------------
// CREATE (n:Entity {
//   name: '张三',
//   type: '人物',                    -- 实体类型（对应 graph_entity_type.entityName）
//   modelId: 1,                      -- 所属图谱模型 ID（隔离用，必填）
//   relationType: null,              -- 仅关系有此字段，节点无
//   createTime: timestamp(),         -- 创建时间
//   // 其他业务属性（动态扩展）
//   age: 30,
//   occupation: '工程师'
// })

// 关系示例：
// MATCH (a:Entity {name: '张三', modelId: 1}),
//       (b:Entity {name: '北京', modelId: 1})
// CREATE (a)-[:RELATED {
//   type: '出生地',                  -- 原始关系名（保留 type 字段以兼容旧逻辑）
//   relationType: '出生地',         -- 业务关系名（推荐使用此字段）
//   modelId: 1,
//   createTime: timestamp()
// }]->(b)

-- ----------------------------------------------------------------------
-- 3. 常用查询示例
-- ----------------------------------------------------------------------

-- 3.1 查询某模型下所有实体（默认前 100 个）
// MATCH (n:Entity)
// WHERE n.modelId = 1
// RETURN n
// LIMIT 100;

-- 3.2 查询某模型下的所有关系
// MATCH (a:Entity)-[r:RELATED]->(b:Entity)
// WHERE r.modelId = 1
// RETURN a, r, b
// LIMIT 50;

-- 3.3 按实体类型筛选
// MATCH (n:Entity {modelId: 1, type: '人物'})
// RETURN n.name AS name, n
// ORDER BY n.name;

-- 3.4 按业务关系类型筛选（推荐使用 relationType 字段）
// MATCH (a:Entity)-[r:RELATED {relationType: '出生于'}]->(b:Entity)
// WHERE a.modelId = 1
// RETURN a.name AS head, r.relationType AS relation, b.name AS tail;

-- 3.5 图谱统计（节点数 / 关系数 / 类型分布）
// MATCH (n:Entity {modelId: 1})
// RETURN count(n) AS nodeCount;
// MATCH ()-[r:RELATED {modelId: 1}]->()
// RETURN count(r) AS relationCount;
// MATCH (n:Entity {modelId: 1})
// RETURN n.type AS type, count(n) AS count
// ORDER BY count DESC;

-- ----------------------------------------------------------------------
-- 4. 数据清理脚本（谨慎使用）
-- ----------------------------------------------------------------------

-- 4.1 清空指定模型的所有图谱数据（节点 + 关系）
// MATCH (n:Entity {modelId: 1})-[r:RELATED]-()
// DELETE r;
// MATCH (n:Entity {modelId: 1})
// DELETE n;

-- 4.2 清空整个图谱（所有模型，慎用）
// MATCH (n)
// DETACH DELETE n;

-- 4.3 删除约束与索引（如需重建）
// DROP CONSTRAINT entity_unique;
// DROP INDEX entity_modelId_idx;
// DROP INDEX entity_type_idx;
// DROP INDEX related_modelId_idx;
// DROP INDEX related_relationType_idx;

-- ----------------------------------------------------------------------
-- 5. 关键设计说明
-- ----------------------------------------------------------------------
-- (1) 多模型隔离：所有节点和关系都带 modelId 属性，查询时通过
--     WHERE n.modelId = $modelId 过滤，实现一个 Neo4j 实例承载多套图谱。
-- (2) 关系类型存储：Neo4j 关系统一使用 :RELATED 类型，业务关系名存于
--     relationType 属性（保留 type 字段以兼容历史逻辑）。
--     原因：Neo4j 不支持动态关系类型，使用统一 :RELATED + relationType 属性
--     既保证 Cypher 语句的通用性，又避免 type 属性被关系类型覆盖的问题。
-- (3) 写入方式：抽取结果通过 Python (graph_writer.py) 使用 MERGE 语句幂等写入，
--     结构化转化由 Java (StructureExtractionService) 直接执行 Cypher。

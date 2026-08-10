package com.yuan.seedboot.service;

import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Record;
import org.neo4j.driver.Result;
import org.neo4j.driver.Session;
import org.neo4j.driver.Value;
import org.neo4j.driver.types.Node;
import org.neo4j.driver.types.Relationship;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Neo4j 服务：执行 Cypher 查询，提供图谱探索能力
 */
@Slf4j
@Service
public class Neo4jService {

    @Resource
    private Driver neo4jDriver;

    /**
     * 获取节点与边（按 modelId 限制，支持 limit）
     *
     * @param modelId 模型 id
     * @param limit   最多返回节点数
     * @return {nodes: [...], edges: [...]}
     */
    public Map<String, Object> getNodes(Long modelId, int limit) {
        Map<String, Object> params = new HashMap<>();
        params.put("modelId", modelId);
        params.put("limit", limit);

        // 查询节点
        List<Map<String, Object>> nodes = executeQuery(
                "MATCH (n:Entity) WHERE n.modelId = $modelId RETURN n LIMIT $limit",
                params,
                record -> nodeToMap(record.get("n").asNode())
        );

        // 查询边（限制在已查询节点范围内）
        List<String> nodeIds = nodes.stream()
                .map(n -> (String) n.get("elementId"))
                .collect(Collectors.toList());

        List<Map<String, Object>> edges = new ArrayList<>();
        if (!nodeIds.isEmpty()) {
            Map<String, Object> edgeParams = new HashMap<>();
            edgeParams.put("nodeIds", nodeIds);
            edges = executeQuery(
                    "MATCH (a:Entity)-[r]->(b:Entity) " +
                            "WHERE elementId(a) IN $nodeIds AND elementId(b) IN $nodeIds " +
                            "RETURN a, r, b",
                    edgeParams,
                    record -> buildEdge(record.get("a").asNode(), record.get("r").asRelationship(), record.get("b").asNode())
            );
        }

        Map<String, Object> result = new HashMap<>();
        result.put("nodes", nodes);
        result.put("edges", edges);
        return result;
    }

    /**
     * 获取邻居节点与边（按 nodeId）
     *
     * @param nodeId 节点 elementId
     * @return {nodes: [...], edges: [...]}
     */
    public Map<String, Object> getNeighbors(String nodeId) {
        Map<String, Object> params = new HashMap<>();
        params.put("nodeId", nodeId);

        List<Map<String, Object>> records = executeQuery(
                "MATCH (n:Entity)-[r]-(m:Entity) WHERE elementId(n) = $nodeId RETURN n, r, m",
                params,
                record -> {
                    Map<String, Object> row = new HashMap<>();
                    row.put("source", nodeToMap(record.get("n").asNode()));
                    row.put("relation", relationshipToMap(record.get("r").asRelationship()));
                    row.put("target", nodeToMap(record.get("m").asNode()));
                    return row;
                }
        );

        // 去重节点
        Map<String, Map<String, Object>> nodeMap = new HashMap<>();
        List<Map<String, Object>> edges = new ArrayList<>();
        for (Map<String, Object> row : records) {
            @SuppressWarnings("unchecked")
            Map<String, Object> src = (Map<String, Object>) row.get("source");
            @SuppressWarnings("unchecked")
            Map<String, Object> tgt = (Map<String, Object>) row.get("target");
            @SuppressWarnings("unchecked")
            Map<String, Object> rel = (Map<String, Object>) row.get("relation");

            String srcId = (String) src.get("elementId");
            String tgtId = (String) tgt.get("elementId");
            nodeMap.putIfAbsent(srcId, src);
            nodeMap.putIfAbsent(tgtId, tgt);

            Map<String, Object> edge = new HashMap<>();
            edge.put("source", srcId);
            edge.put("target", tgtId);
            edge.put("label", rel.get("type"));
            edge.put("data", rel);
            edges.add(edge);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("nodes", new ArrayList<>(nodeMap.values()));
        result.put("edges", edges);
        return result;
    }

    /**
     * 搜索节点与边（按名称模糊查询）
     *
     * @param modelId 模型 id
     * @param keyword 关键词
     * @return {nodes: [...], edges: [...]}
     */
    public Map<String, Object> searchNodes(Long modelId, String keyword) {
        Map<String, Object> params = new HashMap<>();
        params.put("modelId", modelId);
        params.put("keyword", keyword);

        // 查询节点
        List<Map<String, Object>> nodes = executeQuery(
                "MATCH (n:Entity) WHERE n.modelId = $modelId AND toLower(n.name) CONTAINS toLower($keyword) RETURN n LIMIT 50",
                params,
                record -> nodeToMap(record.get("n").asNode())
        );

        // 收集节点 elementId
        List<String> nodeIds = nodes.stream()
                .map(n -> (String) n.get("elementId"))
                .collect(Collectors.toList());

        // 查询边（只查询搜索到的节点之间的边）
        List<Map<String, Object>> edges = new ArrayList<>();
        if (!nodeIds.isEmpty()) {
            Map<String, Object> edgeParams = new HashMap<>();
            edgeParams.put("nodeIds", nodeIds);
            edges = executeQuery(
                    "MATCH (a:Entity)-[r]->(b:Entity) " +
                            "WHERE elementId(a) IN $nodeIds AND elementId(b) IN $nodeIds " +
                            "RETURN a, r, b",
                    edgeParams,
                    record -> buildEdge(record.get("a").asNode(), record.get("r").asRelationship(), record.get("b").asNode())
            );
        }

        Map<String, Object> result = new HashMap<>();
        result.put("nodes", nodes);
        result.put("edges", edges);
        return result;
    }

    /**
     * 图谱统计（节点数、关系数、类型分布）
     *
     * @param modelId 模型 id
     * @return 统计结果，typeDistribution 为 Map<type, count>
     */
    public Map<String, Object> getStats(Long modelId) {
        Map<String, Object> stats = new HashMap<>();
        Map<String, Object> params = new HashMap<>();
        params.put("modelId", modelId);

        // 节点数
        List<Map<String, Object>> nodeCountResult = executeQuery(
                "MATCH (n:Entity) WHERE n.modelId = $modelId RETURN count(n) as nodeCount",
                params,
                record -> {
                    Map<String, Object> m = new HashMap<>();
                    m.put("nodeCount", record.get("nodeCount").asLong());
                    return m;
                });
        stats.put("nodeCount", nodeCountResult.isEmpty() ? 0L : nodeCountResult.get(0).get("nodeCount"));

        // 关系数
        List<Map<String, Object>> relCountResult = executeQuery(
                "MATCH ()-[r]->() WHERE r.modelId = $modelId RETURN count(r) as relationCount",
                params,
                record -> {
                    Map<String, Object> m = new HashMap<>();
                    m.put("relationCount", record.get("relationCount").asLong());
                    return m;
                });
        stats.put("relationCount", relCountResult.isEmpty() ? 0L : relCountResult.get(0).get("relationCount"));

        // 类型分布（转为 Map<type, count>）
        List<Map<String, Object>> typeDistribution = executeQuery(
                "MATCH (n:Entity) WHERE n.modelId = $modelId RETURN n.type as type, count(n) as count",
                params,
                record -> {
                    Map<String, Object> m = new HashMap<>();
                    Value typeVal = record.get("type");
                    m.put("type", typeVal.isNull() ? null : typeVal.asString());
                    m.put("count", record.get("count").asLong());
                    return m;
                });
        Map<String, Object> typeMap = new HashMap<>();
        for (Map<String, Object> item : typeDistribution) {
            String type = (String) item.get("type");
            typeMap.put(type == null ? "unknown" : type, item.get("count"));
        }
        stats.put("typeDistribution", typeMap);

        return stats;
    }

    /**
     * 批量获取多个模型的实体数与关系数
     *
     * @param modelIds 模型 id 列表
     * @return Map<modelId, long[]{nodeCount, relationCount}>
     */
    public Map<Long, long[]> getCountsForModels(List<Long> modelIds) {
        Map<Long, long[]> result = new HashMap<>();
        if (modelIds == null || modelIds.isEmpty()) {
            return result;
        }
        // 初始化
        for (Long id : modelIds) {
            result.put(id, new long[]{0L, 0L});
        }
        Map<String, Object> params = new HashMap<>();
        params.put("modelIds", modelIds);

        // 实体数（按 modelId 分组）
        List<Map<String, Object>> nodeCounts = executeQuery(
                "MATCH (n:Entity) WHERE n.modelId IN $modelIds RETURN n.modelId as modelId, count(n) as cnt",
                params,
                record -> {
                    Map<String, Object> m = new HashMap<>();
                    m.put("modelId", record.get("modelId").asLong());
                    m.put("cnt", record.get("cnt").asLong());
                    return m;
                });
        for (Map<String, Object> item : nodeCounts) {
            Long mid = (Long) item.get("modelId");
            result.get(mid)[0] = (Long) item.get("cnt");
        }

        // 关系数（按 modelId 分组）
        List<Map<String, Object>> relCounts = executeQuery(
                "MATCH ()-[r]->() WHERE r.modelId IN $modelIds RETURN r.modelId as modelId, count(r) as cnt",
                params,
                record -> {
                    Map<String, Object> m = new HashMap<>();
                    m.put("modelId", record.get("modelId").asLong());
                    m.put("cnt", record.get("cnt").asLong());
                    return m;
                });
        for (Map<String, Object> item : relCounts) {
            Long mid = (Long) item.get("modelId");
            if (result.containsKey(mid)) {
                result.get(mid)[1] = (Long) item.get("cnt");
            }
        }

        return result;
    }

    // ======================== 实体管理（Neo4j 数据层 CRUD） ========================

    /** 系统字段，不允许通过属性接口修改/删除 */
    private static final Set<String> SYSTEM_FIELDS = Set.of(
            "name", "type", "modelId", "createTime", "elementId", "labels");
    /** 属性名合法校验（防 Cypher 注入） */
    private static final Pattern PROP_KEY_PATTERN = Pattern.compile("^[a-zA-Z_][a-zA-Z0-9_]*$");

    /**
     * 分页查询实体列表（按 modelId）
     *
     * @param modelId  模型 id
     * @param keyword  名称关键词（可选）
     * @param pageNum  页码（从 1 开始）
     * @param pageSize 每页条数
     * @return {records, total, pageNum, pageSize}
     */
    public Map<String, Object> listEntities(Long modelId, String keyword, int pageNum, int pageSize) {
        Map<String, Object> params = new HashMap<>();
        params.put("modelId", modelId);
        params.put("skip", (pageNum - 1) * pageSize);
        params.put("limit", pageSize);

        boolean hasKeyword = keyword != null && !keyword.isBlank();
        if (hasKeyword) {
            params.put("keyword", keyword);
        }

        String listCypher = hasKeyword
                ? "MATCH (n:Entity) WHERE n.modelId = $modelId AND toLower(n.name) CONTAINS toLower($keyword) "
                + "RETURN n ORDER BY n.name SKIP $skip LIMIT $limit"
                : "MATCH (n:Entity) WHERE n.modelId = $modelId "
                + "RETURN n ORDER BY n.name SKIP $skip LIMIT $limit";

        List<Map<String, Object>> entities = executeQuery(listCypher, params,
                record -> nodeToMap(record.get("n").asNode()));

        String countCypher = hasKeyword
                ? "MATCH (n:Entity) WHERE n.modelId = $modelId AND toLower(n.name) CONTAINS toLower($keyword) RETURN count(n) as cnt"
                : "MATCH (n:Entity) WHERE n.modelId = $modelId RETURN count(n) as cnt";
        List<Long> countResult = executeQuery(countCypher, params,
                record -> record.get("cnt").asLong());
        long total = countResult.isEmpty() ? 0L : countResult.get(0);

        Map<String, Object> result = new HashMap<>();
        result.put("records", entities);
        result.put("total", total);
        result.put("pageNum", pageNum);
        result.put("pageSize", pageSize);
        return result;
    }

    /**
     * 获取实体详情（含全部属性）
     *
     * @param nodeId 节点 elementId
     * @return 节点 Map（含 elementId/labels + 全部属性），不存在返回 null
     */
    public Map<String, Object> getEntityDetail(String nodeId) {
        Map<String, Object> params = new HashMap<>();
        params.put("nodeId", nodeId);
        List<Map<String, Object>> result = executeQuery(
                "MATCH (n:Entity) WHERE elementId(n) = $nodeId RETURN n",
                params,
                record -> nodeToMap(record.get("n").asNode()));
        return result.isEmpty() ? null : result.get(0);
    }

    /**
     * 创建实体节点
     *
     * @param modelId    模型 id
     * @param name       实体名称
     * @param type       实体类型
     * @param properties 业务属性（可选，不能包含系统字段）
     * @return 新建节点 Map
     */
    public Map<String, Object> createEntity(Long modelId, String name, String type,
                                            Map<String, Object> properties) {
        // 过滤掉系统字段
        Map<String, Object> safeProps = filterSystemFields(properties);

        Map<String, Object> params = new HashMap<>();
        params.put("modelId", modelId);
        params.put("name", name);
        params.put("type", type);
        params.put("properties", safeProps);

        List<Map<String, Object>> result = executeQuery(
                "CREATE (n:Entity {name: $name, type: $type, modelId: $modelId}) "
                        + "SET n += $properties, n.createTime = timestamp() RETURN n",
                params,
                record -> nodeToMap(record.get("n").asNode()));
        return result.isEmpty() ? null : result.get(0);
    }

    /**
     * 更新实体名称和类型
     *
     * @param nodeId 节点 elementId
     * @param name   新名称
     * @param type   新类型
     * @return 更新后节点 Map
     */
    public Map<String, Object> updateEntity(String nodeId, String name, String type) {
        Map<String, Object> params = new HashMap<>();
        params.put("nodeId", nodeId);
        params.put("name", name);
        params.put("type", type);

        List<Map<String, Object>> result = executeQuery(
                "MATCH (n:Entity) WHERE elementId(n) = $nodeId "
                        + "SET n.name = $name, n.type = $type RETURN n",
                params,
                record -> nodeToMap(record.get("n").asNode()));
        return result.isEmpty() ? null : result.get(0);
    }

    /**
     * 删除实体节点（及其关联关系）
     *
     * @param nodeId 节点 elementId
     * @return 是否删除成功
     */
    public boolean deleteEntity(String nodeId) {
        Map<String, Object> params = new HashMap<>();
        params.put("nodeId", nodeId);
        try (Session session = neo4jDriver.session()) {
            session.run("MATCH (n:Entity) WHERE elementId(n) = $nodeId DETACH DELETE n", params).consume();
            return true;
        } catch (Exception e) {
            log.error("Neo4j 删除节点失败, nodeId={}", nodeId, e);
            throw e;
        }
    }

    /**
     * 设置实体属性（新增或更新）
     * <p>
     * 使用 SET n += $props 方式，安全且支持动态属性名。
     *
     * @param nodeId 节点 elementId
     * @param key    属性名（不能是系统字段）
     * @param value  属性值
     * @return 更新后节点 Map
     */
    public Map<String, Object> setEntityProperty(String nodeId, String key, Object value) {
        if (SYSTEM_FIELDS.contains(key)) {
            throw new IllegalArgumentException("不能修改系统字段: " + key);
        }
        Map<String, Object> params = new HashMap<>();
        params.put("nodeId", nodeId);
        Map<String, Object> props = new HashMap<>();
        props.put(key, value);
        params.put("props", props);

        List<Map<String, Object>> result = executeQuery(
                "MATCH (n:Entity) WHERE elementId(n) = $nodeId SET n += $props RETURN n",
                params,
                record -> nodeToMap(record.get("n").asNode()));
        return result.isEmpty() ? null : result.get(0);
    }

    /**
     * 删除实体属性
     *
     * @param nodeId 节点 elementId
     * @param key    属性名（不能是系统字段）
     * @return 是否删除成功
     */
    public boolean removeEntityProperty(String nodeId, String key) {
        if (SYSTEM_FIELDS.contains(key)) {
            throw new IllegalArgumentException("不能删除系统字段: " + key);
        }
        if (!PROP_KEY_PATTERN.matcher(key).matches()) {
            throw new IllegalArgumentException("属性名只能包含字母、数字和下划线，且不能以数字开头");
        }
        Map<String, Object> params = new HashMap<>();
        params.put("nodeId", nodeId);
        String cypher = String.format(
                "MATCH (n:Entity) WHERE elementId(n) = $nodeId REMOVE n.%s", key);
        try (Session session = neo4jDriver.session()) {
            session.run(cypher, params).consume();
            return true;
        } catch (Exception e) {
            log.error("Neo4j 删除属性失败, nodeId={}, key={}", nodeId, key, e);
            throw e;
        }
    }

    /**
     * 过滤掉 Map 中的系统字段
     */
    private Map<String, Object> filterSystemFields(Map<String, Object> properties) {
        Map<String, Object> safe = new HashMap<>();
        if (properties != null) {
            for (Map.Entry<String, Object> entry : properties.entrySet()) {
                if (!SYSTEM_FIELDS.contains(entry.getKey())) {
                    safe.put(entry.getKey(), entry.getValue());
                }
            }
        }
        return safe;
    }

    // ======================== 关系管理（Neo4j 数据层 CRUD） ========================

    /** 关系系统字段，不允许通过属性接口修改/删除 */
    private static final Set<String> RELATION_SYSTEM_FIELDS = Set.of(
            "type", "modelId", "createTime", "elementId", "relationType",
            "startNodeElementId", "endNodeElementId", "sourceName", "targetName");

    /**
     * 分页查询关系列表（按 modelId）
     * 返回每条关系的关系名(type属性)、起点名、终点名、关系属性等。
     *
     * @param modelId  模型 id
     * @param keyword  关系名称关键词（可选）
     * @param pageNum  页码
     * @param pageSize 每页条数
     * @return {records, total, pageNum, pageSize}
     */
    public Map<String, Object> listRelations(Long modelId, String keyword, int pageNum, int pageSize) {
        Map<String, Object> params = new HashMap<>();
        params.put("modelId", modelId);
        params.put("skip", (pageNum - 1) * pageSize);
        params.put("limit", pageSize);

        boolean hasKeyword = keyword != null && !keyword.isBlank();
        if (hasKeyword) {
            params.put("keyword", keyword);
        }

        // 查询关系列表（附带起点、终点节点名）
        String listCypher = hasKeyword
                ? "MATCH (a:Entity)-[r]->(b:Entity) WHERE r.modelId = $modelId "
                + "AND toLower(r.type) CONTAINS toLower($keyword) "
                + "RETURN r, a.name as sourceName, b.name as targetName "
                + "ORDER BY r.type SKIP $skip LIMIT $limit"
                : "MATCH (a:Entity)-[r]->(b:Entity) WHERE r.modelId = $modelId "
                + "RETURN r, a.name as sourceName, b.name as targetName "
                + "ORDER BY r.type SKIP $skip LIMIT $limit";

        List<Map<String, Object>> relations = executeQuery(listCypher, params, record -> {
            Map<String, Object> row = relationshipToMap(record.get("r").asRelationship());
            row.put("sourceName", record.get("sourceName").isNull() ? "" : record.get("sourceName").asString());
            row.put("targetName", record.get("targetName").isNull() ? "" : record.get("targetName").asString());
            return row;
        });

        String countCypher = hasKeyword
                ? "MATCH ()-[r]->() WHERE r.modelId = $modelId AND toLower(r.type) CONTAINS toLower($keyword) RETURN count(r) as cnt"
                : "MATCH ()-[r]->() WHERE r.modelId = $modelId RETURN count(r) as cnt";
        List<Long> countResult = executeQuery(countCypher, params,
                record -> record.get("cnt").asLong());
        long total = countResult.isEmpty() ? 0L : countResult.get(0);

        Map<String, Object> result = new HashMap<>();
        result.put("records", relations);
        result.put("total", total);
        result.put("pageNum", pageNum);
        result.put("pageSize", pageSize);
        return result;
    }

    /**
     * 获取关系详情（含全部属性）
     */
    public Map<String, Object> getRelationDetail(String relId) {
        Map<String, Object> params = new HashMap<>();
        params.put("relId", relId);
        List<Map<String, Object>> result = executeQuery(
                "MATCH (a:Entity)-[r]->(b:Entity) WHERE elementId(r) = $relId "
                        + "RETURN r, a.name as sourceName, b.name as targetName",
                params,
                record -> {
                    Map<String, Object> row = relationshipToMap(record.get("r").asRelationship());
                    row.put("sourceName", record.get("sourceName").isNull() ? "" : record.get("sourceName").asString());
                    row.put("targetName", record.get("targetName").isNull() ? "" : record.get("targetName").asString());
                    return row;
                });
        return result.isEmpty() ? null : result.get(0);
    }

    /**
     * 删除关系
     */
    public boolean deleteRelation(String relId) {
        Map<String, Object> params = new HashMap<>();
        params.put("relId", relId);
        try (Session session = neo4jDriver.session()) {
            session.run("MATCH ()-[r]->() WHERE elementId(r) = $relId DELETE r", params).consume();
            return true;
        } catch (Exception e) {
            log.error("Neo4j 删除关系失败, relId={}", relId, e);
            throw e;
        }
    }

    /**
     * 设置关系属性（新增或更新）
     */
    public Map<String, Object> setRelationProperty(String relId, String key, Object value) {
        if (RELATION_SYSTEM_FIELDS.contains(key)) {
            throw new IllegalArgumentException("不能修改系统字段: " + key);
        }
        Map<String, Object> params = new HashMap<>();
        params.put("relId", relId);
        Map<String, Object> props = new HashMap<>();
        props.put(key, value);
        params.put("props", props);

        List<Map<String, Object>> result = executeQuery(
                "MATCH ()-[r]->() WHERE elementId(r) = $relId SET r += $props RETURN r",
                params,
                record -> relationshipToMap(record.get("r").asRelationship()));
        return result.isEmpty() ? null : result.get(0);
    }

    /**
     * 删除关系属性
     */
    public boolean removeRelationProperty(String relId, String key) {
        if (RELATION_SYSTEM_FIELDS.contains(key)) {
            throw new IllegalArgumentException("不能删除系统字段: " + key);
        }
        if (!PROP_KEY_PATTERN.matcher(key).matches()) {
            throw new IllegalArgumentException("属性名只能包含字母、数字和下划线，且不能以数字开头");
        }
        Map<String, Object> params = new HashMap<>();
        params.put("relId", relId);
        String cypher = String.format(
                "MATCH ()-[r]->() WHERE elementId(r) = $relId REMOVE r.%s", key);
        try (Session session = neo4jDriver.session()) {
            session.run(cypher, params).consume();
            return true;
        } catch (Exception e) {
            log.error("Neo4j 删除关系属性失败, relId={}, key={}", relId, key, e);
            throw e;
        }
    }

    // ======================== 以下是图谱探索方法 ========================

    /**
     * 通用查询执行方法
     *
     * @param cypher  Cypher 语句
     * @param params  参数
     * @param mapper  记录转换器
     * @param <T>     返回类型
     * @return 结果列表
     */
    private <T> List<T> executeQuery(String cypher, Map<String, Object> params, RecordMapper<T> mapper) {
        List<T> results = new ArrayList<>();
        try (Session session = neo4jDriver.session()) {
            Result result = session.run(cypher, params);
            while (result.hasNext()) {
                Record record = result.next();
                results.add(mapper.map(record));
            }
        } catch (Exception e) {
            log.error("Neo4j 查询失败, cypher={}, params={}", cypher, params, e);
            throw e;
        }
        return results;
    }

    /**
     * 构造边 Map（统一格式）
     * label 优先使用关系自身的 type 属性（实际关系名称，如"结义兄弟"），
     * 若不存在则回退到 Neo4j 关系类型（如"RELATION"）。
     */
    private Map<String, Object> buildEdge(Node a, Relationship r, Node b) {
        Map<String, Object> edge = new HashMap<>();
        edge.put("source", a.elementId());
        edge.put("target", b.elementId());
        // 实际关系名称存在 rel.type 属性里（由 Python graph_writer 写入）
        Object relationName = r.asMap().get("type");
        edge.put("label", relationName != null ? relationName : r.type());
        edge.put("data", relationshipToMap(r));
        return edge;
    }

    /**
     * Node 转 Map
     */
    private Map<String, Object> nodeToMap(Node node) {
        Map<String, Object> map = new HashMap<>(node.asMap());
        map.put("elementId", node.elementId());
        List<String> labels = new ArrayList<>();
        node.labels().forEach(labels::add);
        map.put("labels", labels);
        return map;
    }

    /**
     * Relationship 转 Map
     * 注意：rel.asMap() 中的 type 属性是实际关系名称（由 Python graph_writer 写入），
     * 不能用 rel.type()（Neo4j 关系类型，如"RELATION"）覆盖。
     * Neo4j 关系类型单独存到 relationType 字段。
     */
    private Map<String, Object> relationshipToMap(Relationship rel) {
        Map<String, Object> map = new HashMap<>(rel.asMap());
        map.put("elementId", rel.elementId());
        map.put("relationType", rel.type());
        map.put("startNodeElementId", rel.startNodeElementId());
        map.put("endNodeElementId", rel.endNodeElementId());
        return map;
    }

    /**
     * 记录转换器
     */
    @FunctionalInterface
    private interface RecordMapper<T> {
        T map(Record record);
    }
}

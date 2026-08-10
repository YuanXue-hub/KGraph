package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;
import java.util.Map;

/**
 * Neo4j 实体新增请求
 */
@Data
public class EntityNeo4jAddRequest implements Serializable {

    /**
     * 模型 id
     */
    private Long modelId;

    /**
     * 实体名称
     */
    private String name;

    /**
     * 实体类型
     */
    private String type;

    /**
     * 业务属性（键值对，不能包含系统字段）
     */
    private Map<String, Object> properties;

    private static final long serialVersionUID = 1L;
}

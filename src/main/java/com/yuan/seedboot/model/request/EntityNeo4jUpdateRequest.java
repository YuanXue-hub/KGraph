package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

/**
 * Neo4j 实体更新请求（名称和类型）
 */
@Data
public class EntityNeo4jUpdateRequest implements Serializable {

    /**
     * 节点 elementId
     */
    private String nodeId;

    /**
     * 实体名称
     */
    private String name;

    /**
     * 实体类型
     */
    private String type;

    private static final long serialVersionUID = 1L;
}

package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

/**
 * Neo4j 节点操作请求（删除等，只需 nodeId）
 */
@Data
public class EntityNeo4jNodeIdRequest implements Serializable {

    /**
     * 节点 elementId
     */
    private String nodeId;

    private static final long serialVersionUID = 1L;
}

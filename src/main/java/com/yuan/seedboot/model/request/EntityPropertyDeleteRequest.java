package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

/**
 * Neo4j 实体属性删除请求
 */
@Data
public class EntityPropertyDeleteRequest implements Serializable {

    /**
     * 节点 elementId
     */
    private String nodeId;

    /**
     * 属性名
     */
    private String key;

    private static final long serialVersionUID = 1L;
}

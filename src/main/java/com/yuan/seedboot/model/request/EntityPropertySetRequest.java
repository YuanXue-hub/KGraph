package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

/**
 * Neo4j 实体属性设置请求（新增或更新）
 */
@Data
public class EntityPropertySetRequest implements Serializable {

    /**
     * 节点 elementId
     */
    private String nodeId;

    /**
     * 属性名
     */
    private String key;

    /**
     * 属性值
     */
    private Object value;

    private static final long serialVersionUID = 1L;
}

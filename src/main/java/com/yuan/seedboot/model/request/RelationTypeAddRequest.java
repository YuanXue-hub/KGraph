package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

@Data
public class RelationTypeAddRequest implements Serializable {

    /**
     * 模型 id
     */
    private Long modelId;

    /**
     * 关系名称
     */
    private String relationName;

    /**
     * 关系描述
     */
    private String description;

    /**
     * 起始实体类型 id
     */
    private Long sourceEntityTypeId;

    /**
     * 终止实体类型 id
     */
    private Long targetEntityTypeId;

    private static final long serialVersionUID = 1L;
}

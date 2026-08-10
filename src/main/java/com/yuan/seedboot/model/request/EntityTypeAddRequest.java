package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

@Data
public class EntityTypeAddRequest implements Serializable {

    /**
     * 模型 id
     */
    private Long modelId;

    /**
     * 实体类型名称
     */
    private String entityName;

    /**
     * 实体描述
     */
    private String description;

    /**
     * 显示颜色
     */
    private String color;

    /**
     * 图标
     */
    private String icon;

    private static final long serialVersionUID = 1L;
}

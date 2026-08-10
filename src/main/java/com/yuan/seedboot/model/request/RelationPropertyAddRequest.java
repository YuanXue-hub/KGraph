package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

@Data
public class RelationPropertyAddRequest implements Serializable {

    /**
     * 关系类型 id
     */
    private Long relationTypeId;

    /**
     * 属性名称
     */
    private String propertyName;

    /**
     * 属性类型: string/number/date/boolean
     */
    private String propertyType;

    /**
     * 是否必填: 0-否 1-是
     */
    private Integer isRequired;

    /**
     * 默认值
     */
    private String defaultValue;

    /**
     * 属性描述
     */
    private String description;

    private static final long serialVersionUID = 1L;
}

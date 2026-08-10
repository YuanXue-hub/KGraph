package com.yuan.seedboot.model.request;

import lombok.Data;

import java.io.Serializable;

/**
 * 实体属性更新请求
 */
@Data
public class EntityPropertyUpdateRequest implements Serializable {

    /**
     * 属性 id
     */
    private Long id;

    /**
     * 属性名称
     */
    private String propertyName;

    /**
     * 属性类型
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

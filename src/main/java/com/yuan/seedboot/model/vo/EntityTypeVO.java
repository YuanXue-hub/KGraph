package com.yuan.seedboot.model.vo;

import com.yuan.seedboot.model.entity.GraphEntityProperty;
import com.yuan.seedboot.model.entity.GraphEntityType;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.io.Serializable;
import java.util.List;

/**
 * 实体类型 VO（含属性列表）
 */
@EqualsAndHashCode(callSuper = true)
@Data
public class EntityTypeVO extends GraphEntityType implements Serializable {

    /**
     * 实体属性列表
     */
    private List<GraphEntityProperty> properties;

    private static final long serialVersionUID = 1L;
}

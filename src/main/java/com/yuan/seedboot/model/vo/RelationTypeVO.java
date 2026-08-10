package com.yuan.seedboot.model.vo;

import com.yuan.seedboot.model.entity.GraphRelationProperty;
import com.yuan.seedboot.model.entity.GraphRelationType;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.io.Serializable;
import java.util.List;

/**
 * 关系类型 VO（含属性列表 + 起止实体名称）
 */
@EqualsAndHashCode(callSuper = true)
@Data
public class RelationTypeVO extends GraphRelationType implements Serializable {

    /**
     * 关系属性列表
     */
    private List<GraphRelationProperty> properties;

    /**
     * 起始实体类型名称
     */
    private String sourceEntityName;

    /**
     * 终止实体类型名称
     */
    private String targetEntityName;

    private static final long serialVersionUID = 1L;
}

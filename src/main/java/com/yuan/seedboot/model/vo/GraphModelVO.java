package com.yuan.seedboot.model.vo;

import com.yuan.seedboot.model.entity.GraphModel;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.io.Serializable;
import java.util.List;

/**
 * 图谱模型 VO（含实体类型 + 关系类型）
 */
@EqualsAndHashCode(callSuper = true)
@Data
public class GraphModelVO extends GraphModel implements Serializable {

    /**
     * 实体类型列表
     */
    private List<EntityTypeVO> entityTypes;

    /**
     * 关系类型列表
     */
    private List<RelationTypeVO> relationTypes;

    private static final long serialVersionUID = 1L;
}

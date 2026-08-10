package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.util.Date;

@TableName(value = "graph_relation_property")
@Data
public class GraphRelationProperty {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("relationTypeId")
    private Long relationTypeId;

    @TableField("propertyName")
    private String propertyName;

    @TableField("propertyType")
    private String propertyType;

    @TableField("isRequired")
    private Integer isRequired;

    @TableField("defaultValue")
    private String defaultValue;

    /**
     * 属性描述
     */
    @TableField("description")
    private String description;

    @TableField("sortOrder")
    private Integer sortOrder;

    @TableField("createTime")
    private Date createTime;

    @TableLogic
    @TableField("isDeleted")
    private Integer isDeleted;
}

package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.util.Date;

@TableName(value = "graph_relation_type")
@Data
public class GraphRelationType {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("modelId")
    private Long modelId;

    @TableField("relationName")
    private String relationName;

    @TableField("description")
    private String description;

    @TableField("sourceEntityTypeId")
    private Long sourceEntityTypeId;

    @TableField("targetEntityTypeId")
    private Long targetEntityTypeId;

    @TableField("sortOrder")
    private Integer sortOrder;

    @TableField("createTime")
    private Date createTime;

    @TableField("updateTime")
    private Date updateTime;

    @TableLogic
    @TableField("isDeleted")
    private Integer isDeleted;
}

package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.util.Date;

@TableName(value = "graph_entity_type")
@Data
public class GraphEntityType {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("modelId")
    private Long modelId;

    @TableField("entityName")
    private String entityName;

    @TableField("description")
    private String description;

    @TableField("color")
    private String color;

    @TableField("icon")
    private String icon;

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

package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.util.Date;

@TableName(value = "graph_project")
@Data
public class GraphProject {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("projectName")
    private String projectName;

    @TableField("projectDescription")
    private String projectDescription;

    @TableField("storageEngine")
    private String storageEngine;

    @TableField("isConfiguredStorage")
    private Integer isConfiguredStorage;

    @TableField("isGraphSpaceCreated")
    private Integer isGraphSpaceCreated;

    @TableField("createBy")
    private Long createBy;

    /**
     * 创建人姓名（非数据库字段，由 Controller 层填充）
     */
    @TableField(exist = false)
    private String createByName;

    @TableField("createTime")
    private Date createTime;

    @TableField("updateTime")
    private Date updateTime;

    @TableLogic
    @TableField("isDeleted")
    private Integer isDeleted;
}

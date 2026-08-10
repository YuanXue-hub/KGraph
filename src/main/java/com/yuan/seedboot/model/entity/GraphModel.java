package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.util.Date;

@TableName(value = "graph_model")
@Data
public class GraphModel {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("projectId")
    private Long projectId;

    @TableField("modelName")
    private String modelName;

    @TableField("modelDescription")
    private String modelDescription;

    @TableField("version")
    private Integer version;

    @TableField("entityCount")
    private Integer entityCount;

    @TableField("relationCount")
    private Integer relationCount;

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

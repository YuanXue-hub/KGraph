package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.util.Date;

@TableName(value = "train_task")
@Data
public class TrainTask {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("taskName")
    private String taskName;

    @TableField("projectId")
    private Long projectId;

    @TableField("annotationTaskId")
    private Long annotationTaskId;

    @TableField("dataset")
    private String dataset;

    @TableField("architecture")
    private String architecture;

    @TableField("version")
    private String version;

    @TableField("status")
    private String status;

    @TableField("progress")
    private Integer progress;

    @TableField("currentEpoch")
    private Integer currentEpoch;

    @TableField("epochs")
    private Integer epochs;

    @TableField("config")
    private String config;

    @TableField("metrics")
    private String metrics;

    @TableField("history")
    private String history;

    @TableField("createBy")
    private Long createBy;

    @TableField("createTime")
    private Date createTime;

    @TableField("updateTime")
    private Date updateTime;

    @TableLogic
    @TableField("isDeleted")
    private Integer isDeleted;
}

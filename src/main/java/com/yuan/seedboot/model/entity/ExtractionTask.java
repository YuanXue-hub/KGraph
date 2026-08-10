package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.util.Date;

@TableName(value = "extraction_task")
@Data
public class ExtractionTask {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("projectId")
    private Long projectId;

    @TableField("modelId")
    private Long modelId;

    @TableField("corpusId")
    private Long corpusId;

    @TableField("inputText")
    private String inputText;

    @TableField("extractionType")
    private String extractionType;

    @TableField("inputConfig")
    private String inputConfig;

    @TableField("result")
    private String result;

    @TableField("status")
    private Integer status;

    @TableField("tokenConsumed")
    private Integer tokenConsumed;

    @TableField("duration")
    private Long duration;

    @TableField("createBy")
    private Long createBy;

    @TableField("createTime")
    private Date createTime;

    @TableField("updateTime")
    private Date updateTime;
}

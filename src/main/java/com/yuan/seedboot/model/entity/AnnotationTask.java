package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.util.Date;

@TableName(value = "annotation_task")
@Data
public class AnnotationTask {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("taskName")
    private String taskName;

    @TableField("projectId")
    private Long projectId;

    @TableField("corpusId")
    private Long corpusId;

    @TableField("corpusTitle")
    private String corpusTitle;

    @TableField("text")
    private String text;

    @TableField("annotator")
    private String annotator;

    @TableField("reviewer")
    private String reviewer;

    @TableField("totalSentences")
    private Integer totalSentences;

    @TableField("annotatedSentences")
    private Integer annotatedSentences;

    @TableField("entities")
    private String entities;

    @TableField("relations")
    private String relations;

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

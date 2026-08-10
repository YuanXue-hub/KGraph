package com.yuan.seedboot.model.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.util.Date;

@TableName(value = "corpus")
@Data
public class Corpus {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    @TableField("projectId")
    private Long projectId;

    @TableField("title")
    private String title;

    @TableField("content")
    private String content;

    @TableField("source")
    private String source;

    @TableField("filePath")
    private String filePath;

    @TableField("status")
    private Integer status;

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
